import sys
from typing import Optional
import typer
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from pokestat.calculator import calculate_all_stats
from pokestat.catalog import MOVE_CATALOG, POKEMON_CATALOG, resolve_move, resolve_pokemon
from pokestat.damage_engine import (
    get_effective_move_type,
    get_type_effectiveness,
    is_defender_ability_ignored,
)
from pokestat.models import (
    BattleField,
    Move,
    MoveCategory,
    Nature,
    PokemonState,
    PokemonType,
    StatName,
    StatSpread,
    Terrain,
    Weather,
)
from pokestat.optimizer import OptimizationCandidate, SurvivalTarget, optimize_defense

# Forzar salida UTF-8 en terminales de Windows para que bordes redondeados y símbolos se vean nítidos
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    name="pokestat",
    help="Optimizador matemático de EVs y Naturalezas para Pokémon Competitivo (Gen 9) y Randomlocke.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()

# Paleta de colores oficial por Tipo Elemental para badges en terminal
TYPE_STYLES: dict[PokemonType, str] = {
    PokemonType.NORMAL: "black on rgb(168,167,122)",
    PokemonType.FIRE: "bold white on rgb(238,129,48)",
    PokemonType.WATER: "bold white on rgb(99,144,240)",
    PokemonType.ELECTRIC: "bold black on rgb(247,208,44)",
    PokemonType.GRASS: "bold white on rgb(122,199,76)",
    PokemonType.ICE: "bold black on rgb(150,217,214)",
    PokemonType.FIGHTING: "bold white on rgb(194,46,40)",
    PokemonType.POISON: "bold white on rgb(163,62,161)",
    PokemonType.GROUND: "bold black on rgb(226,191,101)",
    PokemonType.FLYING: "bold white on rgb(169,143,243)",
    PokemonType.PSYCHIC: "bold white on rgb(249,85,135)",
    PokemonType.BUG: "bold white on rgb(166,185,26)",
    PokemonType.ROCK: "bold white on rgb(182,161,54)",
    PokemonType.GHOST: "bold white on rgb(115,87,151)",
    PokemonType.DRAGON: "bold white on rgb(111,53,252)",
    PokemonType.DARK: "bold white on rgb(112,87,70)",
    PokemonType.STEEL: "bold black on rgb(183,183,206)",
    PokemonType.FAIRY: "bold black on rgb(214,133,173)",
    PokemonType.STELLAR: "bold white on rgb(64,181,165)",
}


def _type_badge(ptype: PokemonType) -> str:
    style = TYPE_STYLES.get(ptype, "bold white on blue")
    return f"[{style}] {ptype.value.upper()} [/{style}]"


def _hp_bar(current_hp: int, max_hp: int, width: int = 24) -> str:
    """Genera una barra de vida estilo consola de Pokémon con código de colores (>50% verde, >20% amarillo, <=20% rojo)."""
    if max_hp <= 0:
        return "[red]" + ("░" * width) + "[/red]"
    ratio = max(0.0, min(1.0, current_hp / max_hp))
    filled = round(ratio * width)
    if current_hp > 0 and filled == 0:
        filled = 1
    empty = width - filled

    if ratio > 0.5:
        color = "bright_green"
    elif ratio > 0.2:
        color = "gold1"
    else:
        color = "bright_red"

    bar = f"[{color}]{'█' * filled}[/{color}][grey30]{'░' * empty}[/grey30]"
    pct = round(ratio * 100, 1)
    return f"{bar} [bold {color}]{current_hp}/{max_hp} HP ({pct}%)[/bold {color}]"


def _ev_meter(spent: int, total: int = 508, width: int = 20) -> str:
    """Barra visual de presupuesto de EVs gastados vs libres."""
    ratio = max(0.0, min(1.0, spent / total))
    filled = round(ratio * width)
    free = width - filled
    return (
        f"[bright_yellow]{'━' * filled}[/bright_yellow][bright_green]{'━' * free}[/bright_green] "
        f"[bold yellow]{spent}[/bold yellow] usados / [bold bright_green]{total - spent}[/bold bright_green] libres"
    )


def _render_header() -> Panel:
    title = Text()
    title.append("⚡ POKESTAT ", style="bold bright_yellow")
    title.append("GEN 9 & RANDOMLOCKE EV OPTIMIZER", style="bold bright_white")
    subtitle = Text("Motor Matemático Exacto (Escala 4096) • Min(EV_HP + EV_DEF) s.a. Max_Dmg < HP", style="dim cyan")
    return Panel(
        Align.center(Group(title, subtitle)),
        box=box.DOUBLE_EDGE,
        border_style="bright_cyan",
        padding=(0, 2),
    )


