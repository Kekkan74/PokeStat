from pokestat.models import BaseStat, Move, MoveCategory, Pokemon, PokemonType, StatName

# Catálogo base de especies competitivas y de uso común (ampliable o personalizable por CLI)
POKEMON_CATALOG: dict[str, Pokemon] = {
    "flutter mane": Pokemon(
        name="Flutter Mane",
        types=[PokemonType.GHOST, PokemonType.FAIRY],
        base_stats=BaseStat(hp=55, atk=55, **{"def": 55}, spa=135, spd=135, spe=135),
    ),
    "dragonite": Pokemon(
        name="Dragonite",
        types=[PokemonType.DRAGON, PokemonType.FLYING],
        base_stats=BaseStat(hp=91, atk=134, **{"def": 95}, spa=100, spd=100, spe=80),
    ),
    "urshifu-rapid-strike": Pokemon(
        name="Urshifu-Rapid-Strike",
        types=[PokemonType.FIGHTING, PokemonType.WATER],
        base_stats=BaseStat(hp=100, atk=130, **{"def": 100}, spa=63, spd=60, spe=97),
    ),
    "urshifu-single-strike": Pokemon(
        name="Urshifu-Single-Strike",
        types=[PokemonType.FIGHTING, PokemonType.DARK],
        base_stats=BaseStat(hp=100, atk=130, **{"def": 100}, spa=63, spd=60, spe=97),
    ),
    "incineroar": Pokemon(
        name="Incineroar",
        types=[PokemonType.FIRE, PokemonType.DARK],
        base_stats=BaseStat(hp=95, atk=115, **{"def": 90}, spa=80, spd=90, spe=60),
    ),
    "rillaboom": Pokemon(
        name="Rillaboom",
        types=[PokemonType.GRASS],
        base_stats=BaseStat(hp=100, atk=125, **{"def": 90}, spa=60, spd=70, spe=85),
    ),
    "chien-pao": Pokemon(
        name="Chien-Pao",
        types=[PokemonType.DARK, PokemonType.ICE],
        base_stats=BaseStat(hp=80, atk=120, **{"def": 80}, spa=90, spd=65, spe=135),
    ),
    "chi-yu": Pokemon(
        name="Chi-Yu",
        types=[PokemonType.DARK, PokemonType.FIRE],
        base_stats=BaseStat(hp=55, atk=80, **{"def": 80}, spa=135, spd=120, spe=100),
    ),
    "ting-lu": Pokemon(
        name="Ting-Lu",
        types=[PokemonType.DARK, PokemonType.GROUND],
        base_stats=BaseStat(hp=155, atk=110, **{"def": 125}, spa=55, spd=80, spe=45),
    ),
    "wo-chien": Pokemon(
        name="Wo-Chien",
        types=[PokemonType.DARK, PokemonType.GRASS],
        base_stats=BaseStat(hp=85, atk=85, **{"def": 100}, spa=95, spd=135, spe=70),
    ),
    "amoonguss": Pokemon(
        name="Amoonguss",
        types=[PokemonType.GRASS, PokemonType.POISON],
        base_stats=BaseStat(hp=114, atk=85, **{"def": 70}, spa=85, spd=80, spe=30),
    ),
    "landorus-therian": Pokemon(
        name="Landorus-Therian",
        types=[PokemonType.GROUND, PokemonType.FLYING],
        base_stats=BaseStat(hp=89, atk=145, **{"def": 90}, spa=105, spd=80, spe=91),
    ),
    "landorus": Pokemon(
        name="Landorus",
        types=[PokemonType.GROUND, PokemonType.FLYING],
        base_stats=BaseStat(hp=89, atk=125, **{"def": 90}, spa=115, spd=80, spe=101),
    ),
    "ogerpon-wellspring": Pokemon(
        name="Ogerpon-Wellspring",
        types=[PokemonType.GRASS, PokemonType.WATER],
        base_stats=BaseStat(hp=80, atk=120, **{"def": 84}, spa=60, spd=96, spe=110),
    ),
    "ogerpon-hearthflame": Pokemon(
        name="Ogerpon-Hearthflame",
        types=[PokemonType.GRASS, PokemonType.FIRE],
        base_stats=BaseStat(hp=80, atk=120, **{"def": 84}, spa=60, spd=96, spe=110),
    ),
    "raging bolt": Pokemon(
        name="Raging Bolt",
        types=[PokemonType.ELECTRIC, PokemonType.DRAGON],
        base_stats=BaseStat(hp=125, atk=73, **{"def": 91}, spa=137, spd=89, spe=75),
    ),
    "gholdengo": Pokemon(
        name="Gholdengo",
        types=[PokemonType.STEEL, PokemonType.GHOST],
        base_stats=BaseStat(hp=87, atk=60, **{"def": 95}, spa=133, spd=91, spe=84),
    ),
    "tornadus": Pokemon(
        name="Tornadus",
        types=[PokemonType.FLYING],
        base_stats=BaseStat(hp=79, atk=115, **{"def": 70}, spa=125, spd=80, spe=111),
    ),
    "kingambit": Pokemon(
        name="Kingambit",
        types=[PokemonType.DARK, PokemonType.STEEL],
        base_stats=BaseStat(hp=100, atk=135, **{"def": 120}, spa=60, spd=85, spe=50),
    ),
    "iron hands": Pokemon(
        name="Iron Hands",
        types=[PokemonType.FIGHTING, PokemonType.ELECTRIC],
        base_stats=BaseStat(hp=154, atk=140, **{"def": 108}, spa=50, spd=68, spe=50),
    ),
    "iron bundle": Pokemon(
        name="Iron Bundle",
        types=[PokemonType.ICE, PokemonType.WATER],
        base_stats=BaseStat(hp=56, atk=80, **{"def": 114}, spa=124, spd=60, spe=136),
    ),
    "ursaluna": Pokemon(
        name="Ursaluna",
        types=[PokemonType.GROUND, PokemonType.NORMAL],
        base_stats=BaseStat(hp=130, atk=140, **{"def": 105}, spa=45, spd=80, spe=50),
    ),
    "ursaluna-bloodmoon": Pokemon(
        name="Ursaluna-Bloodmoon",
        types=[PokemonType.GROUND, PokemonType.NORMAL],
        base_stats=BaseStat(hp=113, atk=70, **{"def": 120}, spa=135, spd=65, spe=52),
    ),
    "calyrex-shadow": Pokemon(
        name="Calyrex-Shadow",
        types=[PokemonType.PSYCHIC, PokemonType.GHOST],
        base_stats=BaseStat(hp=100, atk=85, **{"def": 80}, spa=165, spd=100, spe=150),
    ),
    "calyrex-ice": Pokemon(
        name="Calyrex-Ice",
        types=[PokemonType.PSYCHIC, PokemonType.ICE],
        base_stats=BaseStat(hp=100, atk=165, **{"def": 150}, spa=85, spd=130, spe=50),
    ),
    "miraidon": Pokemon(
        name="Miraidon",
        types=[PokemonType.ELECTRIC, PokemonType.DRAGON],
        base_stats=BaseStat(hp=100, atk=85, **{"def": 100}, spa=135, spd=115, spe=135),
    ),
    "koraidon": Pokemon(
        name="Koraidon",
        types=[PokemonType.FIGHTING, PokemonType.DRAGON],
        base_stats=BaseStat(hp=100, atk=135, **{"def": 115}, spa=85, spd=100, spe=135),
    ),
    "archaludon": Pokemon(
        name="Archaludon",
        types=[PokemonType.STEEL, PokemonType.DRAGON],
        base_stats=BaseStat(hp=90, atk=105, **{"def": 130}, spa=125, spd=65, spe=85),
    ),
    "pelipper": Pokemon(
        name="Pelipper",
        types=[PokemonType.WATER, PokemonType.FLYING],
        base_stats=BaseStat(hp=60, atk=50, **{"def": 100}, spa=95, spd=70, spe=65),
    ),
    "garchomp": Pokemon(
        name="Garchomp",
        types=[PokemonType.DRAGON, PokemonType.GROUND],
        base_stats=BaseStat(hp=108, atk=130, **{"def": 95}, spa=80, spd=85, spe=102),
    ),
    "tyranitar": Pokemon(
        name="Tyranitar",
        types=[PokemonType.ROCK, PokemonType.DARK],
        base_stats=BaseStat(hp=100, atk=134, **{"def": 110}, spa=95, spd=100, spe=61),
    ),
}


