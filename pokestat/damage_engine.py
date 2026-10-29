import math
from dataclasses import dataclass
from pokestat.calculator import calculate_all_stats
from pokestat.models import (
    BattleField,
    Move,
    MoveCategory,
    PokemonState,
    PokemonType,
    StatName,
    Terrain,
    Weather,
)


# ============================================================================
# 1. ARITMÉTICA DE PUNTO FIJO GEN 9 (Escala 4096)
# ============================================================================

def poke_round(value: float) -> int:
    """
    Redondeo oficial de Game Freak ("round half down"):
    Si la parte decimal es exactamente <= 0.5, redondea hacia abajo (floor).
    Si es > 0.5, redondea hacia arriba (ceil).
    """
    if value - math.floor(value) <= 0.5:
        return math.floor(value)
    return math.ceil(value)


def chain_mod(current_mod: int, new_mod: int) -> int:
    """
    Encadena dos modificadores en base 4096 según el motor de Gen 5-9:
        M_final = floor((M1 * M2 + 2048) / 4096)
    """
    return (current_mod * new_mod + 2048) >> 12


def apply_mod(value: int, mod: int) -> int:
    """
    Aplica un modificador en base 4096 a un valor entero usando poke_round.
    """
    return poke_round((value * mod) / 4096)


# ============================================================================
# 2. TABLA DE EFECTIVIDAD DE TIPOS (Gen 9)
# ============================================================================