def _render_matchup_cards(
    attacker: PokemonState,
    defender: PokemonState,
    move: Move,
    field: BattleField,
    target: SurvivalTarget,
) -> Table:
    atk_stats = calculate_all_stats(attacker)
    atk_stat_key = move.override_offensive_stat or (
        StatName.ATK if move.category == MoveCategory.PHYSICAL else StatName.SPA
    )
    eff_type, _ = get_effective_move_type(attacker, move)
    eff_mult = get_type_effectiveness(attacker, defender, move, eff_type)

    # Detectar STAB visualmente
    atk_ability_norm = (attacker.ability or "").strip().lower()
    has_protean = atk_ability_norm in {"protean", "libero"} and not attacker.is_terastallized
    has_orig_stab = (eff_type in attacker.pokemon.types) or has_protean
    has_tera_stab = attacker.is_terastallized and attacker.tera_type == eff_type
    if has_orig_stab and has_tera_stab:
        stab_str = "[bold bright_magenta]x2.25 (Tera+Adaptability)[/bold bright_magenta]" if atk_ability_norm == "adaptability" else "[bold bright_magenta]x2.0 (Tera STAB)[/bold bright_magenta]"
    elif has_orig_stab or has_tera_stab:
        stab_str = "[bold bright_cyan]x2.0 (Adaptability)[/bold bright_cyan]" if atk_ability_norm == "adaptability" else "[bold bright_green]x1.5 (STAB Activo)[/bold bright_green]"
    else:
        stab_str = "[dim]x1.0 (Sin STAB)[/dim]"

    # Efectividad visual
    if eff_mult >= 4.0:
        eff_str = "[bold bright_red]x4.0 (Doble Supereficaz)[/bold bright_red]"
    elif eff_mult >= 2.0:
        eff_str = "[bold rgb(255,140,0)]x2.0 (Supereficaz)[/bold rgb(255,140,0)]"
    elif eff_mult == 1.0:
        eff_str = "[white]x1.0 (Daño Neutro)[/white]"
    elif eff_mult == 0.0:
        eff_str = "[bold bright_cyan]x0.0 (Inmune)[/bold bright_cyan]"
    else:
        eff_str = f"[bold green]x{eff_mult} (Resistido)[/bold green]"

    atk_badges = " ".join(_type_badge(t) for t in attacker.pokemon.types)
    if attacker.is_terastallized and attacker.tera_type:
        atk_badges += f" ➔ [bold bright_magenta]TERA[/bold bright_magenta] {_type_badge(attacker.tera_type)}"

    def_badges = " ".join(_type_badge(t) for t in defender.pokemon.types)
    if defender.is_terastallized and defender.tera_type:
        def_badges += f" ➔ [bold bright_magenta]TERA[/bold bright_magenta] {_type_badge(defender.tera_type)}"

    atk_boost = attacker.stat_boosts.get(atk_stat_key, 0)
    boost_str = f" [bold yellow]({atk_boost:+d})[/bold yellow]" if atk_boost else ""

    atk_card = Panel(
        f"[bold white]{attacker.pokemon.name}[/bold white] [dim](Nvl {attacker.level})[/dim]\n"
        f"Tipos: {atk_badges}\n"
        f"Stat Ofensivo: [bold bright_red]{atk_stats[atk_stat_key]} {atk_stat_key.value.upper()}[/bold bright_red] "
        f"({attacker.evs.get(atk_stat_key)} EVs, {attacker.nature.value}){boost_str}\n"
        f"Habilidad: [bold yellow]{attacker.ability or 'Ninguna / Neutra'}[/bold yellow]\n"
        f"Objeto: [bold cyan]{attacker.item or 'Ninguno'}[/bold cyan]",
        title="⚔️  ATACANTE",
        border_style="red",
        box=box.ROUNDED,
        expand=True,
    )

    cat_icon = "💥 Físico" if move.category == MoveCategory.PHYSICAL else "✨ Especial"
    move_card = Panel(
        f"[bold bright_yellow]{move.name}[/bold bright_yellow] {_type_badge(eff_type)}\n"
        f"Categoría: [bold]{cat_icon}[/bold] • Potencia Base: [bold white]{move.base_power} BP[/bold white]\n"
        f"Bonificación STAB: {stab_str}\n"
        f"Efectividad: {eff_str}\n"
        f"Formato: [bold]{'Dobles / VGC (Spread 0.75x)' if field.is_doubles else 'Singles (1v1)'}[/bold] • "
        f"Clima/Campo: [cyan]{field.weather.value}/{field.terrain.value}[/cyan]",
        title="🎯 MOVIMIENTO Y CAMPO",
        border_style="yellow",
        box=box.ROUNDED,
        expand=True,
    )

    ignored = is_defender_ability_ignored(attacker, defender, move)
    def_ab_str = (
        f"[strike dim]{defender.ability}[/strike dim] [bold red](Ignorada por Mold Breaker)[/bold red]"
        if (defender.ability and ignored)
        else f"[bold bright_green]{defender.ability or 'Ninguna / Neutra'}[/bold bright_green]"
    )
    bs = defender.pokemon.base_stats
    def_card = Panel(
        f"[bold white]{defender.pokemon.name}[/bold white] [dim](Nvl {defender.level})[/dim]\n"
        f"Tipos: {def_badges}\n"
        f"Base Bulk: [bold cyan]{bs.hp} HP / {bs.def_} Def / {bs.spd} SpD[/bold cyan]\n"
        f"Habilidad: {def_ab_str}\n"
        f"Objeto: [bold cyan]{defender.item or 'Ninguno'}[/bold cyan] • Meta: [bold magenta]{target.value}[/bold magenta]",
        title="🛡️  DEFENSOR A OPTIMIZAR",
        border_style="bright_blue",
        box=box.ROUNDED,
        expand=True,
    )

    grid = Table.grid(expand=True, padding=(0, 1))
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(atk_card, move_card, def_card)
    return grid


