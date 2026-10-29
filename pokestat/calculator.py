import math
from pokestat.models import Nature, PokemonState, StatName


def calculate_hp(base: int, iv: int, ev: int, level: int = 50) -> int:
    """
    Calcula el stat final de HP a un nivel dado (50 por defecto).
    Fórmula oficial (Gen 3+):
        HP = floor(((2 * Base + IV + floor(EV / 4)) * Level) / 100) + Level + 10
    Excepción: Shedinja (Base HP == 1) siempre tiene 1 HP.
    """
    if base == 1:
        return 1

    ev_bonus = math.floor(ev / 4)
    core = math.floor(((2 * base + iv + ev_bonus) * level) / 100)
    return core + level + 10


def calculate_non_hp_stat(
    base: int,
    iv: int,
    ev: int,
    nature_modifier: float = 1.0,
    level: int = 50,
) -> int:
    """
    Calcula el valor final de un stat distinto de HP (Atk, Def, SpA, SpD, Spe).
    Fórmula oficial (Gen 3+):
        Stat = floor((floor(((2 * Base + IV + floor(EV / 4)) * Level) / 100) + 5) * Nature)

    Nota de precisión: En la aritmética entera del motor del juego, el modificador
    de naturaleza se aplica como multiplicación por 110, 100 o 90 seguida de división
    entera entre 100, evitando errores de coma flotante (ej. 100 * 1.1 = 110.00000000000001).
    """
    ev_bonus = math.floor(ev / 4)
    pre_nature = math.floor(((2 * base + iv + ev_bonus) * level) / 100) + 5

    # Convertimos el multiplicador (0.9, 1.0, 1.1) a entero porcentual exacto (90, 100, 110)
    nature_percent = round(nature_modifier * 100)
    return math.floor((pre_nature * nature_percent) / 100)


def calculate_stat(
    stat: StatName,
    base: int,
    iv: int = 31,
    ev: int = 0,
    nature: Nature = Nature.SERIOUS,
    level: int = 50,
) -> int:
    """Función unificada para calcular cualquier estadística individual."""
    if stat == StatName.HP:
        return calculate_hp(base=base, iv=iv, ev=ev, level=level)

    modifier = nature.get_modifier(stat)
    return calculate_non_hp_stat(
        base=base,
        iv=iv,
        ev=ev,
        nature_modifier=modifier,
        level=level,
    )


def calculate_all_stats(state: PokemonState) -> dict[StatName, int]:
    """Calcula el diccionario completo de estadísticas reales para un PokemonState."""
    return {
        stat: calculate_stat(
            stat=stat,
            base=state.pokemon.base_stats.get(stat),
            iv=state.ivs.get(stat),
            ev=state.evs.get(stat),
            nature=state.nature,
            level=state.level,
        )
        for stat in StatName
    }