_TYPE_CHART: dict[PokemonType, dict[PokemonType, float]] = {
    PokemonType.NORMAL: {PokemonType.ROCK: 0.5, PokemonType.GHOST: 0.0, PokemonType.STEEL: 0.5},
    PokemonType.FIRE: {
        PokemonType.FIRE: 0.5, PokemonType.WATER: 0.5, PokemonType.GRASS: 2.0,
        PokemonType.ICE: 2.0, PokemonType.BUG: 2.0, PokemonType.ROCK: 0.5,
        PokemonType.DRAGON: 0.5, PokemonType.STEEL: 2.0,
    },
    PokemonType.WATER: {
        PokemonType.FIRE: 2.0, PokemonType.WATER: 0.5, PokemonType.GRASS: 0.5,
        PokemonType.GROUND: 2.0, PokemonType.ROCK: 2.0, PokemonType.DRAGON: 0.5,
    },
    PokemonType.ELECTRIC: {
        PokemonType.WATER: 2.0, PokemonType.ELECTRIC: 0.5, PokemonType.GRASS: 0.5,
        PokemonType.GROUND: 0.0, PokemonType.FLYING: 2.0, PokemonType.DRAGON: 0.5,
    },
    PokemonType.GRASS: {
        PokemonType.FIRE: 0.5, PokemonType.WATER: 2.0, PokemonType.GRASS: 0.5,
        PokemonType.POISON: 0.5, PokemonType.GROUND: 2.0, PokemonType.FLYING: 0.5,
        PokemonType.BUG: 0.5, PokemonType.ROCK: 2.0, PokemonType.DRAGON: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.ICE: {
        PokemonType.FIRE: 0.5, PokemonType.WATER: 0.5, PokemonType.GRASS: 2.0,
        PokemonType.ICE: 0.5, PokemonType.GROUND: 2.0, PokemonType.FLYING: 2.0,
        PokemonType.DRAGON: 2.0, PokemonType.STEEL: 0.5,
    },
    PokemonType.FIGHTING: {
        PokemonType.NORMAL: 2.0, PokemonType.ICE: 2.0, PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5, PokemonType.PSYCHIC: 0.5, PokemonType.BUG: 0.5,
        PokemonType.ROCK: 2.0, PokemonType.GHOST: 0.0, PokemonType.DARK: 2.0,
        PokemonType.STEEL: 2.0, PokemonType.FAIRY: 0.5,
    },
    PokemonType.POISON: {
        PokemonType.GRASS: 2.0, PokemonType.POISON: 0.5, PokemonType.GROUND: 0.5,
        PokemonType.ROCK: 0.5, PokemonType.GHOST: 0.5, PokemonType.STEEL: 0.0,
        PokemonType.FAIRY: 2.0,
    },
    PokemonType.GROUND: {
        PokemonType.FIRE: 2.0, PokemonType.ELECTRIC: 2.0, PokemonType.GRASS: 0.5,
        PokemonType.POISON: 2.0, PokemonType.FLYING: 0.0, PokemonType.BUG: 0.5,
        PokemonType.ROCK: 2.0, PokemonType.STEEL: 2.0,
    },
    PokemonType.FLYING: {
        PokemonType.ELECTRIC: 0.5, PokemonType.GRASS: 2.0, PokemonType.FIGHTING: 2.0,
        PokemonType.BUG: 2.0, PokemonType.ROCK: 0.5, PokemonType.STEEL: 0.5,
    },
    PokemonType.PSYCHIC: {
        PokemonType.FIGHTING: 2.0, PokemonType.POISON: 2.0, PokemonType.PSYCHIC: 0.5,
        PokemonType.DARK: 0.0, PokemonType.STEEL: 0.5,
    },
    PokemonType.BUG: {
        PokemonType.FIRE: 0.5, PokemonType.GRASS: 2.0, PokemonType.FIGHTING: 0.5,
        PokemonType.POISON: 0.5, PokemonType.FLYING: 0.5, PokemonType.PSYCHIC: 2.0,
        PokemonType.GHOST: 0.5, PokemonType.DARK: 2.0, PokemonType.STEEL: 0.5,
        PokemonType.FAIRY: 0.5,
    },
    PokemonType.ROCK: {
        PokemonType.FIRE: 2.0, PokemonType.ICE: 2.0, PokemonType.FIGHTING: 0.5,
        PokemonType.GROUND: 0.5, PokemonType.FLYING: 2.0, PokemonType.BUG: 2.0,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.GHOST: {
        PokemonType.NORMAL: 0.0, PokemonType.PSYCHIC: 2.0, PokemonType.GHOST: 2.0,
        PokemonType.DARK: 0.5,
    },
    PokemonType.DRAGON: {
        PokemonType.DRAGON: 2.0, PokemonType.STEEL: 0.5, PokemonType.FAIRY: 0.0,
    },
    PokemonType.DARK: {
        PokemonType.FIGHTING: 0.5, PokemonType.PSYCHIC: 2.0, PokemonType.GHOST: 2.0,
        PokemonType.DARK: 0.5, PokemonType.FAIRY: 0.5,
    },
    PokemonType.STEEL: {
        PokemonType.FIRE: 0.5, PokemonType.WATER: 0.5, PokemonType.ELECTRIC: 0.5,
        PokemonType.ICE: 2.0, PokemonType.ROCK: 2.0, PokemonType.STEEL: 0.5,
        PokemonType.FAIRY: 2.0,
    },
    PokemonType.FAIRY: {
        PokemonType.FIRE: 0.5, PokemonType.FIGHTING: 2.0, PokemonType.POISON: 0.5,
        PokemonType.DRAGON: 2.0, PokemonType.DARK: 2.0, PokemonType.STEEL: 0.5,
    },
    PokemonType.STELLAR: {},
}

# Habilidades que ignoran habilidades defensivas ignorables (Mold Breaker, Teravolt, Turboblaze, etc.)
MOLD_BREAKER_ABILITIES = {
    "mold breaker",
    "teravolt",
    "turboblaze",
    "mycelium might",
}

# Movimientos que ignoran habilidades defensivas ignorables
MOLD_BREAKER_MOVES = {
    "moongeist beam",
    "sunsteel strike",
    "photon geyser",
    "searing sunraze smash",
    "menacing moonraze maelstrom",
    "light that burns the sky",
    "g-max drum solo",
    "g-max fireball",
    "g-max hydrosnipe",
}

# Habilidades de tipo "-ate" (cambian movimientos Normal a otro tipo y dan x1.2 BP en Gen 7-9)
ATE_ABILITIES: dict[str, PokemonType] = {
    "pixilate": PokemonType.FAIRY,
    "aerilate": PokemonType.FLYING,
    "refrigerate": PokemonType.ICE,
    "galvanize": PokemonType.ELECTRIC,
}

# Habilidades de inmunidad elemental a tipos de movimiento (ignorables por Mold Breaker)
IMMUNITY_ABILITIES: dict[str, set[PokemonType]] = {
    "levitate": {PokemonType.GROUND},
    "earth eater": {PokemonType.GROUND},
    "volt absorb": {PokemonType.ELECTRIC},
    "lightning rod": {PokemonType.ELECTRIC},
    "motor drive": {PokemonType.ELECTRIC},
    "water absorb": {PokemonType.WATER},
    "storm drain": {PokemonType.WATER},
    "dry skin": {PokemonType.WATER},
    "flash fire": {PokemonType.FIRE},
    "well-baked body": {PokemonType.FIRE},
    "sap sipper": {PokemonType.GRASS},
}


def _norm(text: str | None) -> str:
    """Normaliza nombres de habilidades, objetos o movimientos (minúsculas y sin espacios extra)."""
    return (text or "").strip().lower()


def is_defender_ability_ignored(attacker: PokemonState, defender: PokemonState, move: Move) -> bool:
    """
    Determina si la habilidad del defensor es ignorada por Rompemoldes (Mold Breaker)
    o movimientos equivalentes. Nota: Shadow Shield, Full Metal Body y Prism Armor
    NUNCA pueden ser ignoradas.
    """
    def_ability = _norm(defender.ability)
    if def_ability in {"shadow shield", "prism armor", "full metal body"}:
        return False

    atk_ability = _norm(attacker.ability)
    move_name = _norm(move.name)
    if _norm(defender.item) == "ability shield":
        return False

    return atk_ability in MOLD_BREAKER_ABILITIES or move_name in MOLD_BREAKER_MOVES


def get_effective_move_type(attacker: PokemonState, move: Move) -> tuple[PokemonType, bool]:
    """
    Devuelve (tipo_efectivo_del_movimiento, activó_habilidad_cambio_tipo).
    Soporta Randomlocke donde cualquier Pokémon puede tener Pixilate, Normalize, Liquid Voice, etc.
    """
    atk_ability = _norm(attacker.ability)
    move_type = move.type

    if atk_ability == "normalize":
        return PokemonType.NORMAL, True

    if atk_ability == "liquid voice" and move.is_sound:
        return PokemonType.WATER, False

    if move_type == PokemonType.NORMAL and atk_ability in ATE_ABILITIES:
        return ATE_ABILITIES[atk_ability], True

    return move_type, False


def get_defender_active_types(defender: PokemonState) -> list[PokemonType]:
    """Devuelve los tipos defensivos activos (teniendo en cuenta Teracristalización)."""
    if defender.is_terastallized and defender.tera_type and defender.tera_type != PokemonType.STELLAR:
        return [defender.tera_type]
    return defender.pokemon.types


def get_type_effectiveness(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    effective_move_type: PokemonType,
) -> float:
    """
    Calcula el multiplicador total de efectividad de tipos (0, 0.25, 0.5, 1, 2, 4),
    incluyendo inmunidades por habilidad (Levitate, Volt Absorb, Wonder Guard, etc.)
    y Scrappy / Mind's Eye.
    """
    atk_ability = _norm(attacker.ability)
    def_ability = _norm(defender.ability) if not is_defender_ability_ignored(attacker, defender, move) else ""

    # 1. Inmunidades por habilidad defensiva
    if def_ability in IMMUNITY_ABILITIES and effective_move_type in IMMUNITY_ABILITIES[def_ability]:
        return 0.0
    if def_ability == "bulletproof" and move.is_pulse:
        return 0.0
    if def_ability == "soundproof" and move.is_sound:
        return 0.0

    # 2. Movimiento Stellar contra Pokémon Teracristalizado
    if effective_move_type == PokemonType.STELLAR:
        return 2.0 if defender.is_terastallized else 1.0

    # 3. Efectividad en tabla de tipos
    def_types = get_defender_active_types(defender)
    multiplier = 1.0
    chart_row = _TYPE_CHART.get(effective_move_type, {})

    for d_type in def_types:
        eff = chart_row.get(d_type, 1.0)
        # Scrappy / Mind's Eye permiten que Normal y Fighting golpeen neutro a Ghost
        if (
            d_type == PokemonType.GHOST
            and eff == 0.0
            and effective_move_type in {PokemonType.NORMAL, PokemonType.FIGHTING}
            and atk_ability in {"scrappy", "mind's eye"}
        ):
            eff = 1.0
        multiplier *= eff

    # 4. Wonder Guard (Superguarda) - muy relevante en Randomlockes
    if def_ability == "wonder guard" and multiplier <= 1.0:
        return 0.0

    return multiplier


def apply_stat_boost(stat_value: int, stage: int) -> int:
    """Aplica los niveles de boost (-6 a +6) con floor exacto."""
    stage = max(-6, min(6, stage))
    if stage >= 0:
        return math.floor(stat_value * (2 + stage) / 2)
    return math.floor(stat_value * 2 / (2 - stage))


# ============================================================================
# 3. CÁLCULO DE BASE POWER, ATAQUE, DEFENSA Y MODIFICADORES FINALES
# ============================================================================

def compute_effective_base_power(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    effective_move_type: PokemonType,
    ate_boost: bool,
    field: BattleField,
) -> int:
    """Calcula la Potencia Base efectiva encadenando modificadores en base 4096."""
    bp_mod = 4096
    atk_ability = _norm(attacker.ability)
    def_ability = _norm(defender.ability) if not is_defender_ability_ignored(attacker, defender, move) else ""
    atk_item = _norm(attacker.item)

    # Habilidades ofensivas que escalan BP
    if atk_ability == "technician" and move.base_power <= 60:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if (ate_boost or atk_ability == "normalize"):
        bp_mod = chain_mod(bp_mod, 4915)  # x1.2
    if atk_ability == "iron fist" and move.is_punch:
        bp_mod = chain_mod(bp_mod, 4915)  # x1.2
    if atk_ability == "strong jaw" and move.is_biting:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "sharpness" and move.is_slicing:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "mega launcher" and move.is_pulse:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "reckless" and move.is_recoil:
        bp_mod = chain_mod(bp_mod, 4915)  # x1.2
    if atk_ability == "sheer force" and move.has_secondary_effect:
        bp_mod = chain_mod(bp_mod, 5325)  # x1.3
    if atk_ability == "tough claws" and move.makes_contact:
        bp_mod = chain_mod(bp_mod, 5325)  # x1.3
    if atk_ability == "punk rock" and move.is_sound:
        bp_mod = chain_mod(bp_mod, 5325)  # x1.3
    if atk_ability == "toxic boost" and attacker.is_statused and move.category == MoveCategory.PHYSICAL:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "flare boost" and attacker.is_burned and move.category == MoveCategory.SPECIAL:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "sand force" and field.weather == Weather.SAND and effective_move_type in {
        PokemonType.ROCK, PokemonType.GROUND, PokemonType.STEEL
    }:
        bp_mod = chain_mod(bp_mod, 5325)  # x1.3
    if atk_ability == "supreme overlord":
        # Por defecto asumimos 1 aliado debilitado si no se especifica, o no aplicamos si no hay info;
        # dejaremos water bubble / steelworker / etc. que son fijos:
        pass
    if atk_ability in {"steelworker", "steely spirit"} and effective_move_type == PokemonType.STEEL:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "transistor" and effective_move_type == PokemonType.ELECTRIC:
        bp_mod = chain_mod(bp_mod, 5325)  # x1.3 (Gen 9 nerf: 1.3x)
    if atk_ability == "dragon's maw" and effective_move_type == PokemonType.DRAGON:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "rocky payload" and effective_move_type == PokemonType.ROCK:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5
    if atk_ability == "water bubble" and effective_move_type == PokemonType.WATER:
        bp_mod = chain_mod(bp_mod, 8192)  # x2.0

    # Habilidades defensivas que modifican la BP recibida
    if def_ability == "dry skin" and effective_move_type == PokemonType.FIRE:
        bp_mod = chain_mod(bp_mod, 5120)  # x1.25
    if def_ability == "heatproof" and effective_move_type == PokemonType.FIRE:
        bp_mod = chain_mod(bp_mod, 2048)  # x0.5

    # Helping Hand
    if field.is_helping_hand:
        bp_mod = chain_mod(bp_mod, 6144)  # x1.5

    # Objetos que potencian BP
    if atk_item == "muscle band" and move.category == MoveCategory.PHYSICAL:
        bp_mod = chain_mod(bp_mod, 4505)  # x1.1
    elif atk_item == "wise glasses" and move.category == MoveCategory.SPECIAL:
        bp_mod = chain_mod(bp_mod, 4505)  # x1.1
    elif atk_item == "punching glove" and move.is_punch:
        bp_mod = chain_mod(bp_mod, 4506)  # x1.1
    elif atk_item in {
        "charcoal", "mystic water", "magnet", "miracle seed", "never-melt ice",
        "black belt", "poison barb", "soft sand", "sharp beak", "twisted spoon",
        "silver powder", "hard stone", "spell tag", "dragon fang", "black glasses",
        "metal coat", "fairy feather", "silk scarf",
    }:
        bp_mod = chain_mod(bp_mod, 4915)  # x1.2

    # Terrenos (Gen 8-9: x1.3 = 5325/4096)
    if field.terrain == Terrain.ELECTRIC and effective_move_type == PokemonType.ELECTRIC:
        bp_mod = chain_mod(bp_mod, 5325)
    elif field.terrain == Terrain.GRASSY and effective_move_type == PokemonType.GRASS:
        bp_mod = chain_mod(bp_mod, 5325)
    elif field.terrain == Terrain.PSYCHIC and effective_move_type == PokemonType.PSYCHIC:
        bp_mod = chain_mod(bp_mod, 5325)
    elif field.terrain == Terrain.MISTY and effective_move_type == PokemonType.DRAGON:
        bp_mod = chain_mod(bp_mod, 2048)  # x0.5

    # Grassy Terrain debilita Earthquake, Bulldoze y Magnitude a la mitad
    if field.terrain == Terrain.GRASSY and _norm(move.name) in {"earthquake", "bulldoze", "magnitude"}:
        bp_mod = chain_mod(bp_mod, 2048)

    effective_bp = max(1, apply_mod(move.base_power, bp_mod))

    # Regla Tera 60 BP de Gen 9 (si el movimiento coincide con el Tera Type y no tiene prioridad/multi-hit)
    if (
        attacker.is_terastallized
        and attacker.tera_type == effective_move_type
        and effective_bp < 60
    ):
        effective_bp = 60

    return effective_bp


def compute_effective_attack(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    effective_move_type: PokemonType,
    field: BattleField,
) -> int:
    """Calcula el stat de Ataque (o Ataque Especial) efectivo en combate."""
    atk_stats = calculate_all_stats(attacker)
    def_stats = calculate_all_stats(defender)

    # Foul Play usa el Ataque del defensor; Body Press usa la Defensa del atacante
    if _norm(move.name) == "foul play":
        stat_key = StatName.ATK
        raw_atk = def_stats[stat_key]
        boost = defender.stat_boosts.get(stat_key, 0)
    else:
        if move.override_offensive_stat:
            stat_key = move.override_offensive_stat
        else:
            stat_key = StatName.ATK if move.category == MoveCategory.PHYSICAL else StatName.SPA
        raw_atk = atk_stats[stat_key]
        boost = attacker.stat_boosts.get(stat_key, 0)

    atk_ability = _norm(attacker.ability)
    def_ability = _norm(defender.ability) if not is_defender_ability_ignored(attacker, defender, move) else ""

    # Unaware (Ignorante) en el defensor ignora boosts ofensivos del atacante
    if def_ability == "unaware":
        boost = 0

    atk = apply_stat_boost(raw_atk, boost)

    # Hustle (Entusiasmo) se aplica directamente como x1.5 con floor antes de la cadena 4096
    if atk_ability == "hustle" and move.category == MoveCategory.PHYSICAL:
        atk = math.floor(atk * 3 / 2)

    atk_mod = 4096

    # Habilidades ofensivas que multiplican el stat de Ataque / SpA
    if atk_ability in {"huge power", "pure power"} and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 8192)  # x2.0
    if atk_ability == "guts" and attacker.is_statused and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 6144)  # x1.5
    if atk_ability == "gorilla tactics" and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 6144)  # x1.5
    if atk_ability == "orichalcum pulse" and field.weather in {Weather.SUN, Weather.HARSH_SUNSHINE} and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 5461)  # ~x1.3333
    if atk_ability == "hadron engine" and field.terrain == Terrain.ELECTRIC and move.category == MoveCategory.SPECIAL:
        atk_mod = chain_mod(atk_mod, 5461)  # ~x1.3333
    if atk_ability == "solar power" and field.weather in {Weather.SUN, Weather.HARSH_SUNSHINE} and move.category == MoveCategory.SPECIAL:
        atk_mod = chain_mod(atk_mod, 6144)  # x1.5
    if atk_ability in {"Defeatist".lower(), "slow start"} and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 2048)  # x0.5

    # Habilidades defensivas que reducen el Ataque/SpA del atacante en la fórmula (Thick Fat, Purifying Salt, Ruin)
    if def_ability == "thick fat" and effective_move_type in {PokemonType.FIRE, PokemonType.ICE}:
        atk_mod = chain_mod(atk_mod, 2048)  # x0.5
    if def_ability == "purifying salt" and effective_move_type == PokemonType.GHOST:
        atk_mod = chain_mod(atk_mod, 2048)  # x0.5
    if def_ability == "water bubble" and effective_move_type == PokemonType.FIRE:
        atk_mod = chain_mod(atk_mod, 2048)  # x0.5

    # Ruin Abilities que bajan el Ataque o Ataque Especial (Tablets of Ruin / Vessel of Ruin)
    if move.category == MoveCategory.PHYSICAL:
        if (field.tablets_of_ruin or def_ability == "tablets of ruin") and atk_ability != "tablets of ruin":
            atk_mod = chain_mod(atk_mod, 3072)  # x0.75
    elif move.category == MoveCategory.SPECIAL:
        if (field.vessel_of_ruin or def_ability == "vessel of ruin") and atk_ability != "vessel of ruin":
            atk_mod = chain_mod(atk_mod, 3072)  # x0.75

    # Objetos ofensivos (Choice Band, Choice Specs, Light Ball, Thick Club)
    atk_item = _norm(attacker.item)
    if atk_item == "choice band" and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 6144)  # x1.5
    elif atk_item == "choice specs" and move.category == MoveCategory.SPECIAL:
        atk_mod = chain_mod(atk_mod, 6144)  # x1.5
    elif atk_item == "light ball" and _norm(attacker.pokemon.name) == "pikachu":
        atk_mod = chain_mod(atk_mod, 8192)  # x2.0
    elif atk_item == "thick club" and _norm(attacker.pokemon.name) in {"cubone", "marowak", "marowak-alola"} and move.category == MoveCategory.PHYSICAL:
        atk_mod = chain_mod(atk_mod, 8192)  # x2.0

    return max(1, apply_mod(atk, atk_mod))