def _render_rolls_visualizer(cand: OptimizationCandidate) -> Panel:
    """Muestra los 16 rolls exactos del motor de daño (85%..100%) con colores según riesgo."""
    rolls = cand.damage_result.rolls
    hp = cand.final_hp

    grid = Table.grid(expand=True, padding=(0, 1))
    for _ in range(8):
        grid.add_column(justify="center", ratio=1)

    row1 = []
    row2 = []
    for idx, dmg in enumerate(rolls):
        roll_pct = 85 + idx
        if dmg >= hp:
            style = "bold white on red"
        elif dmg == rolls[-1]:
            style = "bold bright_yellow"
        else:
            style = "bright_green"
        cell = f"[dim]R{roll_pct}:[/dim] [{style}]{dmg}[/{style}]"
        if idx < 8:
            row1.append(cell)
        else:
            row2.append(cell)

    grid.add_row(*row1)
    grid.add_row(*row2)

    return Panel(
        grid,
        title=f"🎲 Desglose de los 16 Rolls de Daño (Mín: {cand.damage_result.min_damage} | Máx: {cand.damage_result.max_damage} vs {hp} HP)",
        border_style="dim cyan",
        box=box.ROUNDED,
    )


def _render_showdown_export(defender: PokemonState, cand: OptimizationCandidate) -> Panel:
    """Genera el bloque listo para copiar y pegar en Pokémon Showdown / PokéPaste."""
    def_label = "Def" if cand.def_stat_name == StatName.DEF else "SpD"
    ev_parts = []
    if cand.hp_evs > 0:
        ev_parts.append(f"{cand.hp_evs} HP")
    if cand.def_evs > 0:
        ev_parts.append(f"{cand.def_evs} {def_label}")
    ev_line = " / ".join(ev_parts) if ev_parts else "0 HP"

    lines = []
    item_suffix = f" @ {defender.item}" if defender.item else ""
    lines.append(f"[bold bright_white]{defender.pokemon.name}{item_suffix}[/bold bright_white]")
    if defender.ability:
        lines.append(f"[cyan]Ability:[/cyan] {defender.ability}")
    lines.append(f"[cyan]Level:[/cyan] {defender.level}")
    if defender.tera_type:
        lines.append(f"[cyan]Tera Type:[/cyan] {defender.tera_type.value}")
    lines.append(f"[cyan]EVs:[/cyan] [bold yellow]{ev_line}[/bold yellow]  [dim](# + {cand.remaining_evs} EVs libres)[/dim]")
    lines.append(f"[cyan]{cand.nature.value} Nature[/cyan]")

    return Panel(
        "\n".join(lines),
        title="📋 Exportar a Pokémon Showdown",
        border_style="bright_magenta",
        box=box.ROUNDED,
    )


def _format_candidate_row(cand: OptimizationCandidate, is_winner: bool = False) -> tuple[str, ...]:
    def_label = "Def" if cand.def_stat_name == StatName.DEF else "SpD"
    badge = "🏆 " if is_winner else "   "
    spread_str = f"[bold white]{cand.hp_evs} HP[/bold white] / [bold cyan]{cand.def_evs} {def_label}[/bold cyan]"
    if cand.uses_boosting_nature:
        nature_tag = f"{badge}[bold cyan]{cand.nature.value}[/bold cyan] [dim](+{def_label})[/dim]"
    else:
        nature_tag = f"{badge}[bold bright_green]{cand.nature.value}[/bold bright_green] [dim](Neutra)[/dim]"

    dmg_range = (
        f"[white]{cand.damage_result.min_damage}-{cand.damage_result.max_damage}[/white] "
        f"[dim]({cand.damage_result.min_percent}%-{cand.damage_result.max_percent}%)[/dim]"
    )
    surv_pct = round(cand.hp_remaining_after_hits / cand.final_hp * 100, 1)
    surv_color = "bright_green" if surv_pct >= 15 else "gold1"
    surv_hp = f"[bold {surv_color}]{cand.hp_remaining_after_hits}/{cand.final_hp} HP[/bold {surv_color}] [dim]({surv_pct}%)[/dim]"

    return (
        nature_tag,
        spread_str,
        f"[bold yellow]{cand.total_defensive_evs}[/bold yellow]",
        f"[bold bright_green]{cand.remaining_evs}[/bold bright_green]",
        f"{cand.final_hp} HP / {cand.final_def_stat} {def_label}",
        dmg_range,
        surv_hp,
    )


