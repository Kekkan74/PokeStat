from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import re
from typing import Optional
from pokestat.calculator import calculate_all_stats
from pokestat.catalog import resolve_move, resolve_pokemon
from pokestat.damage_engine import get_effective_move_type, get_type_effectiveness
from pokestat.models import (
    Gender,
    IVSpread,
    Move,
    MoveCategory,
    Nature,
    PokemonState,
    PokemonType,
    StatName,
    StatSpread,
)


class TeamFormat(str, Enum):
    """Formato competitivo o modo de juego del equipo."""
    DOUBLES = "duos"    # VGC / Dobles (4v4 de 6, Protect, Speed Control, Redirección, Fake Out)
    SINGLES = "6v6"     # Singles 6v6 / Randomlocke (Hazards, Pivotes, Sweeper/Wall balance)


_STAT_TOKEN_MAP: dict[str, str] = {
    "hp": "hp",
    "atk": "atk",
    "def": "def",
    "spa": "spa",
    "spd": "spd",
    "spe": "spe",
}

# Tipos ofensivos relevantes a evaluar en la matriz de cobertura y debilidades (los 18 tipos elementales)
CORE_TYPES: list[PokemonType] = [t for t in PokemonType if t != PokemonType.STELLAR]


def _parse_stat_line(raw: str, default_val: int) -> dict[str, int]:
    """Convierte '252 HP / 4 Def / 252 Spe' en un diccionario para StatSpread / IVSpread."""
    result = {k: default_val for k in ("hp", "atk", "def", "spa", "spd", "spe")}
    for chunk in raw.split("/"):
        chunk = chunk.strip()
        m = re.match(r"(\d+)\s+([A-Za-z]+)", chunk)
        if m:
            val = int(m.group(1))
            stat_key = _STAT_TOKEN_MAP.get(m.group(2).lower())
            if stat_key:
                result[stat_key] = val
    return result


def parse_showdown_block(block: str) -> PokemonState:
    """
    Parsea un bloque individual en formato Pokémon Showdown / PokéPaste.
    Soporta además comentarios opcionales para Randomlocke:
      Types: Fire, Fairy
      BaseStats: 80, 100, 80, 120, 80, 110
    """
    lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Bloque de Pokémon vacío.")

    # Primera línea: "Apodo (Especie) (M) @ Objeto" o "Especie (F) @ Objeto" o "Especie @ Objeto"
    first = lines[0]
    item = None
    if "@" in first:
        left, right = first.split("@", 1)
        item = right.strip()
    else:
        left = first.strip()

    left = left.strip()

    # Detectar género "(M)" o "(F)"
    gender = Gender.GENDERLESS
    gender_match = re.search(r"\s*\(([MFmf])\)\s*$", left)
    if gender_match:
        g_val = gender_match.group(1).upper()
        gender = Gender.MALE if g_val == "M" else Gender.FEMALE
        left = left[:gender_match.start()].strip()

    nickname = None
    species_name = left.strip()
    paren_match = re.match(r"^(.+?)\s*\(([^()]+)\)\s*$", left)
    if paren_match:
        nickname = paren_match.group(1).strip()
        species_name = paren_match.group(2).strip()

    ability = None
    level = 50
    tera_type = None
    nature = Nature.SERIOUS
    evs = StatSpread()
    ivs = IVSpread()
    moves: list[Move] = []
    custom_types: str | None = None
    custom_stats: str | None = None

    for ln in lines[1:]:
        low = ln.lower()
        if low.startswith("gender:"):
            g_raw = ln.split(":", 1)[1].strip().upper()
            if g_raw in ("M", "MALE"):
                gender = Gender.MALE
            elif g_raw in ("F", "FEMALE"):
                gender = Gender.FEMALE
            else:
                gender = Gender.GENDERLESS
        elif low.startswith("ability:"):
            ability = ln.split(":", 1)[1].strip()
        elif low.startswith("level:"):
            try:
                level = int(ln.split(":", 1)[1].strip())
            except ValueError:
                level = 50
        elif low.startswith("tera type:"):
            t_raw = ln.split(":", 1)[1].strip().capitalize()
            if t_raw in PokemonType._value2member_map_:
                tera_type = PokemonType(t_raw)
        elif low.startswith("types:"):
            custom_types = ln.split(":", 1)[1].strip()
        elif low.startswith("basestats:"):
            custom_stats = ln.split(":", 1)[1].strip()
        elif low.startswith("evs:"):
            ev_dict = _parse_stat_line(ln.split(":", 1)[1], default_val=0)
            evs = StatSpread(**ev_dict)
        elif low.startswith("ivs:"):
            iv_dict = _parse_stat_line(ln.split(":", 1)[1], default_val=31)
            ivs = IVSpread(**iv_dict)
        elif low.endswith("nature"):
            nat_name = ln.split()[0].strip().capitalize()
            if nat_name in Nature._value2member_map_:
                nature = Nature(nat_name)
        elif ln.startswith("-") or ln.startswith("*"):
            move_raw = ln[1:].strip()
            # Soporte opcional para movimientos personalizados en línea: "- MiAtaque [Fire, Physical, 100]"
            m_custom = re.match(r"^(.+?)\s*\[([A-Za-z]+)\s*,\s*([A-Za-z]+)\s*,\s*(\d+)\]$", move_raw)
            if m_custom:
                m_name = m_custom.group(1).strip()
                m_type = PokemonType(m_custom.group(2).capitalize())
                m_cat = MoveCategory(m_custom.group(3).capitalize())
                m_bp = int(m_custom.group(4))
                moves.append(resolve_move(m_name, move_type=m_type, move_category=m_cat, move_bp=m_bp))
            else:
                moves.append(resolve_move(move_raw))

    try:
        poke = resolve_pokemon(species_name, custom_types=custom_types, custom_base_stats=custom_stats)
    except ValueError:
        # Si es un Pokémon fuera del catálogo y no indicó stats, creamos uno equilibrado 85/85/85/85/85/85 Normal
        poke = resolve_pokemon(
            species_name,
            custom_types=custom_types or "Normal",
            custom_base_stats=custom_stats or "85,85,85,85,85,85",
        )

    return PokemonState(
        pokemon=poke,
        nickname=nickname,
        gender=gender,
        level=level,
        nature=nature,
        evs=evs,
        ivs=ivs,
        item=item,
        ability=ability,
        tera_type=tera_type,
        moves=moves[:4],
    )


