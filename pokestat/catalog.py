import json
import os
from pathlib import Path
import re
from pokestat.models import BaseStat, Move, MoveCategory, Pokemon, PokemonType, StatName

# Carga de la Pokédex oficial de Pokémon Showdown (1.500+ especies y formas)
_DATA_DIR = Path(__file__).parent / "data"
_SHOWDOWN_DEX: dict = {}
_SHOWDOWN_MOVES: dict = {}

_pokedex_path = _DATA_DIR / "pokedex.json"
if _pokedex_path.exists():
    try:
        with open(_pokedex_path, "r", encoding="utf-8") as f:
            _SHOWDOWN_DEX = json.load(f)
    except Exception:
        _SHOWDOWN_DEX = {}

_moves_path = _DATA_DIR / "moves.json"
if _moves_path.exists():
    try:
        with open(_moves_path, "r", encoding="utf-8") as f:
            _SHOWDOWN_MOVES = json.load(f)
    except Exception:
        _SHOWDOWN_MOVES = {}


def to_id(text: str) -> str:
    """Normaliza nombres al formato estándar de ID de Pokémon Showdown (solo letras minúsculas y números)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())

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
    Resuelve un Pokémon buscando primero en la Pokédex completa de Showdown (1.500+ especies),
    luego en el catálogo local y finalmente soporta creación al vuelo para Randomlocke.
    """
    clean_name = name.strip()
    dex_id = to_id(clean_name)
    key = clean_name.lower()

    # 1. Búsqueda en Pokédex oficial de Showdown
    sd_entry = _SHOWDOWN_DEX.get(dex_id)

    # 2. Búsqueda en catálogo local
    base_poke = POKEMON_CATALOG.get(key)

    types: list[PokemonType] = []
    b_stats: BaseStat | None = None

    if custom_types:
        types = [PokemonType(t.strip().capitalize()) for t in custom_types.split(",") if t.strip()]
    elif sd_entry and "types" in sd_entry:
        types = [PokemonType(t.strip().capitalize()) for t in sd_entry["types"] if t.strip() in PokemonType._value2member_map_]
    elif base_poke:
        types = base_poke.types

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
    elif sd_entry and "baseStats" in sd_entry:
        bs_raw = sd_entry["baseStats"]
        b_stats = BaseStat(
            hp=int(bs_raw.get("hp", 80)),
            atk=int(bs_raw.get("atk", 80)),
            **{"def": int(bs_raw.get("def", 80))},
            spa=int(bs_raw.get("spa", 80)),
            spd=int(bs_raw.get("spd", 80)),
            spe=int(bs_raw.get("spe", 80)),
        )
    elif base_poke:
        b_stats = base_poke.base_stats

    # Fallback si no está en ningún catálogo y no dio datos
    if not types:
        types = [PokemonType.NORMAL]
    if not b_stats:
        b_stats = BaseStat(hp=80, atk=80, **{"def": 80}, spa=80, spd=80, spe=80)

    final_name = sd_entry.get("name") if sd_entry else (base_poke.name if base_poke else clean_name)
    return Pokemon(name=final_name, types=types, base_stats=b_stats)


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
    Resuelve un movimiento buscando en la base de datos de Showdown (950+ movimientos),
    en el catálogo local o creándolo al vuelo si es inventado/personalizado.
    """
    clean_name = name.strip()
    move_id = to_id(clean_name)
    key = clean_name.lower()

    sd_move = _SHOWDOWN_MOVES.get(move_id)
    base_move = MOVE_CATALOG.get(key)

    # Determinar tipo
    final_type = move_type
    if not final_type:
        if sd_move and sd_move.get("type") in PokemonType._value2member_map_:
            final_type = PokemonType(sd_move["type"])
        elif base_move:
            final_type = base_move.type
        else:
            final_type = PokemonType.NORMAL

    # Determinar categoría
    final_cat = move_category
    if not final_cat:
        if sd_move and sd_move.get("category") in MoveCategory._value2member_map_:
            final_cat = MoveCategory(sd_move["category"])
        elif base_move:
            final_cat = base_move.category
        else:
            final_cat = MoveCategory.PHYSICAL

    # Determinar base power
    final_bp = move_bp
    if final_bp is None:
        if sd_move and "basePower" in sd_move:
            final_bp = int(sd_move["basePower"])
        elif base_move:
            final_bp = base_move.base_power
        else:
            final_bp = 80 if final_cat != MoveCategory.STATUS else 0

    # Flags especiales de Showdown
    flags = sd_move.get("flags", {}) if sd_move else {}
    target_type = sd_move.get("target", "") if sd_move else ""
    is_spread_final = is_spread if is_spread is not None else (target_type in ("allAdjacent", "allAdjacentFoes", "all") or (base_move.is_spread if base_move else False))

    contact_final = makes_contact or ("contact" in flags) or (base_move.makes_contact if base_move else False)
    punch_final = is_punch or ("punch" in flags) or (base_move.is_punch if base_move else False)
    biting_final = is_biting or ("bite" in flags) or (base_move.is_biting if base_move else False)
    slicing_final = is_slicing or ("slicing" in flags) or (base_move.is_slicing if base_move else False)
    sound_final = is_sound or ("sound" in flags) or (base_move.is_sound if base_move else False)
    pulse_final = is_pulse or ("pulse" in flags) or (base_move.is_pulse if base_move else False)

    final_name = sd_move.get("name") if sd_move else (base_move.name if base_move else clean_name)

    return Move(
        name=final_name,
        type=final_type,
        category=final_cat,
        base_power=final_bp,
        is_spread=is_spread_final,
        makes_contact=contact_final,
        is_punch=punch_final,
        is_biting=biting_final,
        is_slicing=slicing_final,
        is_sound=sound_final,
        is_pulse=pulse_final,
        is_recoil=is_recoil or (base_move.is_recoil if base_move else False),
        has_secondary_effect=has_secondary or (bool(sd_move.get("secondary")) if sd_move else False) or (base_move.has_secondary_effect if base_move else False),
    )
