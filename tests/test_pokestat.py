from pokestat.calculator import calculate_hp, calculate_non_hp_stat
from pokestat.catalog import resolve_move, resolve_pokemon
from pokestat.damage_engine import calculate_damage
from pokestat.models import BattleField, Nature, PokemonState, PokemonType, StatSpread
from pokestat.optimizer import SurvivalTarget, optimize_defense
from pokestat.team_analyzer import TeamFormat, analyze_team, load_team_from_file


def test_level_50_stat_calculation():
    # Flutter Mane Base 55 HP / 55 Def / 135 SpA
    assert calculate_hp(base=55, iv=31, ev=0, level=50) == 130
    assert calculate_hp(base=55, iv=31, ev=4, level=50) == 131
    assert calculate_hp(base=55, iv=31, ev=252, level=50) == 162

    # 55 Base Def: 0 EV Neutral = 75, 252 EV Bold (1.1) = floor(107 * 1.1) = 117
    assert calculate_non_hp_stat(base=55, iv=31, ev=0, nature_modifier=1.0, level=50) == 75
    assert calculate_non_hp_stat(base=55, iv=31, ev=252, nature_modifier=1.1, level=50) == 117


def test_stab_and_protean_and_adaptability():
    dusk_poke = resolve_pokemon("Dragonite")
    def_poke = resolve_pokemon("Flutter Mane")
    eq = resolve_move("Earthquake")

    # 1. Sin STAB (Dragonite es Dragon/Flying usando Ground)
    atk_no_stab = PokemonState(pokemon=dusk_poke, nature=Nature.ADAMANT, evs=StatSpread(atk=252))
    defender = PokemonState(pokemon=def_poke, nature=Nature.SERIOUS)
    dmg_no_stab = calculate_damage(atk_no_stab, defender, eq)

    # 2. Con Protean / Libero en Randomlocke -> Gana STAB 1.5x en Earthquake
    atk_protean = atk_no_stab.model_copy(update={"ability": "Protean"})
    dmg_protean = calculate_damage(atk_protean, defender, eq)
    assert dmg_protean.max_damage > dmg_no_stab.max_damage

    # 3. Con Tera Ground + Adaptability -> STAB 2.0x
    atk_tera_adapt = atk_no_stab.model_copy(
        update={"ability": "Adaptability", "tera_type": PokemonType.GROUND, "is_terastallized": True}
    )
    dmg_adapt = calculate_damage(atk_tera_adapt, defender, eq)
    assert dmg_adapt.max_damage > dmg_protean.max_damage


def test_randomlocke_defensive_abilities_and_mold_breaker():
    atk_poke = resolve_pokemon("Dragonite")
    def_poke = resolve_pokemon("Flutter Mane")
    eq = resolve_move("Earthquake")

    attacker = PokemonState(pokemon=atk_poke, nature=Nature.ADAMANT, evs=StatSpread(atk=252), item="Choice Band")

    # Defensor con Levitate en Randomlocke -> 0 daño de Earthquake
    def_levitate = PokemonState(pokemon=def_poke, ability="Levitate")
    res_lev = calculate_damage(attacker, def_levitate, eq)
    assert res_lev.max_damage == 0
    assert res_lev.survives_guaranteed is True

    # Si el atacante tiene Mold Breaker -> Ignora Levitate y hace daño completo
    atk_mb = attacker.model_copy(update={"ability": "Mold Breaker"})
    res_mb = calculate_damage(atk_mb, def_levitate, eq)
    assert res_mb.max_damage > 0

    # Fur Coat duplica la defensa física del defensor
    def_normal = PokemonState(pokemon=def_poke)
    def_fur = PokemonState(pokemon=def_poke, ability="Fur Coat")
    assert calculate_damage(attacker, def_fur, eq).max_damage < calculate_damage(attacker, def_normal, eq).max_damage


def test_optimizer_finds_minimum_ev_spread():
    atk_poke = resolve_pokemon("Dragonite")
    def_poke = resolve_pokemon("Flutter Mane")
    eq = resolve_move("Earthquake")

    attacker = PokemonState(
        pokemon=atk_poke,
        nature=Nature.ADAMANT,
        evs=StatSpread(atk=252),
        item="Choice Band",
    )
    defender = PokemonState(pokemon=def_poke)

    report = optimize_defense(
        attacker=attacker,
        defender=defender,
        move=eq,
        target=SurvivalTarget.SURVIVE_1_HIT,
        field=BattleField(is_doubles=False),
    )
    assert report.best_overall is not None
    assert report.best_overall.damage_result.max_damage < report.best_overall.final_hp
    # Verifica que es múltiplo válido a nivel 50 (0 o 4 + 8k)
    assert report.best_overall.hp_evs == 0 or (report.best_overall.hp_evs - 4) % 8 == 0
    assert report.best_overall.def_evs == 0 or (report.best_overall.def_evs - 4) % 8 == 0