def _execute_and_render_optimization(
    attacker_state: PokemonState,
    defender_state: PokemonState,
    move_obj: Move,
    target: SurvivalTarget,
    field: BattleField,
    show_header: bool = True,
) -> None:
    """Núcleo compartido entre el modo CLI por argumentos y el modo Interactivo."""
    def_poke = defender_state.pokemon
    level = defender_state.level
    preferred_penalty = (
        StatName.ATK if def_poke.base_stats.spa >= def_poke.base_stats.atk else StatName.SPA
    )

    report = optimize_defense(
        attacker=attacker_state,
        defender=defender_state,
        move=move_obj,
        target=target,
        field=field,
        preferred_penalty_stat=preferred_penalty,
    )

    if show_header:
        console.print()
        console.print(_render_header())
    console.print(_render_matchup_cards(attacker_state, defender_state, move_obj, field, target))

    if report.best_overall is None:
        wc = report.worst_case_with_max_investment
        console.print(
            Panel(
                f"[bold bright_red]💀 IMPOSIBLE SOBREVIVIR ({target.value.upper()})[/bold bright_red]\n\n"
                f"Ni siquiera con la máxima inversión posible ([bold white]252 HP / 252 {wc.def_stat_name.value.upper()}+ ({wc.nature.value})[/bold white]):\n"
                f"• Stats alcanzados: [bold]{wc.final_hp} HP / {wc.final_def_stat} {wc.def_stat_name.value.upper()}[/bold]\n"
                f"• Daño por golpe: [bold red]{wc.damage_result.min_damage}-{wc.damage_result.max_damage}[/bold red] "
                f"({wc.damage_result.min_percent}%-{wc.damage_result.max_percent}%)\n"
                f"• Barra de Vida tras golpe(s): {_hp_bar(0, wc.final_hp)}",
                title="⚠️  Alerta de K.O. Inevitable",
                border_style="bright_red",
                box=box.HEAVY,
            )
        )
        return

    best = report.best_overall
    def_label = "Def" if best.def_stat_name == StatName.DEF else "SpD"
    nature_badge = (
        f"[bold black on bright_cyan] {best.nature.value.upper()} (+10% {def_label}) [/bold black on bright_cyan]"
        if best.uses_boosting_nature
        else f"[bold black on bright_green] {best.nature.value.upper()} (NEUTRA) [/bold black on bright_green]"
    )

    winner_panel = Panel(
        f"Spread Óptimo: [bold bright_white]{best.hp_evs} HP / {best.def_evs} {def_label}[/bold bright_white]  {nature_badge}\n"
        f"Stats Reales (Nvl {level}): [bold cyan]{best.final_hp} HP[/bold cyan] │ [bold cyan]{best.final_def_stat} {def_label}[/bold cyan]\n"
        f"Daño Recibido: [bold white]{best.damage_result.min_damage} - {best.damage_result.max_damage} HP[/bold white] "
        f"[dim]({best.damage_result.min_percent}% - {best.damage_result.max_percent}%)[/dim]\n"
        f"Presupuesto EVs: {_ev_meter(best.total_defensive_evs)}\n"
        f"Vida Restante (Peor Roll): {_hp_bar(best.hp_remaining_after_hits, best.final_hp)}",
        title="🏆 SPREAD MÁS EFICIENTE ENCONTRADO",
        border_style="bright_green",
        box=box.HEAVY,
        expand=True,
    )

    export_panel = _render_showdown_export(defender_state, best)
    top_grid = Table.grid(expand=True, padding=(0, 1))
    top_grid.add_column(ratio=2)
    top_grid.add_column(ratio=1)
    top_grid.add_row(winner_panel, export_panel)
    console.print(top_grid)

    console.print(_render_rolls_visualizer(best))

    table = Table(
        title="📊 Comparativa de Spreads Eficientes (Mínimo Gasto de EVs)",
        box=box.ROUNDED,
        header_style="bold bright_cyan",
        border_style="bright_blue",
        show_lines=True,
        expand=True,
    )
    table.add_column("Naturaleza", justify="left", ratio=2)
    table.add_column("Spread Defensivo", justify="center", ratio=2)
    table.add_column("EVs Usados", justify="right", ratio=1)
    table.add_column("EVs Libres", justify="right", ratio=1)
    table.add_column(f"Stats (Nvl {level})", justify="center", ratio=2)
    table.add_column("Rango de Daño", justify="center", ratio=2)
    table.add_column("HP Garantizado", justify="center", ratio=2)

    seen: set[tuple[Nature, int, int]] = set()
    rows_to_show: list[OptimizationCandidate] = []

    for alt in report.top_alternatives:
        if len(rows_to_show) >= 5:
            break
        key = (alt.nature, alt.hp_evs, alt.def_evs)
        if key not in seen:
            rows_to_show.append(alt)
            seen.add(key)

    if report.best_neutral_nature:
        key = (report.best_neutral_nature.nature, report.best_neutral_nature.hp_evs, report.best_neutral_nature.def_evs)
        if key not in seen:
            rows_to_show.append(report.best_neutral_nature)
            seen.add(key)
    if report.best_boosting_nature:
        key = (report.best_boosting_nature.nature, report.best_boosting_nature.hp_evs, report.best_boosting_nature.def_evs)
        if key not in seen:
            rows_to_show.append(report.best_boosting_nature)
            seen.add(key)

    rows_to_show.sort(key=lambda c: (c.total_defensive_evs, c.uses_boosting_nature, -c.hp_remaining_after_hits))

    for cand in rows_to_show:
        is_best = (
            cand.nature == best.nature
            and cand.hp_evs == best.hp_evs
            and cand.def_evs == best.def_evs
        )
        table.add_row(*_format_candidate_row(cand, is_winner=is_best))

    console.print(table)
    console.print()