def compute_effective_defense(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    field: BattleField,
) -> int:
    """Calcula el stat de Defensa (o Defensa Especial) efectivo del defensor."""
    def_stats = calculate_all_stats(defender)

    if move.override_defensive_stat:
        stat_key = move.override_defensive_stat
    else:
        stat_key = StatName.DEF if move.category == MoveCategory.PHYSICAL else StatName.SPD

    raw_def = def_stats[stat_key]
    boost = defender.stat_boosts.get(stat_key, 0)

    atk_ability = _norm(attacker.ability)
    def_ability = _norm(defender.ability) if not is_defender_ability_ignored(attacker, defender, move) else ""

    # Unaware en el atacante o Sacred Sword / Darkest Lariat ignoran boosts defensivos
    if atk_ability == "unaware" or _norm(move.name) in {"sacred sword", "darkest lariat", "chip away"}:
        boost = 0

    defense = apply_stat_boost(raw_def, boost)

    # Clima que multiplica directamente la defensa (Sandstorm +50% SpD a Rock; Snow +50% Def a Ice en Gen 9)
    def_types = get_defender_active_types(defender)
    if field.weather == Weather.SAND and PokemonType.ROCK in def_types and stat_key == StatName.SPD:
        defense = math.floor(defense * 3 / 2)
    if field.weather == Weather.SNOW and PokemonType.ICE in def_types and stat_key == StatName.DEF:
        defense = math.floor(defense * 3 / 2)

    def_mod = 4096

    # Habilidades defensivas que multiplican Def o SpD
    if def_ability == "marvel scale" and defender.is_statused and stat_key == StatName.DEF:
        def_mod = chain_mod(def_mod, 6144)  # x1.5
    if def_ability == "fur coat" and stat_key == StatName.DEF:
        def_mod = chain_mod(def_mod, 8192)  # x2.0
    if def_ability == "grass pelt" and field.terrain == Terrain.GRASSY and stat_key == StatName.DEF:
        def_mod = chain_mod(def_mod, 6144)  # x1.5
    if def_ability == "ice scales" and move.category == MoveCategory.SPECIAL:
        # Nota: Ice Scales en realidad es un modificador final de daño x0.5, lo aplicamos abajo en final_mods
        pass

    # Ruin Abilities que bajan la Defensa o Defensa Especial (Sword of Ruin / Beads of Ruin)
    if stat_key == StatName.DEF:
        if (field.sword_of_ruin or atk_ability == "sword of ruin") and def_ability != "sword of ruin":
            def_mod = chain_mod(def_mod, 3072)  # x0.75
    elif stat_key == StatName.SPD:
        if (field.beads_of_ruin or atk_ability == "beads of ruin") and def_ability != "beads of ruin":
            def_mod = chain_mod(def_mod, 3072)  # x0.75

    # Objetos defensivos (Assault Vest, Eviolite)
    def_item = _norm(defender.item)
    if def_item == "assault vest" and stat_key == StatName.SPD:
        def_mod = chain_mod(def_mod, 6144)  # x1.5
    elif def_item == "eviolite":
        def_mod = chain_mod(def_mod, 6144)  # x1.5

    return max(1, apply_mod(defense, def_mod))