def test_team_loader_and_analyzer_duos_vs_6v6():
    team = load_team_from_file("team_example.txt")
    assert len(team) == 6
    assert team[0].pokemon.name == "Flutter Mane"
    assert len(team[0].moves) == 4

    rep_duos = analyze_team(team, TeamFormat.DOUBLES)
    rep_6v6 = analyze_team(team, TeamFormat.SINGLES)

    # Este equipo está diseñado para VGC/Dúos (Protect, Tailwind, Fake Out), por lo que puntúa más alto en Dúos que en 6v6 (donde faltan Stealth Rock / Rapid Spin)
    assert rep_duos.balance_score > rep_6v6.balance_score
    assert len(rep_duos.speed_tiers) == 6
    assert rep_duos.composition is not None
    assert rep_duos.composition.damage_dealers_count >= 4
    assert rep_duos.composition.damage_verdict_status == "OPTIMAL"
    assert rep_duos.composition.tank_verdict_status == "OPTIMAL"

    # En 6v6 detecta que tiene atacantes pero carece de Hazards y murallas de recuperación dedicadas
    assert rep_6v6.composition is not None
    assert rep_6v6.composition.wallbreakers_count >= 2
    assert rep_6v6.composition.pivots_count >= 2


def test_lack_of_damage_detected_in_duos():
    blissey = PokemonState(
        pokemon=resolve_pokemon("Blissey"),
        nature=Nature.BOLD,
        moves=[resolve_move("Soft-Boiled"), resolve_move("Protect")],
        item="Leftovers",
    )
    amoonguss = PokemonState(
        pokemon=resolve_pokemon("Amoonguss"),
        nature=Nature.CALM,
        moves=[resolve_move("Spore"), resolve_move("Rage Powder"), resolve_move("Protect")],
        item="Sitrus Berry",
    )
    clefairy = PokemonState(
        pokemon=resolve_pokemon("Clefairy"),
        nature=Nature.BOLD,
        moves=[resolve_move("Follow Me"), resolve_move("Helping Hand"), resolve_move("Protect")],
        item="Eviolite",
    )
    dusclops = PokemonState(
        pokemon=resolve_pokemon("Dusclops"),
        nature=Nature.RELAXED,
        moves=[resolve_move("Trick Room"), resolve_move("Will-O-Wisp"), resolve_move("Pain Split")],
        item="Eviolite",
    )
    passive_team = [blissey, amoonguss, clefairy, dusclops]
    rep = analyze_team(passive_team, TeamFormat.DOUBLES)

    assert rep.composition is not None
    assert rep.composition.damage_verdict_status == "CRITICAL"
    assert "falta de daño" in rep.composition.damage_verdict_title.lower()


def test_lack_of_tanks_detected_in_duos():
    flutter = PokemonState(
        pokemon=resolve_pokemon("Flutter Mane"),
        nature=Nature.TIMID,
        moves=[resolve_move("Moonblast"), resolve_move("Shadow Ball")],
        item="Booster Energy",
        evs=StatSpread(spa=252, spe=252),
    )
    chien_pao = PokemonState(
        pokemon=resolve_pokemon("Chien-Pao"),
        nature=Nature.JOLLY,
        moves=[resolve_move("Icicle Crash"), resolve_move("Sucker Punch")],
        item="Focus Sash",
        evs=StatSpread(atk=252, spe=252),
    )
    greninja = PokemonState(
        pokemon=resolve_pokemon("Greninja"),
        nature=Nature.TIMID,
        moves=[resolve_move("Hydro Pump"), resolve_move("Dark Pulse")],
        item="Life Orb",
        evs=StatSpread(spa=252, spe=252),
    )
    fragile_team = [flutter, chien_pao, greninja]
    rep = analyze_team(fragile_team, TeamFormat.DOUBLES)

    assert rep.composition is not None
    assert rep.composition.tank_verdict_status == "CRITICAL"
    assert "falta de tanques" in rep.composition.tank_verdict_title.lower()