# ============================================================================
# MODO 1: CLI NO INTERACTIVO (Por argumentos directos / Scripting)
# ============================================================================

@app.command("optimize-def")
def optimize_def_command(
    defender: str = typer.Option(..., "--defender", "-d", help="Nombre del Pokémon defensor (ej. 'Flutter Mane')."),
    attacker: str = typer.Option(..., "--attacker", "-a", help="Nombre del Pokémon atacante (ej. 'Dragonite')."),
    move: str = typer.Option(..., "--move", "-m", help="Nombre del movimiento (ej. 'Earthquake')."),
    target: SurvivalTarget = typer.Option(
        SurvivalTarget.SURVIVE_1_HIT,
        "--target",
        "-t",
        help="Objetivo de supervivencia: survive-1-hit (evitar OHKO), survive-2-hits (evitar 2HKO), survive-3-hits.",
    ),
    # Configuración del Atacante (Standard + Randomlocke)
    nature_attacker: Nature = typer.Option(
        Nature.ADAMANT,
        "--nature-attacker",
        help="Naturaleza del atacante (por defecto Adamant para físicos / Modest si es especial).",
    ),
    evs_attacker: int = typer.Option(252, "--evs-attacker", min=0, max=252, help="EVs en el stat ofensivo del atacante."),
    item_attacker: Optional[str] = typer.Option(None, "--item-attacker", help="Objeto del atacante (ej. 'Choice Band', 'Life Orb')."),
    ability_attacker: Optional[str] = typer.Option(
        None,
        "--ability-attacker",
        help="Habilidad del atacante (soporta cualquiera para Randomlocke: 'Huge Power', 'Adaptability', 'Protean', 'Pixilate', 'Sword of Ruin', etc.).",
    ),
    tera_attacker: Optional[PokemonType] = typer.Option(None, "--tera-attacker", help="Tipo Tera activo en el atacante."),
    boost_attacker: int = typer.Option(0, "--boost-attacker", min=-6, max=6, help="Boost de Ataque/SpA del atacante (-6 a +6)."),
    burned_attacker: bool = typer.Option(False, "--burned-attacker", help="Si el atacante está quemado."),
    statused_attacker: bool = typer.Option(False, "--statused-attacker", help="Si el atacante tiene un problema de estado (para Guts, Toxic Boost)."),
    attacker_types: Optional[str] = typer.Option(None, "--attacker-types", help="Sobrescribir tipos del atacante separados por coma (ej. 'Dragon,Flying')."),
    attacker_stats: Optional[str] = typer.Option(None, "--attacker-stats", help="Sobrescribir Base Stats del atacante: 'HP,Atk,Def,SpA,SpD,Spe'."),
    # Configuración del Defensor (Standard + Randomlocke)
    item_defender: Optional[str] = typer.Option(None, "--item-defender", help="Objeto del defensor (ej. 'Assault Vest', 'Eviolite', 'Ability Shield')."),
    ability_defender: Optional[str] = typer.Option(
        None,
        "--ability-defender",
        help="Habilidad del defensor (ej. 'Multiscale', 'Fur Coat', 'Thick Fat', 'Filter', 'Levitate', 'Wonder Guard', 'Tablets of Ruin').",
    ),
    tera_defender: Optional[PokemonType] = typer.Option(None, "--tera-defender", help="Tipo Tera activo en el defensor."),
    boost_defender: int = typer.Option(0, "--boost-defender", min=-6, max=6, help="Boost de Defensa/SpD del defensor (-6 a +6)."),
    statused_defender: bool = typer.Option(False, "--statused-defender", help="Si el defensor tiene un problema de estado (para Marvel Scale)."),
    not_full_hp: bool = typer.Option(False, "--not-full-hp", help="Desactiva habilidades de 100% HP como Multiscale o Shadow Shield."),
    defender_types: Optional[str] = typer.Option(None, "--defender-types", help="Sobrescribir tipos del defensor separados por coma."),
    defender_stats: Optional[str] = typer.Option(None, "--defender-stats", help="Sobrescribir Base Stats del defensor: 'HP,Atk,Def,SpA,SpD,Spe'."),
    level: int = typer.Option(50, "--level", "-l", min=1, max=100, help="Nivel de los Pokémon (50 por defecto en VGC)."),
    # Configuración personalizada del Movimiento (para Randomlocke o ataques fuera del catálogo)
    move_type: Optional[PokemonType] = typer.Option(None, "--move-type", help="Tipo del movimiento (si es personalizado o modificado)."),
    move_category: Optional[MoveCategory] = typer.Option(None, "--move-category", help="Categoría del movimiento (Physical / Special)."),
    move_bp: Optional[int] = typer.Option(None, "--move-bp", help="Potencia base del movimiento."),
    # Condiciones del Campo (VGC / Singles)
    doubles: bool = typer.Option(False, "--doubles", help="Activa modo Dobles/VGC (aplica 0.75x a movimientos spread como Earthquake)."),
    weather: Weather = typer.Option(Weather.NONE, "--weather", help="Clima activo (Sun, Rain, Sand, Snow)."),
    terrain: Terrain = typer.Option(Terrain.NONE, "--terrain", help="Campo activo (Electric, Grassy, Misty, Psychic)."),
    reflect: bool = typer.Option(False, "--reflect", help="Reflect activo en el lado del defensor."),
    light_screen: bool = typer.Option(False, "--light-screen", help="Light Screen activo en el lado del defensor."),
    aurora_veil: bool = typer.Option(False, "--aurora-veil", help="Aurora Veil activo en el lado del defensor."),
    helping_hand: bool = typer.Option(False, "--helping-hand", help="Helping Hand activo en el atacante."),
    friend_guard: bool = typer.Option(False, "--friend-guard", help="Friend Guard activo en el aliado del defensor."),
) -> None:
    """
    [MODO NO INTERACTIVO] Calcula el spread óptimo directamente mediante argumentos de línea de comandos.
    """
    try:
        atk_poke = resolve_pokemon(attacker, attacker_types, attacker_stats)
        def_poke = resolve_pokemon(defender, defender_types, defender_stats)
        move_obj = resolve_move(
            move,
            move_type=move_type,
            move_category=move_category,
            move_bp=move_bp,
        )
    except ValueError as err:
        console.print(Panel(f"[bold red]{err}[/bold red]", title="❌ Error de Entrada", border_style="red"))
        raise typer.Exit(code=1)

    if move_obj.category == MoveCategory.SPECIAL and nature_attacker == Nature.ADAMANT:
        nature_attacker = Nature.MODEST

    atk_ev_spread = (
        StatSpread(atk=evs_attacker)
        if move_obj.category == MoveCategory.PHYSICAL
        else StatSpread(spa=evs_attacker)
    )
    atk_stat_key = StatName.ATK if move_obj.category == MoveCategory.PHYSICAL else StatName.SPA
    def_stat_key = move_obj.override_defensive_stat or (
        StatName.DEF if move_obj.category == MoveCategory.PHYSICAL else StatName.SPD
    )

    attacker_state = PokemonState(
        pokemon=atk_poke,
        level=level,
        nature=nature_attacker,
        evs=atk_ev_spread,
        item=item_attacker,
        ability=ability_attacker,
        tera_type=tera_attacker,
        is_terastallized=tera_attacker is not None,
        is_burned=burned_attacker,
        is_statused=statused_attacker or burned_attacker,
        stat_boosts={atk_stat_key: boost_attacker} if boost_attacker else {},
    )

    defender_state = PokemonState(
        pokemon=def_poke,
        level=level,
        item=item_defender,
        ability=ability_defender,
        tera_type=tera_defender,
        is_terastallized=tera_defender is not None,
        is_statused=statused_defender,
        is_full_hp=not not_full_hp,
        stat_boosts={def_stat_key: boost_defender} if boost_defender else {},
    )

    field = BattleField(
        weather=weather,
        terrain=terrain,
        is_doubles=doubles,
        is_reflect=reflect,
        is_light_screen=light_screen,
        is_aurora_veil=aurora_veil,
        is_helping_hand=helping_hand,
        is_friend_guard=friend_guard,
    )

    _execute_and_render_optimization(attacker_state, defender_state, move_obj, target, field)