# ============================================================================
# 4. MOTOR PRINCIPAL DE DAÑO (FÓRMULA COMPLETA GEN 9)
# ============================================================================

@dataclass(frozen=True)
class DamageResult:
    """Resultado detallado de la simulación de daño (16 rolls)."""
    rolls: tuple[int, ...]
    min_damage: int
    max_damage: int
    defender_hp: int
    min_percent: float
    max_percent: float
    is_ohko_guaranteed: bool
    is_ohko_possible: bool
    survives_guaranteed: bool


def calculate_damage(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    field: BattleField | None = None,
) -> DamageResult:
    """
    Ejecuta la fórmula exacta de daño de Pokémon Generación 9 paso a paso,
    incluyendo los 16 rolls aleatorios (85..100).
    """
    if field is None:
        field = BattleField()

    def_stats = calculate_all_stats(defender)
    defender_hp = def_stats[StatName.HP]

    if move.category == MoveCategory.STATUS or move.base_power == 0:
        return DamageResult(
            rolls=(0,) * 16,
            min_damage=0,
            max_damage=0,
            defender_hp=defender_hp,
            min_percent=0.0,
            max_percent=0.0,
            is_ohko_guaranteed=False,
            is_ohko_possible=False,
            survives_guaranteed=True,
        )

    effective_move_type, ate_boost = get_effective_move_type(attacker, move)
    type_eff = get_type_effectiveness(attacker, defender, move, effective_move_type)

    # Inmunidad por tipo o por habilidad (Levitate, Wonder Guard, Volt Absorb, etc.)
    if type_eff == 0.0:
        return DamageResult(
            rolls=(0,) * 16,
            min_damage=0,
            max_damage=0,
            defender_hp=defender_hp,
            min_percent=0.0,
            max_percent=0.0,
            is_ohko_guaranteed=False,
            is_ohko_possible=False,
            survives_guaranteed=True,
        )

    bp = compute_effective_base_power(attacker, defender, move, effective_move_type, ate_boost, field)
    atk = compute_effective_attack(attacker, defender, move, effective_move_type, field)
    defense = compute_effective_defense(attacker, defender, move, field)

    # Paso 1: Daño Base
    level_factor = math.floor((2 * attacker.level) / 5) + 2
    base_damage = math.floor(math.floor(level_factor * bp * atk / defense) / 50) + 2

    # Paso 2: Modificador Spread (0.75x = 3072/4096 en Dobles)
    if field.is_doubles and move.is_spread:
        base_damage = apply_mod(base_damage, 3072)

    # Paso 3: Modificador de Clima
    if field.weather in {Weather.SUN, Weather.HARSH_SUNSHINE}:
        if effective_move_type == PokemonType.FIRE:
            base_damage = apply_mod(base_damage, 6144)  # x1.5
        elif effective_move_type == PokemonType.WATER:
            if _norm(move.name) == "hydro steam":
                base_damage = apply_mod(base_damage, 6144)  # Hydro Steam sube x1.5 en Sol
            else:
                base_damage = apply_mod(base_damage, 2048)  # x0.5
    elif field.weather in {Weather.RAIN, Weather.HEAVY_RAIN}:
        if effective_move_type == PokemonType.WATER:
            base_damage = apply_mod(base_damage, 6144)  # x1.5
        elif effective_move_type == PokemonType.FIRE:
            base_damage = apply_mod(base_damage, 2048)  # x0.5

    # Paso 4: Modificador STAB (con Adaptability, Protean/Libero y Teracristalización Gen 9)
    atk_ability = _norm(attacker.ability)
    def_ability = _norm(defender.ability) if not is_defender_ability_ignored(attacker, defender, move) else ""
    orig_types = attacker.pokemon.types
    has_protean_stab = atk_ability in {"protean", "libero"} and not attacker.is_terastallized
    has_orig_stab = (effective_move_type in orig_types) or has_protean_stab
    has_tera_stab = attacker.is_terastallized and attacker.tera_type == effective_move_type

    stab_mod = 4096
    if attacker.is_terastallized and attacker.tera_type == PokemonType.STELLAR:
        stab_mod = 8192 if has_orig_stab else 4915  # 2.0x si era tipo original, 1.2x si no
    elif has_orig_stab and has_tera_stab:
        stab_mod = 9216 if atk_ability == "adaptability" else 8192  # 2.25x con Adaptability, 2.0x normal
    elif has_orig_stab or has_tera_stab:
        stab_mod = 8192 if atk_ability == "adaptability" else 6144  # 2.0x con Adaptability, 1.5x normal

    # Paso 5: Quemadura (0.5x en físicos salvo Guts o Facade)
    burn_active = (
        attacker.is_burned
        and move.category == MoveCategory.PHYSICAL
        and atk_ability != "guts"
        and _norm(move.name) != "facade"
    )

    # Paso 6: Cadena de modificadores finales (Pantallas, Multiscale, Tinted Lens, Filter, Life Orb, etc.)
    final_mod = 4096

    # Pantallas (Reflect / Light Screen / Aurora Veil) si no tiene Infiltrator
    if atk_ability != "infiltrator":
        screen_mod = 2732 if field.is_doubles else 2048
        if move.category == MoveCategory.PHYSICAL and (field.is_reflect or field.is_aurora_veil):
            final_mod = chain_mod(final_mod, screen_mod)
        elif move.category == MoveCategory.SPECIAL and (field.is_light_screen or field.is_aurora_veil):
            final_mod = chain_mod(final_mod, screen_mod)

    # Habilidades ofensivas de daño final
    if atk_ability == "neuroforce" and type_eff > 1.0:
        final_mod = chain_mod(final_mod, 5120)  # x1.25
    if atk_ability == "tinted lens" and type_eff < 1.0:
        final_mod = chain_mod(final_mod, 8192)  # x2.0

    # Habilidades defensivas de daño final
    if (def_ability == "multiscale" or _norm(defender.ability) == "shadow shield") and defender.is_full_hp:
        final_mod = chain_mod(final_mod, 2048)  # x0.5
    if def_ability == "fluffy":
        if move.makes_contact:
            final_mod = chain_mod(final_mod, 2048)  # x0.5 por contacto
        if effective_move_type == PokemonType.FIRE:
            final_mod = chain_mod(final_mod, 8192)  # x2.0 por Fuego
    if def_ability == "ice scales" and move.category == MoveCategory.SPECIAL:
        final_mod = chain_mod(final_mod, 2048)  # x0.5
    if def_ability == "punk rock" and move.is_sound:
        final_mod = chain_mod(final_mod, 2048)  # x0.5
    if (def_ability in {"filter", "solid rock"} or _norm(defender.ability) == "prism armor") and type_eff > 1.0:
        final_mod = chain_mod(final_mod, 3072)  # x0.75
    if field.is_friend_guard:
        final_mod = chain_mod(final_mod, 3072)  # x0.75

    # Objetos de modificador final (Expert Belt, Life Orb)
    atk_item = _norm(attacker.item)
    if atk_item == "expert belt" and type_eff > 1.0:
        final_mod = chain_mod(final_mod, 4915)  # x1.2
    elif atk_item == "life orb":
        final_mod = chain_mod(final_mod, 5324)  # x1.3 exacto en Showdown/Cartucho (5324/4096)

    # Paso 7: Evaluación de los 16 rolls (85 a 100)
    rolls: list[int] = []
    for r in range(85, 101):
        d = math.floor(base_damage * r / 100)
        if stab_mod != 4096:
            d = apply_mod(d, stab_mod)
        d = math.floor(d * type_eff)
        if burn_active:
            d = apply_mod(d, 2048)
        d = max(1, d)
        if final_mod != 4096:
            d = apply_mod(d, final_mod)
        rolls.append(max(1, d))

    min_dmg = rolls[0]
    max_dmg = rolls[-1]

    return DamageResult(
        rolls=tuple(rolls),
        min_damage=min_dmg,
        max_damage=max_dmg,
        defender_hp=defender_hp,
        min_percent=round((min_dmg / defender_hp) * 100, 1),
        max_percent=round((max_dmg / defender_hp) * 100, 1),
        is_ohko_guaranteed=min_dmg >= defender_hp,
        is_ohko_possible=max_dmg >= defender_hp,
        survives_guaranteed=max_dmg < defender_hp,
    )
