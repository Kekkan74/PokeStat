from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class StatName(str, Enum):
    """Identificadores de las 6 estadísticas principales de Pokémon."""
    HP = "hp"
    ATK = "atk"
    DEF = "def"
    SPA = "spa"
    SPD = "spd"
    SPE = "spe"


class PokemonType(str, Enum):
    """Los 18 tipos elementales + Stellar (Gen 9)."""
    NORMAL = "Normal"
    FIRE = "Fire"
    WATER = "Water"
    ELECTRIC = "Electric"
    GRASS = "Grass"
    ICE = "Ice"
    FIGHTING = "Fighting"
    POISON = "Poison"
    GROUND = "Ground"
    FLYING = "Flying"
    PSYCHIC = "Psychic"
    BUG = "Bug"
    ROCK = "Rock"
    GHOST = "Ghost"
    DRAGON = "Dragon"
    DARK = "Dark"
    STEEL = "Steel"
    FAIRY = "Fairy"
    STELLAR = "Stellar"


class MoveCategory(str, Enum):
    """Categorías de movimiento."""
    PHYSICAL = "Physical"
    SPECIAL = "Special"
    STATUS = "Status"


class Nature(str, Enum):
    """Las 25 naturalezas de Pokémon y sus modificadores de estadísticas."""
    # Neutras (x1.0 en todo)
    HARDY = "Hardy"
    DOCILE = "Docile"
    SERIOUS = "Serious"
    BASHFUL = "Bashful"
    QUIRKY = "Quirky"

    # +Atk (x1.1)
    LONELY = "Lonely"    # -Def
    BRAVE = "Brave"      # -Spe
    ADAMANT = "Adamant"  # -SpA
    NAUGHTY = "Naughty"  # -SpD

    # +Def (x1.1)
    BOLD = "Bold"        # -Atk
    RELAXED = "Relaxed"  # -Spe
    IMPISH = "Impish"    # -SpA
    LAX = "Lax"          # -SpD

    # +Spe (x1.1)
    TIMID = "Timid"      # -Atk
    HASTY = "Hasty"      # -Def
    JOLLY = "Jolly"      # -SpA
    NAIVE = "Naive"      # -SpD

    # +SpA (x1.1)
    MODEST = "Modest"    # -Atk
    MILD = "Mild"        # -Def
    QUIET = "Quiet"      # -Spe
    RASH = "Rash"        # -SpD

    # +SpD (x1.1)
    CALM = "Calm"        # -Atk
    GENTLE = "Gentle"    # -Def
    SASSY = "Sassy"      # -Spe
    CAREFUL = "Careful"  # -SpA

    def get_modifier(self, stat: StatName) -> float:
        """Devuelve el multiplicador de naturaleza (1.1, 0.9 o 1.0) para un stat dado."""
        if stat == StatName.HP:
            return 1.0
        plus_stat, minus_stat = _NATURE_EFFECTS.get(self, (None, None))
        if plus_stat == minus_stat:
            return 1.0
        if stat == plus_stat:
            return 1.1
        if stat == minus_stat:
            return 0.9
        return 1.0


_NATURE_EFFECTS: dict[Nature, tuple[Optional[StatName], Optional[StatName]]] = {
    Nature.HARDY: (StatName.ATK, StatName.ATK),
    Nature.LONELY: (StatName.ATK, StatName.DEF),
    Nature.BRAVE: (StatName.ATK, StatName.SPE),
    Nature.ADAMANT: (StatName.ATK, StatName.SPA),
    Nature.NAUGHTY: (StatName.ATK, StatName.SPD),
    Nature.BOLD: (StatName.DEF, StatName.ATK),
    Nature.DOCILE: (StatName.DEF, StatName.DEF),
    Nature.RELAXED: (StatName.DEF, StatName.SPE),
    Nature.IMPISH: (StatName.DEF, StatName.SPA),
    Nature.LAX: (StatName.DEF, StatName.SPD),
    Nature.TIMID: (StatName.SPE, StatName.ATK),
    Nature.HASTY: (StatName.SPE, StatName.DEF),
    Nature.SERIOUS: (StatName.SPE, StatName.SPE),
    Nature.JOLLY: (StatName.SPE, StatName.SPA),
    Nature.NAIVE: (StatName.SPE, StatName.SPD),
    Nature.MODEST: (StatName.SPA, StatName.ATK),
    Nature.MILD: (StatName.SPA, StatName.DEF),
    Nature.QUIET: (StatName.SPA, StatName.SPE),
    Nature.BASHFUL: (StatName.SPA, StatName.SPA),
    Nature.RASH: (StatName.SPA, StatName.SPD),
    Nature.CALM: (StatName.SPD, StatName.ATK),
    Nature.GENTLE: (StatName.SPD, StatName.DEF),
    Nature.SASSY: (StatName.SPD, StatName.SPE),
    Nature.CAREFUL: (StatName.SPD, StatName.SPA),
    Nature.QUIRKY: (StatName.SPD, StatName.SPD),
}


class BaseStat(BaseModel):
    """Estadísticas base (Base Stats) de una especie Pokémon."""
    hp: int = Field(..., ge=1, le=255)
    atk: int = Field(..., ge=1, le=255)
    def_: int = Field(..., alias="def", ge=1, le=255)
    spa: int = Field(..., ge=1, le=255)
    spd: int = Field(..., ge=1, le=255)
    spe: int = Field(..., ge=1, le=255)

    model_config = {"populate_by_name": True}

    def get(self, stat: StatName) -> int:
        return getattr(self, "def_" if stat == StatName.DEF else stat.value)


