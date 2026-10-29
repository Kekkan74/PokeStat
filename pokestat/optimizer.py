from dataclasses import dataclass
from enum import Enum
from pokestat.calculator import calculate_all_stats
from pokestat.damage_engine import DamageResult, calculate_damage
from pokestat.models import (
    BattleField,
    Move,
    MoveCategory,
    Nature,
    PokemonState,
    StatName,
    StatSpread,
)


class SurvivalTarget(str, Enum):
    """Objetivos de supervivencia soportados por el optimizador."""
    SURVIVE_1_HIT = "survive-1-hit"   # Evitar OHKO (Daño_Máximo < HP_Total)
    SURVIVE_2_HITS = "survive-2-hits" # Evitar 2HKO (2 * Daño_Máximo < HP_Total)
    SURVIVE_3_HITS = "survive-3-hits" # Evitar 3HKO (3 * Daño_Máximo < HP_Total)

    @property
    def hits_to_survive(self) -> int:
        if self == SurvivalTarget.SURVIVE_1_HIT:
            return 1
        if self == SurvivalTarget.SURVIVE_2_HITS:
            return 2
        return 3


@dataclass(frozen=True)
class OptimizationCandidate:
    """Representa una solución válida (Naturaleza + EVs defensivos) y sus métricas."""
    nature: Nature
    hp_evs: int
    def_stat_name: StatName
    def_evs: int
    total_defensive_evs: int
    remaining_evs: int
    final_hp: int
    final_def_stat: int
    damage_result: DamageResult
    hits_survived: int
    uses_boosting_nature: bool

    @property
    def max_total_damage(self) -> int:
        return self.damage_result.max_damage * self.hits_survived

    @property
    def hp_remaining_after_hits(self) -> int:
        return self.final_hp - self.max_total_damage

    @property
    def bulk_product(self) -> int:
        """Producto HP * Defensa Efectiva (medida de Bulk general)."""
        return self.final_hp * self.final_def_stat


@dataclass(frozen=True)
class OptimizationReport:
    """Informe completo devuelto por el optimizador."""
    best_overall: OptimizationCandidate | None
    best_neutral_nature: OptimizationCandidate | None
    best_boosting_nature: OptimizationCandidate | None
    top_alternatives: list[OptimizationCandidate]
    worst_case_with_max_investment: OptimizationCandidate
    target: SurvivalTarget
    defensive_stat_used: StatName


def get_valid_ev_breakpoints(level: int = 50) -> list[int]:
    """
    Devuelve los valores de EVs que realmente incrementan un punto de stat
    para no desperdiciar EVs.
    - A Nivel 50 (con 31 IVs): 0, 4, 12, 20, 28, ..., 252 (33 valores).
    - A otros niveles: todos los múltiplos de 4 de 0 a 252 (64 valores).
    """
    if level == 50:
        return [0] + list(range(4, 253, 8))
    return list(range(0, 253, 4))


def get_relevant_defensive_stat(move: Move) -> StatName:
    """
    Determina qué estadística defensiva mitiga el movimiento (Defensa o Defensa Especial),
    respetando movimientos como Psyshock / Psystrike / Secret Sword.
    """
    if move.override_defensive_stat:
        return move.override_defensive_stat
    return StatName.DEF if move.category == MoveCategory.PHYSICAL else StatName.SPD


def get_candidate_natures(
    def_stat: StatName,
    preferred_penalty_stat: StatName | None = None,
) -> tuple[Nature, Nature]:
    """
    Devuelve (naturaleza_neutra, naturaleza_positiva_defensiva) para el stat defensivo.
    Por defecto:
      - Para DEF: Bold (+Def, -Atk) o Impish (+Def, -SpA) según preferred_penalty_stat.
      - Para SPD: Calm (+SpD, -Atk) o Careful (+SpD, -SpA).
    """
    neutral = Nature.SERIOUS
    if def_stat == StatName.DEF:
        boosting = Nature.IMPISH if preferred_penalty_stat == StatName.SPA else Nature.BOLD
    else:
        boosting = Nature.CAREFUL if preferred_penalty_stat == StatName.SPA else Nature.CALM
    return neutral, boosting


def _build_defender_state(
    base_defender: PokemonState,
    nature: Nature,
    hp_evs: int,
    def_stat: StatName,
    def_evs: int,
) -> PokemonState:
    """Crea una copia inmutable del defensor con los EVs y Naturaleza indicados."""
    ev_dict = {
        "hp": hp_evs,
        "atk": base_defender.evs.atk,
        "def": def_evs if def_stat == StatName.DEF else base_defender.evs.def_,
        "spa": base_defender.evs.spa,
        "spd": def_evs if def_stat == StatName.SPD else base_defender.evs.spd,
        "spe": base_defender.evs.spe,
    }
    return base_defender.model_copy(
        update={
            "nature": nature,
            "evs": StatSpread(**ev_dict),
        }
    )