def load_team_from_file(path: str | Path) -> list[PokemonState]:
    """
    Carga un equipo de hasta 6 Pokémon desde un archivo .txt (formato Showdown/PokéPaste)
    o .json.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de equipo: {file_path}")

    raw_text = file_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError("El archivo de equipo está vacío.")

    if file_path.suffix.lower() == ".json":
        data = json.loads(raw_text)
        team: list[PokemonState] = []
        for entry in data:
            poke = resolve_pokemon(
                entry["name"],
                custom_types=",".join(entry.get("types", [])) or None,
                custom_base_stats=entry.get("base_stats_csv"),
            )
            evs = StatSpread(**entry.get("evs", {}))
            moves = [resolve_move(m) for m in entry.get("moves", [])[:4]]
            tera = PokemonType(entry["tera_type"]) if entry.get("tera_type") else None
            team.append(
                PokemonState(
                    pokemon=poke,
                    nickname=entry.get("nickname"),
                    gender=Gender(entry.get("gender", "N")),
                    level=entry.get("level", 50),
                    nature=Nature(entry.get("nature", "Serious")),
                    evs=evs,
                    item=entry.get("item"),
                    ability=entry.get("ability"),
                    tera_type=tera,
                    moves=moves,
                )
            )
        return team

    # Separar por bloques en blanco
    blocks = re.split(r"\n\s*\n", raw_text)
    team = [parse_showdown_block(b) for b in blocks if b.strip()]
    return team[:6]


# ============================================================================
# CONSTANTES TÁCTICAS PARA CLASIFICACIÓN DE ROLES COMPETITIVOS
# ============================================================================

REDIRECTION_MOVES: set[str] = {"follow me", "rage powder", "spotlight", "ally switch"}
PROTECT_MOVES: set[str] = {
    "protect", "detect", "spiky shield", "baneful bunker", "wide guard",
    "quick guard", "kings shield", "king's shield", "silk trap", "burning bulwark", "obstruct"
}
SPEED_CONTROL_MOVES: set[str] = {
    "tailwind", "trick room", "icy wind", "electroweb", "thunder wave",
    "glare", "quash", "string shot", "bulldoze", "scary face"
}
SUPPORT_DISRUPT_MOVES: set[str] = {
    "fake out", "parting shot", "spore", "yawn", "will-o-wisp", "thunder wave",
    "taunt", "encore", "helping hand", "haze", "clear smog", "roar", "whirlwind",
    "reflect", "light screen", "aurora veil", "heal bell", "aromatherapy", "trick",
    "switcheroo", "hypnosis", "sleep powder"
}
RECOVERY_MOVES: set[str] = {
    "recover", "roost", "slack off", "soft-boiled", "synthesis", "wish", "rest",
    "shore up", "strength sap", "milk drink", "morning sun", "moonlight", "life dew", "heal order"
}
SETUP_MOVES: set[str] = {
    "swords dance", "nasty plot", "dragon dance", "calm mind", "bulk up",
    "quiver dance", "iron defense", "curse", "shell smash", "shift gear",
    "victory dance", "tidy up", "fillet away", "belly drum", "growth", "agility", "rock polish",
    "tail glow", "clangorous soul", "no retreat", "autotomize", "hone claws", "coil"
}
PIVOT_MOVES: set[str] = {
    "u-turn", "volt switch", "flip turn", "parting shot", "chilly reception", "teleport", "shed tail", "baton pass"
}
HAZARD_SET_MOVES: set[str] = {
    "stealth rock", "spikes", "toxic spikes", "sticky web", "ceaseless edge", "stone axe"
}
HAZARD_REMOVE_MOVES: set[str] = {
    "rapid spin", "defog", "mortal spin", "tidy up", "court change"
}
OFFENSIVE_ITEMS: set[str] = {
    "choice band", "choice specs", "choice scarf", "life orb", "expert belt",
    "focus sash", "booster energy", "loaded dice", "punching glove",
    "mystic water", "charcoal", "magnet", "miracle seed", "never-melt ice",
    "black glasses", "soft sand", "spell tag", "twisted spoon", "dragon fang",
    "sharp beak", "poison barb", "hard stone", "silver powder", "metal coat", "silk scarf",
    "garchompite", "air balloon", "zoom lens"
}
DEFENSIVE_ITEMS: set[str] = {
    "leftovers", "sitrus berry", "assault vest", "eviolite", "rocky helmet",
    "heavy-duty boots", "black sludge", "iapapa berry", "aguav berry", "figy berry",
    "wiki berry", "mago berry", "covert cloak", "safety goggles", "mental herb"
}
OFFENSIVE_ABILITIES: set[str] = {
    "protosynthesis", "quark drive", "unseen fist", "sword of ruin", "beads of ruin",
    "supreme overlord", "huge power", "pure power", "adaptability", "sheer force",
    "aerilate", "pixilate", "refrigerate", "galvanize", "moxie", "beast boost",
    "transistor", "dragons maw", "dragon's maw", "tough claws", "sharpness",
    "technician", "guts", "magic guard", "contrary", "speed boost", "libero", "protean"
}
DEFENSIVE_ABILITIES: set[str] = {
    "intimidate", "fur coat", "ice scales", "fluffy", "unaware", "regenerator",
    "friend guard", "vessel of ruin", "tablets of ruin", "thick fat", "water absorb",
    "earth eater", "well-baked body", "solid rock", "multiscale", "shadow shield",
    "filter", "prism armor", "stamına", "stamina", "good as gold", "dauntless shield",
    "magic bounce", "poison heal", "natural cure", "purifying salt"
}


@dataclass
class MemberRoleInfo:
    """Rol competitivo y táctico asignado a un miembro del equipo."""
    member_name: str
    species_name: str
    role_tag: str
    role_title: str
    role_icon: str
    is_damage_dealer: bool
    is_tank: bool
    is_support: bool
    details: str


@dataclass
class FormatCompositionReport:
    """Auditoría de composición y roles según el formato de juego (Dúos vs 6v6)."""
    team_format: TeamFormat
    archetype_label: str
    damage_dealers_count: int
    tanks_count: int
    supports_count: int
    # 6v6 específico
    wallbreakers_count: int = 0
    sweepers_count: int = 0
    physical_walls_count: int = 0
    special_walls_count: int = 0
    pivots_count: int = 0
    hazard_controllers_count: int = 0
    # Veredictos del formato
    damage_verdict_title: str = ""
    damage_verdict_status: str = "OPTIMAL"  # "OPTIMAL", "WARNING", "CRITICAL"
    damage_verdict_desc: str = ""
    tank_verdict_title: str = ""
    tank_verdict_status: str = "OPTIMAL"    # "OPTIMAL", "WARNING", "CRITICAL"
    tank_verdict_desc: str = ""
    role_assignments: list[MemberRoleInfo] = field(default_factory=list)


# ============================================================================
# MOTOR DE AUDITORÍA TÁCTICA Y EQUILIBRIO DE EQUIPO (6v6 vs DÚOS/VGC)
# ============================================================================

@dataclass
class TypeDefenseSummary:
    """Resumen defensivo del equipo frente a un tipo elemental atacante."""
    attacking_type: PokemonType
    weak_count: int = 0       # x2 o x4
    resist_count: int = 0     # x0.5 o x0.25
    immune_count: int = 0     # x0 (por tipo o habilidad como Levitate/Volt Absorb)
    per_member_multiplier: list[float] = field(default_factory=list)


@dataclass
class TeamAnalysisReport:
    """Diagnóstico integral del equipo y propuestas de mejora."""
    team: list[PokemonState]
    team_format: TeamFormat
    balance_score: int  # 0..100
    verdict_label: str
    defensive_matrix: dict[PokemonType, TypeDefenseSummary]
    top_weakness_types: list[tuple[PokemonType, int, int]]  # (Tipo, cant_debiles, cant_resistencias_o_inmunidades)
    top_resistance_types: list[tuple[PokemonType, int]]     # (Tipo, cant_resistencias_o_inmunidades)
    offensive_super_effective_coverage: set[PokemonType]
    uncovered_offensive_types: list[PokemonType]
    speed_tiers: list[tuple[str, int, str]]  # (Nombre, Spe real, Naturaleza/EVs)
    physical_attackers: int
    special_attackers: int
    # Auditoría Física vs Especial
    avg_team_def: float
    avg_team_spd: float
    physically_fragile_members: list[tuple[str, int, int]]  # (Nombre, HP, Def)
    specially_fragile_members: list[tuple[str, int, int]]   # (Nombre, HP, SpD)
    bulk_orientation_verdict: str  # e.g. "Equilibrado", "Más vulnerable a Físico", "Más vulnerable a Especial"
    bulk_differential_pct: float
    strengths: list[str]
    warnings: list[str]
    recommendations: list[str]
    composition: Optional[FormatCompositionReport] = None


def classify_member_role(member: PokemonState, team_format: TeamFormat) -> MemberRoleInfo:
    """
    Clasifica a un miembro del equipo en su rol táctico y competitivo según sus
    estadísticas calculadas, objetos, habilidades, movimientos y el formato de batalla.
    """
    m_stats = calculate_all_stats(member)
    hp = m_stats[StatName.HP]
    atk = m_stats[StatName.ATK]
    def_ = m_stats[StatName.DEF]
    spa = m_stats[StatName.SPA]
    spd = m_stats[StatName.SPD]
    spe = m_stats[StatName.SPE]

    it_norm = (member.item or "").strip().lower()
    ab_norm = (member.ability or "").strip().lower()

    eff_atk = atk * (1.5 if it_norm == "choice band" else 1.0) * (2.0 if ab_norm in {"huge power", "pure power"} else 1.0)
    eff_spa = spa * (1.5 if it_norm == "choice specs" else 1.0)
    eff_spe = spe * (1.5 if it_norm == "choice scarf" else 1.0)

    eff_def = def_ * (1.5 if it_norm == "eviolite" else 1.0) * (2.0 if ab_norm == "fur coat" else (1.5 if ab_norm == "fluffy" else 1.0))
    eff_spd = spd * (1.5 if it_norm in {"assault vest", "eviolite"} else 1.0) * (2.0 if ab_norm == "ice scales" else 1.0)

    phys_bulk = hp * eff_def
    spec_bulk = hp * eff_spd
    max_offensive = max(eff_atk, eff_spa)

    move_names = {mv.name.strip().lower() for mv in member.moves}
    damaging_moves = [mv for mv in member.moves if mv.category != MoveCategory.STATUS and mv.base_power > 0]

    has_redir = bool(move_names & REDIRECTION_MOVES)
    has_sc = bool(move_names & SPEED_CONTROL_MOVES)
    has_support = bool(move_names & SUPPORT_DISRUPT_MOVES)
    has_recov = bool(move_names & RECOVERY_MOVES)
    has_setup = bool(move_names & SETUP_MOVES)
    has_piv = bool(move_names & PIVOT_MOVES)
    has_hz_set = bool(move_names & HAZARD_SET_MOVES)
    has_hz_rem = bool(move_names & HAZARD_REMOVE_MOVES)

    disp_name = member.nickname or member.pokemon.name

    has_defensive_item = it_norm in DEFENSIVE_ITEMS
    has_offensive_item = it_norm in OFFENSIVE_ITEMS
    has_defensive_ability = ab_norm in DEFENSIVE_ABILITIES
    has_high_dual_bulk = (phys_bulk >= 19000 and spec_bulk >= 19000)

    if team_format == TeamFormat.DOUBLES:
        # Dúos / VGC
        if has_redir:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="SUPPORT_REDIR",
                role_title="Soporte / Redirección",
                role_icon="🎯",
                is_damage_dealer=False,
                is_tank=(phys_bulk >= 16000 or spec_bulk >= 16000),
                is_support=True,
                details="Redirige ataques enemigos (Follow Me / Rage Powder) para proteger al compañero atacante.",
            )
        if (has_sc and len(damaging_moves) <= 2) or (ab_norm == "prankster" and len(damaging_moves) <= 2):
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="SPEED_CONTROL",
                role_title="Control de Velocidad / Support",
                role_icon="⚡",
                is_damage_dealer=False,
                is_tank=(phys_bulk >= 16000 or spec_bulk >= 16000),
                is_support=True,
                details="Controla el orden de turno mediante Tailwind, Trick Room, Icy Wind o cambios de estado.",
            )
        if (("spore" in move_names or "yawn" in move_names) and len(damaging_moves) <= 1):
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="SUPPORT_DISRUPT",
                role_title="Soporte / Disrupción Pura",
                role_icon="🎯",
                is_damage_dealer=False,
                is_tank=(phys_bulk >= 16000 or spec_bulk >= 16000),
                is_support=True,
                details="Inutiliza rivales con sueño o cambios de estado para crear ventajas de posicionamiento.",
            )

        is_tank_profile = (
            (has_defensive_item and (phys_bulk >= 16000 or spec_bulk >= 16000))
            or (has_defensive_ability and (phys_bulk >= 16000 or spec_bulk >= 16000))
            or has_high_dual_bulk
        ) and not (has_offensive_item and (phys_bulk < 18000 or spec_bulk < 18000))

        if is_tank_profile:
            if max_offensive >= 135 and len(damaging_moves) >= 2:
                return MemberRoleInfo(
                    member_name=disp_name,
                    species_name=member.pokemon.name,
                    role_tag="BULKY_ATTACKER",
                    role_title="Tanque / Atacante Bulky",
                    role_icon="⚖️",
                    is_damage_dealer=True,
                    is_tank=True,
                    is_support=("fake out" in move_names or has_piv or has_sc),
                    details=f"Gran resistencia ({phys_bulk//1000}k bulk físico / {spec_bulk//1000}k bulk esp.) combinada con pegada ofensiva respetable.",
                )
            else:
                return MemberRoleInfo(
                    member_name=disp_name,
                    species_name=member.pokemon.name,
                    role_tag="TANK",
                    role_title="Tanque Defensivo / Utilidad",
                    role_icon="🛡️",
                    is_damage_dealer=False,
                    is_tank=True,
                    is_support=True,
                    details="Absorbe impactos rivales, desgasta con cambios de estado o asiste con utilidad sin buscar noqueos directos.",
                )

        return MemberRoleInfo(
            member_name=disp_name,
            species_name=member.pokemon.name,
            role_tag="SWEEPER",
            role_title="Atacante Principal / Sweeper",
            role_icon="⚔️",
            is_damage_dealer=True,
            is_tank=False,
            is_support=False,
            details=f"Alta presión de noqueo ({'Físico' if eff_atk >= eff_spa else 'Especial'}) con {int(max_offensive)} de poder ofensivo.",
        )

    else:
        # 1. Hazard Setter / Control de Campo especializado (con poco ataque directo)
        if has_hz_set and len(damaging_moves) <= 2:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="HAZARDS",
                role_title="Hazard Setter / Entrada",
                role_icon="🪨",
                is_damage_dealer=False,
                is_tank=(phys_bulk >= 16000 or spec_bulk >= 16000),
                is_support=True,
                details="Coloca rocas o púas (Stealth Rock / Spikes / Red Viscosa) para desgastar al rival en cada cambio.",
            )

        # 2. Pivote Defensivo (Momentum Pivot con U-turn / Volt Switch / Parting Shot + Bulk)
        if has_piv and (has_defensive_item or phys_bulk >= 16000 or spec_bulk >= 16000) and not (has_offensive_item and max_offensive >= 150):
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="PIVOT",
                role_title="Pivote Defensivo / VoltTurn",
                role_icon="🔄",
                is_damage_dealer=(max_offensive >= 140),
                is_tank=True,
                is_support=True,
                details="Mantiene la iniciativa con U-turn / Volt Switch / Parting Shot absorbiendo golpes.",
            )

        # 3. Muralla Física (Physical Wall)
        is_phys_wall = (
            (phys_bulk >= 18000 and phys_bulk >= spec_bulk * 1.05)
            or (member.nature in {Nature.IMPISH, Nature.BOLD, Nature.RELAXED} and phys_bulk >= 16000)
            or (ab_norm in {"fur coat", "unaware"} and phys_bulk >= 15000)
        ) and not (has_offensive_item and max_offensive >= 145)

        if is_phys_wall:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="PHYSICAL_WALL",
                role_title="Muralla Física (Physical Wall)",
                role_icon="🛡️",
                is_damage_dealer=(max_offensive >= 140 and len(damaging_moves) >= 3),
                is_tank=True,
                is_support=(has_hz_set or has_piv or has_hz_rem),
                details=f"Especialista en absorber daño físico ({phys_bulk//1000}k bulk) y frenar atacantes físicos rivales.",
            )

        # 4. Muralla Especial (Special Wall)
        is_spec_wall = (
            (spec_bulk >= 18000 and spec_bulk >= phys_bulk * 1.05)
            or (it_norm == "assault vest" and spec_bulk >= 16000)
            or (member.nature in {Nature.CALM, Nature.CAREFUL, Nature.SASSY} and spec_bulk >= 16000)
            or (ab_norm in {"ice scales", "vessel of ruin"} and spec_bulk >= 15000)
        ) and not (has_offensive_item and max_offensive >= 145)

        if is_spec_wall:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="SPECIAL_WALL",
                role_title="Muralla Especial (Special Wall)",
                role_icon="🔮",
                is_damage_dealer=(max_offensive >= 140 and len(damaging_moves) >= 3),
                is_tank=True,
                is_support=(has_hz_set or has_piv or has_hz_rem),
                details=f"Especialista en absorber daño especial ({spec_bulk//1000}k bulk) frente a atacantes especiales rivales.",
            )

        # 5. Setup Sweeper / Cleaner
        if has_setup or (it_norm == "choice scarf" and max_offensive >= 135):
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="SWEEPER",
                role_title="Setup Sweeper / Cleaner",
                role_icon="🧹",
                is_damage_dealer=True,
                is_tank=False,
                is_support=False,
                details="Aumenta sus estadísticas con movimientos de boosteo o limpia al final con velocidad.",
            )

        # 6. Wallbreaker (Rompedor de Murallas)
        if max_offensive >= 145 or has_offensive_item or len(damaging_moves) >= 3:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="WALLBREAKER",
                role_title="Wallbreaker (Rompedor de Murallas)",
                role_icon="💥",
                is_damage_dealer=True,
                is_tank=has_high_dual_bulk,
                is_support=False,
                details=f"Inmensa pegada inmediata ({int(max_offensive)} poder ofensivo) para demoler murallas rivales.",
            )

        if max_offensive >= 135:
            return MemberRoleInfo(
                member_name=disp_name,
                species_name=member.pokemon.name,
                role_tag="ATTACKER",
                role_title="Atacante General",
                role_icon="⚔️",
                is_damage_dealer=True,
                is_tank=False,
                is_support=False,
                details="Aporta daño ofensivo general al equipo.",
            )
        return MemberRoleInfo(
            member_name=disp_name,
            species_name=member.pokemon.name,
            role_tag="TANK_GENERAL",
            role_title="Tanque / Apoyo Defensivo",
            role_icon="🛡️",
            is_damage_dealer=False,
            is_tank=True,
            is_support=True,
            details="Aporta presencia defensiva y absorción de turnos.",
        )


def audit_format_composition(
    team: list[PokemonState],
    roles: list[MemberRoleInfo],
    team_format: TeamFormat,
    warnings: list[str],
    recommendations: list[str],
    strengths: list[str],
) -> tuple[FormatCompositionReport, int]:
    """
    Evalúa si al equipo le falta daño, le faltan tanques o si está desequilibrado
    según las reglas y dinámicas de Dúos (VGC) o 6v6 Singles. Devuelve el reporte y el ajuste de puntuación.
    """
    score_mod = 0
    pure_attackers = sum(1 for r in roles if r.is_damage_dealer and not r.is_tank)
    bulky_attackers = sum(1 for r in roles if r.is_damage_dealer and r.is_tank)
    pure_tanks = sum(1 for r in roles if r.is_tank and not r.is_damage_dealer)
    pure_supports = sum(1 for r in roles if r.is_support and not r.is_damage_dealer and not r.is_tank)
    total_attackers = pure_attackers + bulky_attackers
    total_tanks = pure_tanks + bulky_attackers
    supports_count = sum(1 for r in roles if r.is_support)

    if team_format == TeamFormat.DOUBLES:
        # ==========================
        # AUDITORÍA PARA DÚOS / VGC
        # ==========================
        # 1. ¿Te falta daño?
        if total_attackers <= 1:
            dmg_title = "¿Te falta daño?: SÍ, FALTA DE DAÑO CRÍTICA"
            dmg_status = "CRITICAL"
            dmg_desc = (
                f"Tu equipo solo cuenta con {total_attackers} atacante con suficiente pegada. "
                "En Dúos los combates se deciden en 6 a 8 turnos. "
                "Si el rival noquea o neutraliza a tu único atacante (con Fake Out, Intimidate o fuego concentrado), "
                "te quedarás sin capacidad de respuesta ni daño para cerrar la partida."
            )
            warnings.append(f"Falta grave de daño en Dúos: solo tienes {total_attackers}/6 atacantes principales.")
            recommendations.append("Incorpora al menos 1 o 2 atacantes con alta presión ofensiva inmediata (ej. Urshifu, Flutter Mane, Chien-Pao, Chi-Yu o Raging Bolt) con Choice item, Life Orb o Booster Energy.")
            score_mod -= 14
        elif total_attackers == 2:
            dmg_title = "¿Te falta daño?: AL LÍMITE (2 Atacantes)"
            dmg_status = "WARNING"
            dmg_desc = (
                "Cuentas con 2 atacantes principales. Es un esquema jugable si tus apoyos desgastan bien, "
                "pero la pérdida prematura de uno de ellos te dejará con muy poco margen para conseguir noqueos."
            )
            warnings.append("Profundidad de daño al límite en Dúos (2 atacantes): perder un atacante compromete seriamente tu victoria.")
            recommendations.append("Valora dotar de un movimiento de cobertura ofensiva o mayor inversión en Ataque/SpA a alguno de tus tanques.")
            score_mod -= 5
        elif total_attackers in {3, 4, 5}:
            dmg_title = "¿Te falta daño?: NO, POTENCIA OFENSIVA ÓPTIMA"
            dmg_status = "OPTIMAL"
            dmg_desc = (
                f"Excelente profundidad ofensiva ({total_attackers} atacantes). "
                "Tienes múltiples opciones para presionar al rival y castigar errores de posicionamiento."
            )
            strengths.append(f"Potencia ofensiva bien calibrada para Dúos ({total_attackers} atacantes con pegada sólida).")
        else:
            if total_tanks == 0:
                dmg_title = "¿Te falta daño?: NO, PERO ES HIPEROFENSIVO FRÁGIL"
                dmg_status = "WARNING"
                dmg_desc = (
                    f"Tienes {total_attackers} atacantes y 0 tanques. Todo tu equipo es 'Glass Cannon': "
                    "tienes mucho daño pero eres extremadamente vulnerable ante ataques en área o Trick Room."
                )
            else:
                dmg_title = "¿Te falta daño?: NO, ALTA PRESIÓN OFENSIVA"
                dmg_status = "OPTIMAL"
                dmg_desc = f"Alta concentración de daño ({total_attackers} atacantes con gran pegada)."

        # 2. ¿Te faltan tanques?
        if total_tanks == 0:
            tank_title = "¿Te faltan tanques?: SÍ, FALTA DE TANQUES CRÍTICA"
            tank_status = "CRITICAL"
            tank_desc = (
                "No tienes ningún Pokémon con bulk defensivo, intimidación o redirección para absorber golpes. "
                "Los ataques de área del rival (Make It Rain, Bleakwind Storm, Earthquake, Rock Slide) "
                "o ataques dobles coordinados desmantelarán tu equipo sin que puedas pivotar."
            )
            warnings.append("Falta total de tanques o pivotes defensivos en Dúos (0 tanques en el equipo).")
            recommendations.append("Añade al menos un tanque o pivote con utilidad defensiva (ej. Incineroar con Intimidate/Fake Out, Amoonguss con Redirección/Espora, o Rillaboom con Assault Vest) para absorber daño.")
            score_mod -= 14
        elif pure_tanks >= 3 or (pure_tanks >= 2 and total_attackers <= 2):
            tank_title = "¿Te faltan tanques?: EXCESO DE TANQUES PASIVOS (DEMASIADO PASIVO)"
            tank_status = "WARNING"
            tank_desc = (
                f"Tienes {pure_tanks} tanques/soportes puramente pasivos. En Dúos tener tantos tanques sin pegada vuelve al equipo excesivamente pasivo: "
                "el rival ignorará a tus Pokémon pasivos y noqueará rápidamente a tus pocos atacantes."
            )
            warnings.append("Exceso de tanques pasivos en Dúos (equipo demasiado pasivo): te costará noquear Pokémon rivales antes de que ellos se posicionen.")
            recommendations.append("Sustituye uno o dos de tus tanques pasivos por atacantes con mayor impacto inmediato o atacantes bulky.")
            score_mod -= 8
        else:
            tank_title = "¿Te faltan tanques?: NO, PRESENCIA DEFENSIVA ÓPTIMA"
            tank_status = "OPTIMAL"
            tank_desc = (
                f"Excelente equilibrio defensivo ({total_tanks} tanques/bulky pivots). "
                "Cuentas con la resistencia necesaria para absorber ataques rivales y permitir rotaciones seguras."
            )
            strengths.append(f"Sólida presencia defensiva en Dúos ({total_tanks} tanques/bulky pivots para absorber golpes).")

        all_moves = {mv.name.lower() for m in team for mv in m.moves}
        if total_attackers >= 5 and total_tanks == 0:
            archetype = "Hyper Offense VGC (Glass Cannon)"
        elif pure_tanks >= 3 and total_attackers <= 2:
            archetype = "Stall / Demasiado Pasivo (Riesgoso en VGC)"
        elif "trick room" in all_moves:
            archetype = "Trick Room Core VGC"
        elif "tailwind" in all_moves and total_attackers >= 3:
            archetype = "Tailwind Offense VGC"
        else:
            archetype = "Balance VGC (Equilibrado Oficial)"

        report = FormatCompositionReport(
            team_format=team_format,
            archetype_label=archetype,
            damage_dealers_count=total_attackers,
            tanks_count=total_tanks,
            supports_count=supports_count,
            damage_verdict_title=dmg_title,
            damage_verdict_status=dmg_status,
            damage_verdict_desc=dmg_desc,
            tank_verdict_title=tank_title,
            tank_verdict_status=tank_status,
            tank_verdict_desc=tank_desc,
            role_assignments=roles,
        )
        return report, score_mod

    else:
        # ==========================
        # AUDITORÍA PARA 6v6 SINGLES
        # ==========================
        wb_count = sum(1 for r in roles if r.role_tag == "WALLBREAKER")
        sw_count = sum(1 for r in roles if r.role_tag == "SWEEPER")
        phys_w_count = sum(1 for r in roles if r.role_tag == "PHYSICAL_WALL")
        spec_w_count = sum(1 for r in roles if r.role_tag == "SPECIAL_WALL")
        piv_count = sum(1 for r in roles if r.role_tag == "PIVOT" or (r.is_support and any(mv.name.lower() in PIVOT_MOVES for mv in team[roles.index(r)].moves)))
        hz_count = sum(1 for m in team if any(mv.name.lower() in HAZARD_SET_MOVES for mv in m.moves))

        total_offensive = wb_count + sw_count + sum(1 for r in roles if r.is_damage_dealer and r.role_tag not in {"WALLBREAKER", "SWEEPER"})
        total_walls = phys_w_count + spec_w_count + sum(1 for r in roles if r.is_tank and r.role_tag not in {"PHYSICAL_WALL", "SPECIAL_WALL"})

        # 1. ¿Te falta daño / Wallbreakers?
        if (wb_count + sw_count) <= 1:
            dmg_title = "¿Te falta daño / Wallbreakers?: SÍ, FALTA DE DAÑO EN 6v6"
            dmg_status = "CRITICAL"
            dmg_desc = (
                f"Solo tienes {wb_count + sw_count} Wallbreaker/Sweeper dedicado. "
                "En 6v6 los combates duran 20 a 50+ turnos y te enfrentarás a murallas como Blissey, Ting-Lu, Dondozo o Corviknight. "
                "Sin atacantes con Choice Band/Specs o boosteos de Swords Dance/Nasty Plot, tus golpes serán absorbidos "
                "y curados con Roost/Slack Off, dejándote totalmente atascado y vulnerable al desgaste (Stall)."
            )
            warnings.append("Falta de Wallbreakers en 6v6: no tienes suficiente pegada para derribar murallas defensivas rivales.")
            recommendations.append("Incorpora al menos 1 o 2 Wallbreakers dedicados (ej. Great Tusk, Iron Valiant, Kingambit, Gholdengo, Kyurem) con Choice Band/Specs o movimientos de boosteo.")
            score_mod -= 14
        elif (wb_count + sw_count) in {2, 3, 4}:
            dmg_title = "¿Te falta daño / Wallbreakers?: NO, PODER DE RUPTURA ÓPTIMO"
            dmg_status = "OPTIMAL"
            dmg_desc = (
                f"Excelente potencia ofensiva ({wb_count} Wallbreakers / {sw_count} Sweepers). "
                "Tienes las herramientas necesarias para presionar a núcleos defensivos y rematar partidas."
            )
            strengths.append(f"Capacidad de Wallbreaking y limpieza sobresaliente para 6v6 ({wb_count + sw_count} atacantes clave).")
        else:
            dmg_title = "¿Te falta daño / Wallbreakers?: NO, HIPEROFENSIVO PURO"
            dmg_status = "OPTIMAL"
            dmg_desc = f"Alta presión ofensiva continua ({wb_count + sw_count} atacantes)."

        # 2. ¿Te faltan murallas / tanques?
        if phys_w_count == 0 and spec_w_count == 0 and total_walls <= 1:
            tank_title = "¿Te faltan murallas / tanques?: SÍ, SIN COLUMNA DEFENSIVA EN 6v6"
            tank_status = "CRITICAL"
            tank_desc = (
                "No dispones de ninguna muralla física ni especial dedicada. "
                "En 6v6 hay continuos cambios de Pokémon: sin murallas donde apoyarte, "
                "cada vez que el rival fuerce un cambio o entre con ventaja, perderás un Pokémon en el turno de entrada."
            )
            warnings.append("Sin columna defensiva (Murallas) en 6v6: careces de switch-ins seguros para absorber daño en los cambios.")
            recommendations.append("Incorpora una columna defensiva mixta: una muralla física (ej. Great Tusk, Corviknight, Dondozo, Gliscor) y una especial (ej. Clodsire, Ting-Lu, Blissey, Slowking-Galar).")
            score_mod -= 14
        elif phys_w_count == 0 and spec_w_count == 0:
            tank_title = "¿Te faltan murallas / tanques?: AVISO, SIN MURALLAS PURAS DEDICADAS"
            tank_status = "WARNING"
            tank_desc = (
                f"Tienes {total_walls} Pokémon con resistencia o pivoteo, pero careces de murallas defensivas puras "
                "con recuperación (como Corviknight, Ting-Lu, Clodsire o Dondozo) para soportar el desgaste en partidas largas de 6v6."
            )
            warnings.append("Sin muralla pura dedicada en 6v6 (ni física ni especial): alta exigencia y desgaste en tus rotaciones.")
            recommendations.append("Incorpora al menos una muralla pura física o especial con movimiento de recuperación (Roost, Slack Off, Recover).")
            score_mod -= 6
        elif phys_w_count == 0:
            tank_title = "¿Te faltan murallas / tanques?: AVISO, SIN MURALLA FÍSICA DEDICADA"
            tank_status = "WARNING"
            tank_desc = (
                "Tienes presencia defensiva pero careces de una Muralla Física dedicada. "
                "Atacantes físicos contundentes como Great Tusk, Dragonite, Roaring Moon o Kingambit "
                "podrán entrar y golpear sin que tengas un escudo seguro con el que frenarlos."
            )
            warnings.append("Sin muralla física dedicada en 6v6: alta vulnerabilidad ante amenazas ofensivas físicas.")
            recommendations.append("Añade una muralla con alta Defensa física y recuperación o intimidación (ej. Corviknight con Roost, Dondozo, o Skarmory).")
            score_mod -= 6
        elif spec_w_count == 0:
            tank_title = "¿Te faltan murallas / tanques?: AVISO, SIN MURALLA ESPECIAL DEDICADA"
            tank_status = "WARNING"
            tank_desc = (
                "Tienes presencia defensiva pero careces de una Muralla Especial dedicada. "
                "Atacantes especiales como Gholdengo, Walking Wake, Darkrai o Dragapult "
                "te causarán graves problemas al no disponer de una esponja con la que absorber sus ataques."
            )
            warnings.append("Sin muralla especial dedicada en 6v6: alta vulnerabilidad ante atacantes especiales rivales.")
            recommendations.append("Añade una muralla con alta Defensa Especial o Assault Vest (ej. Ting-Lu, Clodsire con Unaware, o Blissey/Slowking-Galar).")
            score_mod -= 6
        else:
            tank_title = "¿Te faltan murallas / tanques?: NO, COLUMNA DEFENSIVA COMPLETA"
            tank_status = "OPTIMAL"
            tank_desc = (
                f"Excelente base defensiva ({phys_w_count} Murallas Físicas / {spec_w_count} Murallas Especiales). "
                "Dispones de respuestas sólidas para rotar de forma segura ante ambos tipos de atacantes."
            )
            strengths.append(f"Columna defensiva mixta completa para 6v6 ({phys_w_count} físicas / {spec_w_count} especiales).")

        if total_offensive >= 5 and total_walls == 0:
            archetype = "6v6 Hyper Offense (HO)"
        elif total_walls >= 4 and total_offensive <= 1:
            archetype = "6v6 Stall / Muy Pasivo"
        elif total_walls >= 2 and total_offensive >= 2 and (piv_count >= 1 or hz_count >= 1):
            archetype = "6v6 Bulky Offense / Balance Competitivo"
        elif total_walls >= 2:
            archetype = "6v6 Balance Tradicional"
        else:
            archetype = "6v6 Offense Estándar"

        report = FormatCompositionReport(
            team_format=team_format,
            archetype_label=archetype,
            damage_dealers_count=total_offensive,
            tanks_count=total_walls,
            supports_count=piv_count + hz_count,
            wallbreakers_count=wb_count,
            sweepers_count=sw_count,
            physical_walls_count=phys_w_count,
            special_walls_count=spec_w_count,
            pivots_count=piv_count,
            hazard_controllers_count=hz_count,
            damage_verdict_title=dmg_title,
            damage_verdict_status=dmg_status,
            damage_verdict_desc=dmg_desc,
            tank_verdict_title=tank_title,
            tank_verdict_status=tank_status,
            tank_verdict_desc=tank_desc,
            role_assignments=roles,
        )
        return report, score_mod


def analyze_team(team: list[PokemonState], team_format: TeamFormat = TeamFormat.DOUBLES) -> TeamAnalysisReport:
    """
    Evalúa matemáticamente la sinergia defensiva, cobertura ofensiva, control de velocidad,
    eficiencia de EVs/Naturalezas y herramientas del formato (Dúos/VGC vs 6v6 Singles).
    """
    defensive_matrix: dict[PokemonType, TypeDefenseSummary] = {}

    for atk_type in CORE_TYPES:
        summary = TypeDefenseSummary(attacking_type=atk_type)
        dummy_attacker = PokemonState(
            pokemon=resolve_pokemon("Dragonite"),
            level=50,
        )
        dummy_move = Move(name="Test", type=atk_type, category=MoveCategory.PHYSICAL, base_power=80)

        for member in team:
            mult = get_type_effectiveness(dummy_attacker, member, dummy_move, atk_type)
            summary.per_member_multiplier.append(mult)
            if mult == 0.0:
                summary.immune_count += 1
            elif mult < 1.0:
                summary.resist_count += 1
            elif mult > 1.0:
                summary.weak_count += 1

        defensive_matrix[atk_type] = summary

    # Cobertura ofensiva (qué tipos golpea en supereficaz al menos un movimiento de daño del equipo)
    covered_types: set[PokemonType] = set()
    phys_count = 0
    spec_count = 0

    for member in team:
        has_phys = False
        has_spec = False
        for mv in member.moves:
            if mv.category == MoveCategory.STATUS or mv.base_power == 0:
                continue
            if mv.category == MoveCategory.PHYSICAL:
                has_phys = True
            elif mv.category == MoveCategory.SPECIAL:
                has_spec = True

            eff_type, _ = get_effective_move_type(member, mv)
            for def_type in CORE_TYPES:
                dummy_def = PokemonState(
                    pokemon=resolve_pokemon("Dragonite", custom_types=def_type.value),
                    level=50,
                )
                eff = get_type_effectiveness(member, dummy_def, mv, eff_type)
                if eff > 1.0:
                    covered_types.add(def_type)

        if has_phys:
            phys_count += 1
        if has_spec:
            spec_count += 1

    uncovered = [t for t in CORE_TYPES if t not in covered_types]

    # Speed Tiers
    speed_tiers: list[tuple[str, int, str]] = []
    for member in team:
        stats = calculate_all_stats(member)
        spe_val = stats[StatName.SPE]
        mod = member.nature.get_modifier(StatName.SPE)
        sign = "+" if mod > 1.0 else ("-" if mod < 1.0 else "")
        speed_tiers.append((member.pokemon.name, spe_val, f"{member.evs.spe} EVs ({member.nature.value}{sign})"))
    speed_tiers.sort(key=lambda x: x[1], reverse=True)

    # Inicializar listas de diagnóstico
    score = 100
    strengths: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    # Auditoría Física vs Especial (Defensa vs Defensa Especial real a Nivel 50)
    total_def = 0
    total_spd = 0
    phys_fragile: list[tuple[str, int, int]] = []
    spec_fragile: list[tuple[str, int, int]] = []

    for member in team:
        m_stats = calculate_all_stats(member)
        hp_v = m_stats[StatName.HP]
        def_v = m_stats[StatName.DEF]
        spd_v = m_stats[StatName.SPD]

        # Considerar si el Pokémon lleva Assault Vest (x1.5 SpD) o Eviolite (x1.5 Def y SpD)
        it_norm = (member.item or "").strip().lower()
        eff_def = def_v
        eff_spd = spd_v
        if it_norm == "assault vest":
            eff_spd = int(eff_spd * 1.5)
        elif it_norm == "eviolite":
            eff_def = int(eff_def * 1.5)
            eff_spd = int(eff_spd * 1.5)

        # Si tiene habilidad Fur Coat (x2 Def) o Ice Scales (x2 bulk especial)
        ab_norm = (member.ability or "").strip().lower()
        if ab_norm == "fur coat":
            eff_def *= 2
        elif ab_norm == "ice scales":
            eff_spd *= 2

        total_def += eff_def
        total_spd += eff_spd

        disp_n = member.nickname if member.nickname else member.pokemon.name
        # Umbral de fragilidad a nivel 50 (Bulk < 100 de stat o producto HP*Def < 14000)
        if eff_def < 100 or (hp_v * eff_def < 14000):
            phys_fragile.append((disp_n, hp_v, eff_def))
        if eff_spd < 100 or (hp_v * eff_spd < 14000):
            spec_fragile.append((disp_n, hp_v, eff_spd))

    n_members = max(1, len(team))
    avg_def = round(total_def / n_members, 1)
    avg_spd = round(total_spd / n_members, 1)
    diff_pct = round(((avg_spd - avg_def) / max(1.0, avg_def)) * 100, 1)

    if diff_pct >= 12.0:
        bulk_verdict = "MÁS VULNERABLE A ATACANTES FÍSICOS"
        warnings.append(
            f"Desequilibrio defensivo físico/especial: la defensa física media del equipo ({avg_def}) es un {abs(diff_pct)}% inferior a la especial ({avg_spd})."
        )
        recommendations.append(
            f"El equipo sufre más frente a Atacantes Físicos (ej. Urshifu, Chien-Pao, Dragonite, Great Tusk). Considera potenciar la Def física de los miembros más frágiles: {', '.join(p[0] for p in phys_fragile)} o añadir Intimidate / Will-O-Wisp / Reflect."
        )
        score -= 6
    elif diff_pct <= -12.0:
        bulk_verdict = "MÁS VULNERABLE A ATACANTES ESPECIALES"
        warnings.append(
            f"Desequilibrio defensivo físico/especial: la defensa especial media del equipo ({avg_spd}) es un {abs(diff_pct)}% inferior a la física ({avg_def})."
        )
        recommendations.append(
            f"El equipo sufre más frente a Atacantes Especiales (ej. Flutter Mane, Chi-Yu, Miraidon, Bloodmoon Ursaluna). Considera equipar un Assault Vest, aumentar SpD en los miembros frágiles: {', '.join(p[0] for p in spec_fragile)} o añadir Light Screen / Snarl."
        )
        score -= 6
    else:
        bulk_verdict = "EQUILIBRADO ENTRE FÍSICO Y ESPECIAL"
        strengths.append(
            f"Excelente balance defensivo mixto: el equipo resiste de forma pareja tanto a atacantes Físicos (Def media: {avg_def}) como Especiales (SpD media: {avg_spd})."
        )

    # Ranking de Tipos más débiles y más resistidos
    weakness_ranking: list[tuple[PokemonType, int, int]] = []
    resistance_ranking: list[tuple[PokemonType, int]] = []
    for t, summ in defensive_matrix.items():
        if summ.weak_count > 0:
            weakness_ranking.append((t, summ.weak_count, summ.resist_count + summ.immune_count))
        if (summ.resist_count + summ.immune_count) > 0:
            resistance_ranking.append((t, summ.resist_count + summ.immune_count))

    # Ordenar tipos débiles por mayor cantidad de débiles y menor cantidad de resistencias
    weakness_ranking.sort(key=lambda x: (x[1], -x[2]), reverse=True)
    resistance_ranking.sort(key=lambda x: x[1], reverse=True)

    # 1. Revisión de agujeros defensivos (Tipos donde >=3 miembros son débiles o hay >=2 débiles sin ninguna resistencia/inmunidad)
    severe_weaknesses: list[PokemonType] = []
    unresisted_types: list[PokemonType] = []
    great_immunities: list[PokemonType] = []

    for t, summ in defensive_matrix.items():
        if summ.immune_count >= 1 and summ.resist_count >= 1 and summ.weak_count <= 1:
            great_immunities.append(t)
        if summ.weak_count >= 3:
            severe_weaknesses.append(t)
            score -= 10
        elif summ.weak_count >= 2 and (summ.resist_count + summ.immune_count) == 0:
            unresisted_types.append(t)
            score -= 7

    if great_immunities:
        names = ", ".join(t.value for t in great_immunities[:5])
        strengths.append(f"Excelente sinergia defensiva e inmunidades frente a: {names}.")

    if severe_weaknesses:
        names = ", ".join(t.value for t in severe_weaknesses)
        warnings.append(f"Vulnerabilidad acumulativa grave (3+ Pokémon débiles) a: {names}.")
        recommendations.append(
            f"Cambia el Tera Type de al menos un miembro o incorpora una resistencia/inmunidad (ej. Levitate/Earth Eater/Well-Baked Body) contra {names}."
        )

    if unresisted_types:
        names = ", ".join(t.value for t in unresisted_types)
        warnings.append(f"Sin ningún switch-in seguro (2+ débiles y 0 resistencias) ante ataques de tipo: {names}.")
        recommendations.append(f"Añade un pivote defensivo que resista {names} para no perder momentum al cambiar.")

    # 2. Equilibrio Físico / Especial
    if phys_count == 0 or spec_count == 0:
        score -= 15
        missing_cat = "Físicos" if phys_count == 0 else "Especiales"
        warnings.append(f"Equipo 100% unidimensional: no tienes atacantes {missing_cat}.")
        recommendations.append(f"Incluye al menos 1 o 2 atacantes {missing_cat} para no ser bloqueado por murallas como Blissey o Dondozo.")
    else:
        strengths.append(f"Buen balance de daño mixto ({phys_count} perfiles Físicos / {spec_count} perfiles Especiales).")

    # 3. Cobertura ofensiva
    if len(covered_types) >= 15:
        strengths.append(f"Cobertura ofensiva sobresaliente: golpeas supereficaz a {len(covered_types)}/18 tipos.")
    elif len(covered_types) < 12:
        score -= 8
        miss_str = ", ".join(t.value for t in uncovered[:6])
        warnings.append(f"Cobertura ofensiva limitada ({len(covered_types)}/18 tipos). Tipos sin respuesta supereficaz: {miss_str}.")
        recommendations.append(f"Valora añadir movimientos de cobertura (como Ground, Ice, Fighting o Fairy) para amenazar a {miss_str}.")

    # 4. Auditoría matemática de EVs y Naturalezas miembro por miembro
    for member in team:
        rem = member.evs.remaining_evs
        if rem >= 8:
            score -= 4
            warnings.append(f"{member.pokemon.name} tiene {rem} EVs sin asignar (Total actual: {member.evs.total}/508).")
            recommendations.append(
                f"Usa el optimizador de PokeStat con `{member.pokemon.name}` para invertir esos {rem} EVs libres en Bulk o Velocidad."
            )
        # Detectar EVs desperdiciados a Nivel 50 (múltiplos de 4 que son divisibles por 8 y no son 0)
        if member.level == 50:
            wasted_stats = []
            for st in StatName:
                ev_val = member.evs.get(st)
                if ev_val > 0 and (ev_val - 4) % 8 != 0:
                    wasted_stats.append(f"{ev_val} {st.value.upper()}")
            if wasted_stats:
                score -= 3
                warnings.append(
                    f"{member.pokemon.name} desperdicia EVs a Nivel 50 en: {', '.join(wasted_stats)} (a Nvl 50 los puntos suben en 4, 12, 20, 28... 252)."
                )
                recommendations.append(
                    f"Ajusta los EVs de {member.pokemon.name} a la secuencia 4 + 8k (ej. 4, 12, 20... 244, 252) para ganar hasta 1 stat extra gratis."
                )
        if member.nature.get_modifier(StatName.ATK) == 1.0 and member.nature.get_modifier(StatName.DEF) == 1.0 and member.nature in {
            Nature.SERIOUS, Nature.HARDY, Nature.DOCILE, Nature.BASHFUL, Nature.QUIRKY
        }:
            score -= 3
            warnings.append(f"{member.pokemon.name} lleva naturaleza Neutra ({member.nature.value}), perdiendo un +10% gratuito en su mejor stat.")
            recommendations.append(f"Cambia la naturaleza de {member.pokemon.name} a una favorable (ej. Bold, Impish, Adamant, Modest, Timid o Jolly).")

    # 5. Reglas específicas según Formato: DÚOS (VGC/Dobles) vs 6v6 (Singles)
    all_move_names = {mv.name.strip().lower() for m in team for mv in m.moves}
    all_abilities = {(m.ability or "").strip().lower() for m in team}
    all_items = [m.item.strip().lower() for m in team if m.item]

    if team_format == TeamFormat.DOUBLES:
        # Regla de Objetos Únicos (Item Clause en VGC)
        seen_items: set[str] = set()
        dup_items: set[str] = set()
        for it in all_items:
            if it in seen_items:
                dup_items.add(it)
            seen_items.add(it)
        if dup_items:
            score -= 8
            warnings.append(f"Item Clause vulnerada en Dúos/VGC: objetos repetidos ({', '.join(dup_items)}).")
            recommendations.append("Asigna objetos distintos a cada Pokémon para cumplir la normativa oficial de VGC.")

        # Protect / Detect / Spiky Shield
        protect_users = sum(
            1 for m in team if any(mv.name.lower() in {"protect", "detect", "spiky shield", "baneful bunker", "wide guard"} for mv in m.moves)
        )
        if protect_users < 2:
            score -= 10
            warnings.append(f"Muy poca protección para Dúos ({protect_users}/{len(team)} Pokémon con Protect/Detect).")
            recommendations.append("En formato Dúos/VGC, añade Protect al menos a 3-4 Pokémon para reposicionarte y desgastar turnos de Tailwind/Trick Room.")
        else:
            strengths.append(f"Sólida presencia de Protect en Dúos ({protect_users}/{len(team)} miembros con protección).")

        # Speed Control (Tailwind, Trick Room, Icy Wind, Electroweb, Thunder Wave)
        speed_control_moves = {"tailwind", "trick room", "icy wind", "electroweb", "thunder wave", "glare", "bulldoze"}
        if not (all_move_names & speed_control_moves):
            score -= 8
            warnings.append("Ausencia de control de velocidad para Dúos (sin Tailwind, Trick Room, Icy Wind ni Thunder Wave).")
            recommendations.append("Incorpora Icy Wind, Tailwind o Trick Room para controlar el orden de turno en Dúos.")
        else:
            sc_found = ", ".join(sorted(all_move_names & speed_control_moves))
            strengths.append(f"Control de velocidad activo para Dúos ({sc_found.title()}).")

        # Disrupción / Intimidate / Fake Out / Redirección
        support_tools = (all_move_names & {"fake out", "rage powder", "follow me", "parting shot", "taunt", "spore", "helping hand"}) | (
            all_abilities & {"intimidate", "friend guard", "regenerator", "prankster"}
        )
        if not support_tools:
            score -= 6
            warnings.append("Falta de soporte táctico en Dúos (sin Fake Out, Intimidate ni redirección Follow Me / Rage Powder).")
            recommendations.append("Añade un usuario de Fake Out o Intimidate (como Incineroar o Rillaboom) para facilitar el posicionamiento de tus compañeros.")
        else:
            strengths.append(f"Herramientas de soporte en Dúos detectadas: {', '.join(sorted(t.title() for t in support_tools))}.")

    else:
        # Formato 6v6 Singles
        hazard_moves = {"stealth rock", "spikes", "toxic spikes", "sticky web", "ceaseless edge", "stone axe"}
        removal_moves = {"rapid spin", "defog", "mortal spin", "tidy up", "court change"}
        pivot_moves = {"u-turn", "volt switch", "flip turn", "parting shot", "chilly reception", "teleport"}
        setup_moves = {"swords dance", "nasty plot", "dragon dance", "calm mind", "bulk up", "quiver dance", "iron defense"}

        if not (all_move_names & hazard_moves):
            score -= 8
            warnings.append("Sin Entry Hazards para 6v6 (no llevas Stealth Rock, Spikes ni Sticky Web).")
            recommendations.append("En 6v6 los cambios son constantes: añade Stealth Rock o Spikes en uno de tus tanques para castigar las rotaciones rivales.")
        else:
            strengths.append(f"Presión de Entry Hazards activa para 6v6 ({', '.join(all_move_names & hazard_moves).title()}).")

        if not (all_move_names & removal_moves) and "heavy-duty boots" not in all_items:
            score -= 7
            warnings.append("Sin control de Hazards rivales en 6v6 (sin Rapid Spin, Defog ni Heavy-Duty Boots).")
            recommendations.append("Añade Rapid Spin / Defog o equipa Heavy-Duty Boots a tus Pokémon débiles a Roca.")

        if not (all_move_names & pivot_moves):
            score -= 5
            warnings.append("Sin movimientos de pivoteo (U-turn, Volt Switch, Flip Turn, Parting Shot) para mantener iniciativa en 6v6.")
            recommendations.append("Incluye U-turn o Volt Switch en al menos un miembro para ganar ventaja en los cambios.")
        else:
            strengths.append(f"Rotación fluida en 6v6 con movimientos de pivote ({', '.join(all_move_names & pivot_moves).title()}).")

        if all_move_names & setup_moves:
            strengths.append(f"Condición de victoria (Win-Condition) de Setup presente ({', '.join(all_move_names & setup_moves).title()}).")

    # 6. Clasificación de roles miembro por miembro y auditoría de composición (Daño vs Tanques vs Soporte)
    roles: list[MemberRoleInfo] = [classify_member_role(m, team_format) for m in team]
    comp_report, comp_score_mod = audit_format_composition(
        team=team,
        roles=roles,
        team_format=team_format,
        warnings=warnings,
        recommendations=recommendations,
        strengths=strengths,
    )
    score += comp_score_mod

    score = max(15, min(100, score))
    if score >= 85:
        verdict = "EXCELENTE / COMPETITIVAMENTE EQUILIBRADO"
    elif score >= 70:
        verdict = "SÓLIDO CON MARGEN DE OPTIMIZACIÓN"
    elif score >= 50:
        verdict = "DESEQUILIBRADO — REQUIERE AJUSTES TÁCTICOS"
    else:
        verdict = "CRÍTICO — ALTA VULNERABILIDAD ESTRUCTURAL"

    return TeamAnalysisReport(
        team=team,
        team_format=team_format,
        balance_score=score,
        verdict_label=verdict,
        defensive_matrix=defensive_matrix,
        top_weakness_types=weakness_ranking,
        top_resistance_types=resistance_ranking,
        offensive_super_effective_coverage=covered_types,
        uncovered_offensive_types=uncovered,
        speed_tiers=speed_tiers,
        physical_attackers=phys_count,
        special_attackers=spec_count,
        avg_team_def=avg_def,
        avg_team_spd=avg_spd,
        physically_fragile_members=phys_fragile,
        specially_fragile_members=spec_fragile,
        bulk_orientation_verdict=bulk_verdict,
        bulk_differential_pct=diff_pct,
        strengths=strengths,
        warnings=warnings,
        recommendations=recommendations,
        composition=comp_report,
    )