# ============================================================================
# MODO 2: ASISTENTE INTERACTIVO GUIADO PASO A PASO
# ============================================================================

def _prompt_pokemon_interactive(role_label: str, default_name: str, border_color: str) -> tuple:
    console.print(Rule(f"[bold {border_color}]{role_label}[/bold {border_color}]", style=border_color))
    while True:
        name = Prompt.ask(f"  Nombre del Pokémon [dim](Enter para '{default_name}')[/dim]", default=default_name)
        in_catalog = name.strip().lower() in POKEMON_CATALOG
        custom_types = None
        custom_stats = None

        if not in_catalog:
            console.print(f"  [yellow]ℹ️  '{name}' no está en el catálogo rápido. Introduce sus Tipos y Base Stats:[/yellow]")
            custom_types = Prompt.ask("  Tipos separados por coma [dim](ej. Fire,Flying)[/dim]", default="Normal")
            custom_stats = Prompt.ask("  Base Stats (HP,Atk,Def,SpA,SpD,Spe) [dim](ej. 80,100,80,80,80,100)[/dim]", default="80,100,80,80,80,100")
        elif Confirm.ask("  ¿Quieres personalizar sus Tipos o Base Stats (Randomlocke)?", default=False):
            custom_types = Prompt.ask("  Nuevos Tipos separados por coma [dim](Enter para mantener)[/dim]", default="") or None
            custom_stats = Prompt.ask("  Nuevos Base Stats HP,Atk,Def,SpA,SpD,Spe [dim](Enter para mantener)[/dim]", default="") or None

        try:
            poke = resolve_pokemon(name, custom_types, custom_stats)
            break
        except ValueError as err:
            console.print(f"  [bold red]Error:[/bold red] {err}")

    ability = Prompt.ask(
        "  Habilidad [dim](ej. Huge Power, Adaptability, Protean, Multiscale, Fur Coat, Levitate | Enter = Ninguna)[/dim]",
        default="",
    ).strip() or None
    item = Prompt.ask(
        "  Objeto [dim](ej. Choice Band, Choice Specs, Life Orb, Assault Vest, Eviolite | Enter = Ninguno)[/dim]",
        default="",
    ).strip() or None
    tera_raw = Prompt.ask(
        "  Tipo Tera activo [dim](ej. Fire, Water, Ground, Fairy, Stellar | Enter = No Teracristalizado)[/dim]",
        default="",
    ).strip()
    tera_type = PokemonType(tera_raw.capitalize()) if tera_raw else None
    return poke, ability, item, tera_type