def optimize_defense(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    target: SurvivalTarget = SurvivalTarget.SURVIVE_1_HIT,
    field: BattleField | None = None,
    preferred_penalty_stat: StatName | None = None,
) -> OptimizationReport:
    """
    Resuelve el problema de optimización matemática:
        Minimizar (EV_HP + EV_DEF)
        sujeto a: (Daño_Máximo * N_Golpes) < HP_Total
                  EV_HP + EV_DEF + EV_Otros <= 508

    En caso de empate en EVs totales gastados:
      1. Prioriza naturaleza neutra si logra el mismo gasto de EVs (deja libre la naturaleza para velocidad/ataque).
      2. Prioriza mayor porcentaje de vida restante tras el golpe.
      3. Prioriza mayor Bulk general (HP * Defensa).
    """
    if field is None:
        field = BattleField()

    def_stat = get_relevant_defensive_stat(move)
    neutral_nature, boosting_nature = get_candidate_natures(def_stat, preferred_penalty_stat)
    ev_steps = get_valid_ev_breakpoints(defender.level)
    hits = target.hits_to_survive

    valid_candidates: list[OptimizationCandidate] = []

    for uses_boost, nature in ((False, neutral_nature), (True, boosting_nature)):
        for hp_ev in ev_steps:
            for def_ev in ev_steps:
                if hp_ev + def_ev > 508:
                    continue

                cand_state = _build_defender_state(defender, nature, hp_ev, def_stat, def_ev)
                dmg = calculate_damage(attacker, cand_state, move, field)

                # Si estamos evaluando 2HKO y el defensor tiene Multiscale / Shadow Shield al 100% HP,
                # el primer golpe hace la mitad pero el segundo golpe es sin Multiscale:
                if hits > 1 and cand_state.is_full_hp and (cand_state.ability or "").strip().lower() in {"multiscale", "shadow shield"}:
                    no_ms_state = cand_state.model_copy(update={"is_full_hp": False})
                    dmg_subsequent = calculate_damage(attacker, no_ms_state, move, field)
                    total_max_dmg = dmg.max_damage + dmg_subsequent.max_damage * (hits - 1)
                else:
                    total_max_dmg = dmg.max_damage * hits

                if total_max_dmg < dmg.defender_hp:
                    stats = calculate_all_stats(cand_state)
                    total_evs = hp_ev + def_ev
                    valid_candidates.append(
                        OptimizationCandidate(
                            nature=nature,
                            hp_evs=hp_ev,
                            def_stat_name=def_stat,
                            def_evs=def_ev,
                            total_defensive_evs=total_evs,
                            remaining_evs=508 - total_evs,
                            final_hp=stats[StatName.HP],
                            final_def_stat=stats[def_stat],
                            damage_result=dmg,
                            hits_survived=hits,
                            uses_boosting_nature=uses_boost,
                        )
                    )

    # Ordenación multicriterio matemática:
    # 1º Menor suma de EVs (hp_evs + def_evs)
    # 2º Naturaleza neutra antes que naturaleza defensiva a igualdad de EVs
    # 3º Mayor HP restante tras recibir los golpes
    # 4º Mayor Bulk general (HP * Def)
    valid_candidates.sort(
        key=lambda c: (
            c.total_defensive_evs,
            c.uses_boosting_nature,
            -c.hp_remaining_after_hits,
            -c.bulk_product,
        )
    )

    neutral_candidates = [c for c in valid_candidates if not c.uses_boosting_nature]
    boosting_candidates = [c for c in valid_candidates if c.uses_boosting_nature]

    # Calculamos el caso de máxima inversión (252 HP / 252 Def+) por si es imposible sobrevivir
    max_state = _build_defender_state(defender, boosting_nature, 252, def_stat, 252)
    max_dmg = calculate_damage(attacker, max_state, move, field)
    max_stats = calculate_all_stats(max_state)
    worst_case_max_bulk = OptimizationCandidate(
        nature=boosting_nature,
        hp_evs=252,
        def_stat_name=def_stat,
        def_evs=252,
        total_defensive_evs=504,
        remaining_evs=4,
        final_hp=max_stats[StatName.HP],
        final_def_stat=max_stats[def_stat],
        damage_result=max_dmg,
        hits_survived=hits,
        uses_boosting_nature=True,
    )

    # Seleccionamos hasta 5 alternativas distintas (sin repetir el mismo total con peor bulk)
    top_alternatives = valid_candidates[:6]

    return OptimizationReport(
        best_overall=valid_candidates[0] if valid_candidates else None,
        best_neutral_nature=neutral_candidates[0] if neutral_candidates else None,
        best_boosting_nature=boosting_candidates[0] if boosting_candidates else None,
        top_alternatives=top_alternatives,
        worst_case_with_max_investment=worst_case_max_bulk,
        target=target,
        defensive_stat_used=def_stat,
    )