MOVE_CATALOG: dict[str, Move] = {
    "earthquake": Move(
        name="Earthquake",
        type=PokemonType.GROUND,
        category=MoveCategory.PHYSICAL,
        base_power=100,
        is_spread=True,
        makes_contact=False,
    ),
    "extreme speed": Move(
        name="Extreme Speed",
        type=PokemonType.NORMAL,
        category=MoveCategory.PHYSICAL,
        base_power=80,
        makes_contact=True,
    ),
    "moonblast": Move(
        name="Moonblast",
        type=PokemonType.FAIRY,
        category=MoveCategory.SPECIAL,
        base_power=95,
        has_secondary_effect=True,
    ),
    "shadow ball": Move(
        name="Shadow Ball",
        type=PokemonType.GHOST,
        category=MoveCategory.SPECIAL,
        base_power=80,
        is_pulse=True,
        has_secondary_effect=True,
    ),
    "dazzling gleam": Move(
        name="Dazzling Gleam",
        type=PokemonType.FAIRY,
        category=MoveCategory.SPECIAL,
        base_power=80,
        is_spread=True,
    ),
    "flare blitz": Move(
        name="Flare Blitz",
        type=PokemonType.FIRE,
        category=MoveCategory.PHYSICAL,
        base_power=120,
        makes_contact=True,
        is_recoil=True,
        has_secondary_effect=True,
    ),
    "wood hammer": Move(
        name="Wood Hammer",
        type=PokemonType.GRASS,
        category=MoveCategory.PHYSICAL,
        base_power=120,
        makes_contact=True,
        is_recoil=True,
    ),
    "grassy glide": Move(
        name="Grassy Glide",
        type=PokemonType.GRASS,
        category=MoveCategory.PHYSICAL,
        base_power=55,
        makes_contact=True,
    ),
    "close combat": Move(
        name="Close Combat",
        type=PokemonType.FIGHTING,
        category=MoveCategory.PHYSICAL,
        base_power=120,
        makes_contact=True,
    ),
    "wicked blow": Move(
        name="Wicked Blow",
        type=PokemonType.DARK,
        category=MoveCategory.PHYSICAL,
        base_power=75,
        makes_contact=True,
    ),
    "icicle crash": Move(
        name="Icicle Crash",
        type=PokemonType.ICE,
        category=MoveCategory.PHYSICAL,
        base_power=85,
        has_secondary_effect=True,
    ),
    "ice spinner": Move(
        name="Ice Spinner",
        type=PokemonType.ICE,
        category=MoveCategory.PHYSICAL,
        base_power=80,
        makes_contact=True,
    ),
    "sucker punch": Move(
        name="Sucker Punch",
        type=PokemonType.DARK,
        category=MoveCategory.PHYSICAL,
        base_power=70,
        makes_contact=True,
    ),
    "kowtow cleave": Move(
        name="Kowtow Cleave",
        type=PokemonType.DARK,
        category=MoveCategory.PHYSICAL,
        base_power=85,
        makes_contact=True,
        is_slicing=True,
    ),
    "heat wave": Move(
        name="Heat Wave",
        type=PokemonType.FIRE,
        category=MoveCategory.SPECIAL,
        base_power=95,
        is_spread=True,
        has_secondary_effect=True,
    ),
    "overheat": Move(
        name="Overheat",
        type=PokemonType.FIRE,
        category=MoveCategory.SPECIAL,
        base_power=130,
    ),
    "dark pulse": Move(
        name="Dark Pulse",
        type=PokemonType.DARK,
        category=MoveCategory.SPECIAL,
        base_power=80,
        is_pulse=True,
        has_secondary_effect=True,
    ),
    "make it rain": Move(
        name="Make It Rain",
        type=PokemonType.STEEL,
        category=MoveCategory.SPECIAL,
        base_power=120,
        is_spread=True,
    ),
    "astral barrage": Move(
        name="Astral Barrage",
        type=PokemonType.GHOST,
        category=MoveCategory.SPECIAL,
        base_power=120,
        is_spread=True,
    ),
    "glacial lance": Move(
        name="Glacial Lance",
        type=PokemonType.ICE,
        category=MoveCategory.PHYSICAL,
        base_power=120,
        is_spread=True,
    ),
    "blood moon": Move(
        name="Blood Moon",
        type=PokemonType.NORMAL,
        category=MoveCategory.SPECIAL,
        base_power=140,
    ),
    "hyper voice": Move(
        name="Hyper Voice",
        type=PokemonType.NORMAL,
        category=MoveCategory.SPECIAL,
        base_power=90,
        is_spread=True,
        is_sound=True,
    ),
    "thunderbolt": Move(
        name="Thunderbolt",
        type=PokemonType.ELECTRIC,
        category=MoveCategory.SPECIAL,
        base_power=90,
        has_secondary_effect=True,
    ),
    "draco meteor": Move(
        name="Draco Meteor",
        type=PokemonType.DRAGON,
        category=MoveCategory.SPECIAL,
        base_power=130,
    ),
    "psyshock": Move(
        name="Psyshock",
        type=PokemonType.PSYCHIC,
        category=MoveCategory.SPECIAL,
        base_power=80,
        override_defensive_stat=StatName.DEF,
    ),
    "body press": Move(
        name="Body Press",
        type=PokemonType.FIGHTING,
        category=MoveCategory.PHYSICAL,
        base_power=80,
        makes_contact=True,
        override_offensive_stat=StatName.DEF,
    ),
    "crunch": Move(
        name="Crunch",
        type=PokemonType.DARK,
        category=MoveCategory.PHYSICAL,
        base_power=80,
        makes_contact=True,
        is_biting=True,
        has_secondary_effect=True,
    ),
    "mach punch": Move(
        name="Mach Punch",
        type=PokemonType.FIGHTING,
        category=MoveCategory.PHYSICAL,
        base_power=40,
        makes_contact=True,
        is_punch=True,
    ),
    "iron head": Move(
        name="Iron Head",
        type=PokemonType.STEEL,
        category=MoveCategory.PHYSICAL,
        base_power=80,
        makes_contact=True,
        has_secondary_effect=True,
    ),
    "ivy cudgel-water": Move(
        name="Ivy Cudgel-Water",
        type=PokemonType.WATER,
        category=MoveCategory.PHYSICAL,
        base_power=100,
    ),
    "ivy cudgel-fire": Move(
        name="Ivy Cudgel-Fire",
        type=PokemonType.FIRE,
        category=MoveCategory.PHYSICAL,
        base_power=100,
    ),
    "protect": Move(
        name="Protect",
        type=PokemonType.NORMAL,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "spiky shield": Move(
        name="Spiky Shield",
        type=PokemonType.GRASS,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "detect": Move(
        name="Detect",
        type=PokemonType.FIGHTING,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "fake out": Move(
        name="Fake Out",
        type=PokemonType.NORMAL,
        category=MoveCategory.PHYSICAL,
        base_power=40,
        makes_contact=True,
    ),
    "parting shot": Move(
        name="Parting Shot",
        type=PokemonType.DARK,
        category=MoveCategory.STATUS,
        base_power=0,
        is_sound=True,
    ),
    "u-turn": Move(
        name="U-turn",
        type=PokemonType.BUG,
        category=MoveCategory.PHYSICAL,
        base_power=70,
        makes_contact=True,
    ),
    "volt switch": Move(
        name="Volt Switch",
        type=PokemonType.ELECTRIC,
        category=MoveCategory.SPECIAL,
        base_power=70,
    ),
    "tailwind": Move(
        name="Tailwind",
        type=PokemonType.FLYING,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "trick room": Move(
        name="Trick Room",
        type=PokemonType.PSYCHIC,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "icy wind": Move(
        name="Icy Wind",
        type=PokemonType.ICE,
        category=MoveCategory.SPECIAL,
        base_power=55,
        is_spread=True,
        has_secondary_effect=True,
    ),
    "electroweb": Move(
        name="Electroweb",
        type=PokemonType.ELECTRIC,
        category=MoveCategory.SPECIAL,
        base_power=55,
        is_spread=True,
        has_secondary_effect=True,
    ),
    "thunder wave": Move(
        name="Thunder Wave",
        type=PokemonType.ELECTRIC,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "will-o-wisp": Move(
        name="Will-O-Wisp",
        type=PokemonType.FIRE,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "spore": Move(
        name="Spore",
        type=PokemonType.GRASS,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "rage powder": Move(
        name="Rage Powder",
        type=PokemonType.BUG,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "follow me": Move(
        name="Follow Me",
        type=PokemonType.NORMAL,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "pollen puff": Move(
        name="Pollen Puff",
        type=PokemonType.BUG,
        category=MoveCategory.SPECIAL,
        base_power=90,
    ),
    "surging strikes": Move(
        name="Surging Strikes",
        type=PokemonType.WATER,
        category=MoveCategory.PHYSICAL,
        base_power=75,
        makes_contact=True,
        is_punch=True,
    ),
    "aqua jet": Move(
        name="Aqua Jet",
        type=PokemonType.WATER,
        category=MoveCategory.PHYSICAL,
        base_power=40,
        makes_contact=True,
    ),
    "thunderclap": Move(
        name="Thunderclap",
        type=PokemonType.ELECTRIC,
        category=MoveCategory.SPECIAL,
        base_power=70,
    ),
    "swords dance": Move(
        name="Swords Dance",
        type=PokemonType.NORMAL,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "nasty plot": Move(
        name="Nasty Plot",
        type=PokemonType.DARK,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "calm mind": Move(
        name="Calm Mind",
        type=PokemonType.PSYCHIC,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "dragon dance": Move(
        name="Dragon Dance",
        type=PokemonType.DRAGON,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "stealth rock": Move(
        name="Stealth Rock",
        type=PokemonType.ROCK,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "spikes": Move(
        name="Spikes",
        type=PokemonType.GROUND,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "rapid spin": Move(
        name="Rapid Spin",
        type=PokemonType.NORMAL,
        category=MoveCategory.PHYSICAL,
        base_power=50,
        makes_contact=True,
    ),
    "defog": Move(
        name="Defog",
        type=PokemonType.FLYING,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "knock off": Move(
        name="Knock Off",
        type=PokemonType.DARK,
        category=MoveCategory.PHYSICAL,
        base_power=65,
        makes_contact=True,
    ),
    "taunt": Move(
        name="Taunt",
        type=PokemonType.DARK,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "roost": Move(
        name="Roost",
        type=PokemonType.FLYING,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "recover": Move(
        name="Recover",
        type=PokemonType.NORMAL,
        category=MoveCategory.STATUS,
        base_power=0,
    ),
    "bleakwind storm": Move(
        name="Bleakwind Storm",
        type=PokemonType.FLYING,
        category=MoveCategory.SPECIAL,
        base_power=100,
        is_spread=True,
        has_secondary_effect=True,
    ),
    "earth power": Move(
        name="Earth Power",
        type=PokemonType.GROUND,
        category=MoveCategory.SPECIAL,
        base_power=90,
        has_secondary_effect=True,
    ),
    "sludge bomb": Move(
        name="Sludge Bomb",
        type=PokemonType.POISON,
        category=MoveCategory.SPECIAL,
        base_power=90,
        has_secondary_effect=True,
    ),
    "rock slide": Move(
        name="Rock Slide",
        type=PokemonType.ROCK,
        category=MoveCategory.PHYSICAL,
        base_power=75,
        is_spread=True,
        has_secondary_effect=True,
    ),
    "stomping tantrum": Move(
        name="Stomping Tantrum",
        type=PokemonType.GROUND,
        category=MoveCategory.PHYSICAL,
        base_power=75,
        makes_contact=True,
    ),
    "high horsepower": Move(
        name="High Horsepower",
        type=PokemonType.GROUND,
        category=MoveCategory.PHYSICAL,
        base_power=95,
        makes_contact=True,
    ),
}


def resolve_pokemon(
    name: str,
    custom_types: str | None = None,
    custom_base_stats: str | None = None,
) -> Pokemon:
    """
    Resuelve un Pokémon del catálogo o lo construye al vuelo si se pasan stats/tipos
    personalizados (ideal para Randomlockes con stats/tipos randomizados o especies no listadas).
    Formato custom_types: "Ghost,Fairy" o "Fire"
    Formato custom_base_stats: "55,55,55,135,135,135" (HP,Atk,Def,SpA,SpD,Spe)
    """
    key = name.strip().lower()
    base_poke = POKEMON_CATALOG.get(key)

    if base_poke is None and (custom_types is None or custom_base_stats is None):
        available = ", ".join(sorted(p.name for p in POKEMON_CATALOG.values()))
        raise ValueError(
            f"Pokémon '{name}' no encontrado en el catálogo integrado. "
            f"Puedes especificar cualquier Pokémon usando --defender-types / --defender-stats "
            f"(o --attacker-types / --attacker-stats). Catálogo incluido: {available}"
        )

    types = base_poke.types if base_poke else []
    if custom_types:
        types = [PokemonType(t.strip().capitalize()) for t in custom_types.split(",") if t.strip()]

    if custom_base_stats:
        parts = [int(x.strip()) for x in custom_base_stats.split(",")]
        if len(parts) != 6:
            raise ValueError("Los Base Stats deben tener exactamente 6 enteros separados por comas: HP,Atk,Def,SpA,SpD,Spe")
        b_stats = BaseStat(
            hp=parts[0],
            atk=parts[1],
            **{"def": parts[2]},
            spa=parts[3],
            spd=parts[4],
            spe=parts[5],
        )
    else:
        assert base_poke is not None
        b_stats = base_poke.base_stats

    return Pokemon(name=name if not base_poke else base_poke.name, types=types, base_stats=b_stats)


def resolve_move(
    name: str,
    move_type: PokemonType | None = None,
    move_category: MoveCategory | None = None,
    move_bp: int | None = None,
    is_spread: bool | None = None,
    makes_contact: bool = False,
    is_punch: bool = False,
    is_biting: bool = False,
    is_slicing: bool = False,
    is_sound: bool = False,
    is_pulse: bool = False,
    is_recoil: bool = False,
    has_secondary: bool = False,
) -> Move:
    """
    Resuelve un movimiento del catálogo o permite crear/sobreescribir cualquier ataque
    personalizado al vuelo para Randomlocke.
    """
    key = name.strip().lower()
    base_move = MOVE_CATALOG.get(key)

    if base_move is None and (move_type is None or move_category is None or move_bp is None):
        return Move(
            name=name.strip(),
            type=move_type or PokemonType.NORMAL,
            category=move_category or MoveCategory.PHYSICAL,
            base_power=move_bp if move_bp is not None else 80,
            is_spread=bool(is_spread),
            makes_contact=makes_contact,
            is_punch=is_punch,
            is_biting=is_biting,
            is_slicing=is_slicing,
            is_sound=is_sound,
            is_pulse=is_pulse,
            is_recoil=is_recoil,
            has_secondary_effect=has_secondary,
        )

    if base_move is not None:
        return base_move.model_copy(
            update={
                "type": move_type or base_move.type,
                "category": move_category or base_move.category,
                "base_power": move_bp if move_bp is not None else base_move.base_power,
                "is_spread": is_spread if is_spread is not None else base_move.is_spread,
                "makes_contact": makes_contact or base_move.makes_contact,
                "is_punch": is_punch or base_move.is_punch,
                "is_biting": is_biting or base_move.is_biting,
                "is_slicing": is_slicing or base_move.is_slicing,
                "is_sound": is_sound or base_move.is_sound,
                "is_pulse": is_pulse or base_move.is_pulse,
                "is_recoil": is_recoil or base_move.is_recoil,
                "has_secondary_effect": has_secondary or base_move.has_secondary_effect,
            }
        )

    assert move_type is not None and move_category is not None and move_bp is not None
    return Move(
        name=name,
        type=move_type,
        category=move_category,
        base_power=move_bp,
        is_spread=bool(is_spread),
        makes_contact=makes_contact,
        is_punch=is_punch,
        is_biting=is_biting,
        is_slicing=is_slicing,
        is_sound=is_sound,
        is_pulse=is_pulse,
        is_recoil=is_recoil,
        has_secondary_effect=has_secondary,
    )