@app.command("interactive")
def interactive_command() -> None:
    """
    [MODO INTERACTIVO] Asistente visual paso a paso para optimizar EVs en Competitivo o Randomlocke.
    """
    console.print()
    console.print(_render_header())

    while True:
        console.print(
            Panel(
                "[bold white]Selecciona una acción del menú principal:[/bold white]\n"
                "  [bold cyan][1][/bold cyan] 🛡️  Optimizar EVs Defensivos (Asistente Guiado Paso a Paso)\n"
                "  [bold cyan][2][/bold cyan] ⚡ Prueba Rápida de Demostración (Dragonite Choice Band vs Flutter Mane)\n"
                "  [bold cyan][3][/bold cyan] 📖 Ver Catálogo Integrado de Pokémon y Movimientos\n"
                "  [bold cyan][4][/bold cyan] 🚪 Salir",
                title="🎮 Menú Interactivo PokeStat",
                border_style="bright_cyan",
                box=box.ROUNDED,
            )
        )
        choice = Prompt.ask("Elige una opción", choices=["1", "2", "3", "4"], default="1")

        if choice == "4":
            console.print("[bold bright_cyan]¡Hasta pronto, entrenador![/bold bright_cyan]")
            break

        if choice == "3":
            list_catalog()
            continue

        if choice == "2":
            optimize_def_command(
                defender="Flutter Mane",
                attacker="Dragonite",
                move="Earthquake",
                target=SurvivalTarget.SURVIVE_1_HIT,
                nature_attacker=Nature.ADAMANT,
                evs_attacker=252,
                item_attacker="Choice Band",
                ability_attacker=None,
                tera_attacker=None,
                boost_attacker=0,
                burned_attacker=False,
                statused_attacker=False,
                attacker_types=None,
                attacker_stats=None,
                item_defender=None,
                ability_defender=None,
                tera_defender=None,
                boost_defender=0,
                statused_defender=False,
                not_full_hp=False,
                defender_types=None,
                defender_stats=None,
                level=50,
                move_type=None,
                move_category=None,
                move_bp=None,
                doubles=False,
                weather=Weather.NONE,
                terrain=Terrain.NONE,
                reflect=False,
                light_screen=False,
                aurora_veil=False,
                helping_hand=False,
                friend_guard=False,
            )
            continue

        # Opción 1: Asistente paso a paso
        def_poke, def_ab, def_item, def_tera = _prompt_pokemon_interactive(
            "PASO 1: CONFIGURAR TU POKÉMON DEFENSOR", "Flutter Mane", "bright_blue"
        )
        atk_poke, atk_ab, atk_item, atk_tera = _prompt_pokemon_interactive(
            "PASO 2: CONFIGURAR EL POKÉMON ATACANTE RIVAL", "Dragonite", "red"
        )

        console.print(Rule("[bold yellow]PASO 3: MOVIMIENTO DEL ATACANTE[/bold yellow]", style="yellow"))
        while True:
            move_name = Prompt.ask("  Nombre del Movimiento", default="Earthquake")
            in_move_cat = move_name.strip().lower() in MOVE_CATALOG
            m_type = None
            m_cat = None
            m_bp = None
            if not in_move_cat:
                console.print(f"  [yellow]ℹ️  '{move_name}' es personalizado. Define sus datos:[/yellow]")
                t_str = Prompt.ask("  Tipo del movimiento [dim](ej. Ground, Fire, Fairy)[/dim]", default="Normal")
                c_str = Prompt.ask("  Categoría", choices=["Physical", "Special"], default="Physical")
                m_bp = IntPrompt.ask("  Potencia Base (BP)", default=100)
                m_type = PokemonType(t_str.strip().capitalize())
                m_cat = MoveCategory(c_str)
            try:
                move_obj = resolve_move(move_name, move_type=m_type, move_category=m_cat, move_bp=m_bp)
                break
            except ValueError as err:
                console.print(f"  [bold red]Error:[/bold red] {err}")

        console.print(Rule("[bold magenta]PASO 4: DETALLES DE COMBATE Y OBJETIVO[/bold magenta]", style="magenta"))
        default_nat = "Adamant" if move_obj.category == MoveCategory.PHYSICAL else "Modest"
        nat_str = Prompt.ask(
            f"  Naturaleza del Atacante [dim](Adamant, Modest, Jolly, Timid, Serious...)[/dim]",
            default=default_nat,
        )
        atk_nature = Nature(nat_str.strip().capitalize())
        atk_evs = IntPrompt.ask("  EVs ofensivos del Atacante (0-252)", default=252)
        level = IntPrompt.ask("  Nivel del combate", default=50)
        is_doubles = Confirm.ask("  ¿Es combate Dobles / VGC?", default=False)
        target_choice = Prompt.ask(
            "  Objetivo de supervivencia",
            choices=["survive-1-hit", "survive-2-hits", "survive-3-hits"],
            default="survive-1-hit",
        )

        atk_ev_spread = (
            StatSpread(atk=atk_evs)
            if move_obj.category == MoveCategory.PHYSICAL
            else StatSpread(spa=atk_evs)
        )
        attacker_state = PokemonState(
            pokemon=atk_poke,
            level=level,
            nature=atk_nature,
            evs=atk_ev_spread,
            item=atk_item,
            ability=atk_ab,
            tera_type=atk_tera,
            is_terastallized=atk_tera is not None,
        )
        defender_state = PokemonState(
            pokemon=def_poke,
            level=level,
            item=def_item,
            ability=def_ab,
            tera_type=def_tera,
            is_terastallized=def_tera is not None,
        )
        field = BattleField(is_doubles=is_doubles)

        _execute_and_render_optimization(
            attacker_state=attacker_state,
            defender_state=defender_state,
            move_obj=move_obj,
            target=SurvivalTarget(target_choice),
            field=field,
            show_header=False,
        )


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Si el usuario ejecuta `python main.py` sin subcomandos, lanza automáticamente el modo interactivo."""
    if ctx.invoked_subcommand is None:
        interactive_command()


@app.command("catalog")
def list_catalog() -> None:
    """Muestra los Pokémon y Movimientos predefinidos en el catálogo con badges de color."""
    console.print()
    console.print(_render_header())

    p_table = Table(
        title="📖 Pokémon en Catálogo Integrado (Usa --defender-stats/--defender-types para cualquier otro)",
        box=box.ROUNDED,
        header_style="bold bright_cyan",
        border_style="bright_blue",
        expand=True,
    )
    p_table.add_column("Pokémon", style="bold white")
    p_table.add_column("Tipos Elementales", justify="center")
    p_table.add_column("HP", justify="right", style="bright_green")
    p_table.add_column("Atk", justify="right", style="bright_red")
    p_table.add_column("Def", justify="right", style="bright_yellow")
    p_table.add_column("SpA", justify="right", style="bright_magenta")
    p_table.add_column("SpD", justify="right", style="bright_cyan")
    p_table.add_column("Spe", justify="right", style="bright_white")

    for p in sorted(POKEMON_CATALOG.values(), key=lambda x: x.name):
        bs = p.base_stats
        badges = " ".join(_type_badge(t) for t in p.types)
        p_table.add_row(
            p.name,
            badges,
            str(bs.hp),
            str(bs.atk),
            str(bs.def_),
            str(bs.spa),
            str(bs.spd),
            str(bs.spe),
        )
    console.print(p_table)

    m_table = Table(
        title="⚔️ Movimientos en Catálogo Integrado (Usa --move-type/--move-category/--move-bp para cualquier otro)",
        box=box.ROUNDED,
        header_style="bold bright_yellow",
        border_style="yellow",
        expand=True,
    )
    m_table.add_column("Movimiento", style="bold white")
    m_table.add_column("Tipo", justify="center")
    m_table.add_column("Categoría", justify="center")
    m_table.add_column("Potencia (BP)", justify="right", style="bold bright_yellow")
    m_table.add_column("Propiedades Especiales", style="dim")

    for m in sorted(MOVE_CATALOG.values(), key=lambda x: x.name):
        flags = []
        if m.is_spread:
            flags.append("Spread (Dobles)")
        if m.makes_contact:
            flags.append("Contacto")
        if m.is_punch:
            flags.append("Puño")
        if m.is_biting:
            flags.append("Mordisco")
        if m.is_slicing:
            flags.append("Cortante")
        if m.is_sound:
            flags.append("Sonido")
        if m.is_pulse:
            flags.append("Pulso")
        if m.is_recoil:
            flags.append("Retroceso")
        cat_str = "💥 Physical" if m.category == MoveCategory.PHYSICAL else "✨ Special"
        m_table.add_row(
            m.name,
            _type_badge(m.type),
            cat_str,
            str(m.base_power),
            ", ".join(flags) if flags else "—",
        )
    console.print(m_table)
    console.print()