class StatSpread(BaseModel):
    """Reparto de EVs o IVs en las 6 estadísticas."""
    hp: int = Field(default=0, ge=0, le=252)
    atk: int = Field(default=0, ge=0, le=252)
    def_: int = Field(default=0, alias="def", ge=0, le=252)
    spa: int = Field(default=0, ge=0, le=252)
    spd: int = Field(default=0, ge=0, le=252)
    spe: int = Field(default=0, ge=0, le=252)

    model_config = {"populate_by_name": True}

    @property
    def total(self) -> int:
        return self.hp + self.atk + self.def_ + self.spa + self.spd + self.spe

    @property
    def remaining_evs(self) -> int:
        return 508 - self.total

    @model_validator(mode="after")
    def validate_total_evs(self) -> "StatSpread":
        if self.total > 510:
            raise ValueError(f"El total de EVs ({self.total}) no puede superar 510.")
        return self

    def get(self, stat: StatName) -> int:
        return getattr(self, "def_" if stat == StatName.DEF else stat.value)


class IVSpread(BaseModel):
    """Valores Individuales (IVs) de un Pokémon (31 por defecto en competitivo)."""
    hp: int = Field(default=31, ge=0, le=31)
    atk: int = Field(default=31, ge=0, le=31)
    def_: int = Field(default=31, alias="def", ge=0, le=31)
    spa: int = Field(default=31, ge=0, le=31)
    spd: int = Field(default=31, ge=0, le=31)
    spe: int = Field(default=31, ge=0, le=31)

    model_config = {"populate_by_name": True}

    def get(self, stat: StatName) -> int:
        return getattr(self, "def_" if stat == StatName.DEF else stat.value)


class Pokemon(BaseModel):
    """Definición estática de una especie Pokémon."""
    name: str
    types: list[PokemonType] = Field(..., min_length=1, max_length=2)
    base_stats: BaseStat


class Weather(str, Enum):
    """Climas activos en el campo."""
    NONE = "None"
    SUN = "Sun"
    RAIN = "Rain"
    SAND = "Sand"
    SNOW = "Snow"
    HARSH_SUNSHINE = "Harsh Sunshine"
    HEAVY_RAIN = "Heavy Rain"


class Terrain(str, Enum):
    """Campos activos en combate."""
    NONE = "None"
    ELECTRIC = "Electric"
    GRASSY = "Grassy"
    MISTY = "Misty"
    PSYCHIC = "Psychic"


class BattleField(BaseModel):
    """Condiciones globales del campo de batalla."""
    weather: Weather = Weather.NONE
    terrain: Terrain = Terrain.NONE
    is_doubles: bool = False
    is_reflect: bool = False
    is_light_screen: bool = False
    is_aurora_veil: bool = False
    is_helping_hand: bool = False
    is_friend_guard: bool = False
    # Ruin abilities activas en el campo (aunque las tenga otro Pokémon o el mismo)
    tablets_of_ruin: bool = False  # -25% Atk
    sword_of_ruin: bool = False    # -25% Def
    vessel_of_ruin: bool = False   # -25% SpA
    beads_of_ruin: bool = False    # -25% SpD


class PokemonState(BaseModel):
    """Estado completo de un Pokémon en combate (especie + configuración competitiva / Randomlocke)."""
    pokemon: Pokemon
    nickname: Optional[str] = None
    level: int = Field(default=50, ge=1, le=100)
    nature: Nature = Field(default=Nature.SERIOUS)
    evs: StatSpread = Field(default_factory=StatSpread)
    ivs: IVSpread = Field(default_factory=IVSpread)
    item: Optional[str] = None
    ability: Optional[str] = None
    tera_type: Optional[PokemonType] = None
    is_terastallized: bool = False
    is_burned: bool = False
    is_statused: bool = Field(
        default=False,
        description="True si sufre quemadura, parálisis, veneno, sueño o congelación (para Guts, Marvel Scale, etc.).",
    )
    is_full_hp: bool = Field(
        default=True,
        description="True si está al 100% de vida (para Multiscale / Shadow Shield).",
    )
    moves: list["Move"] = Field(default_factory=list, max_length=4)
    stat_boosts: dict[StatName, int] = Field(default_factory=dict)


class Move(BaseModel):
    """Representación de un movimiento de Pokémon en Gen 9 (desacoplado del Pokémon para soportar Randomlocke)."""
    name: str
    type: PokemonType
    category: MoveCategory
    base_power: int = Field(..., ge=0)
    is_spread: bool = Field(
        default=False,
        description="True si golpea a múltiples objetivos (ej. Earthquake en Dobles/VGC).",
    )
    makes_contact: bool = False
    is_punch: bool = Field(default=False, description="Para Iron Fist.")
    is_biting: bool = Field(default=False, description="Para Strong Jaw.")
    is_slicing: bool = Field(default=False, description="Para Sharpness.")
    is_sound: bool = Field(default=False, description="Para Punk Rock.")
    is_pulse: bool = Field(default=False, description="Para Mega Launcher.")
    is_recoil: bool = Field(default=False, description="Para Reckless.")
    has_secondary_effect: bool = Field(default=False, description="Para Sheer Force.")
    override_defensive_stat: Optional[StatName] = Field(
        default=None,
        description="Para movimientos como Psyshock que son Especiales pero golpean en Defensa física.",
    )
    override_offensive_stat: Optional[StatName] = Field(
        default=None,
        description="Para movimientos como Body Press que usan Defensa como stat ofensivo.",
    )

