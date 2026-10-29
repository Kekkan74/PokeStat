from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import re
from pokestat.calculator import calculate_all_stats
from pokestat.catalog import resolve_move, resolve_pokemon
from pokestat.damage_engine import get_effective_move_type, get_type_effectiveness
from pokestat.models import (
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

    # Primera línea: "Apodo (Especie) (M) @ Objeto" o "Especie @ Objeto"
    first = lines[0]
    item = None
    if "@" in first:
        left, right = first.split("@", 1)
        item = right.strip()
    else:
        left = first.strip()

    # Limpiar indicador de género "(M)" o "(F)"
    left = re.sub(r"\s*\([MF]\)\s*$", "", left).strip()

    nickname = None
    species_name = left
    paren_match = re.match(r"^(.+?)\s*\(([^()]+)\)$", left)
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
        if low.startswith("ability:"):
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
    offensive_super_effective_coverage: set[PokemonType]
    uncovered_offensive_types: list[PokemonType]
    speed_tiers: list[tuple[str, int, str]]  # (Nombre, Spe real, Naturaleza/EVs)
    physical_attackers: int
    special_attackers: int
    strengths: list[str]
    warnings: list[str]
    recommendations: list[str]


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

    # Auditoría de Fortalezas, Alertas y Recomendaciones según Formato (6v6 vs Dúos)
    score = 100
    strengths: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

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
        offensive_super_effective_coverage=covered_types,
        uncovered_offensive_types=uncovered,
        speed_tiers=speed_tiers,
        physical_attackers=phys_count,
        special_attackers=spec_count,
        strengths=strengths,
        warnings=warnings,
        recommendations=recommendations,
    )
