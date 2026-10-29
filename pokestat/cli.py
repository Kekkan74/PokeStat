from pathlib import Path
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
    Gender,
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
from pokestat.team_analyzer import (
    CORE_TYPES,
    TeamAnalysisReport,
    TeamFormat,
    analyze_team,
    load_team_from_file,
)

# Forzar salida UTF-8 en terminales de Windows para que bordes redondeados y símbolos se vean nítidos
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    name="pokestat",
    help="Analizador Visual de Equipos (6v6 / Dúos) y Optimizador Matemático de EVs para Pokémon Gen 9 & Randomlocke.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console(force_terminal=True if sys.stdout.isatty() else None)

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


def _gender_badge(gender: Gender) -> str:
    """Badge de género visual con colores estándar."""
    if gender == Gender.MALE:
        return "[bold bright_blue]♂ M[/bold bright_blue]"
    elif gender == Gender.FEMALE:
        return "[bold bright_magenta]♀ F[/bold bright_magenta]"
    return "[dim]⚲ N[/dim]"


def _type_badge(ptype: PokemonType, short: bool = False) -> str:
    style = TYPE_STYLES.get(ptype, "bold white on blue")
    label = ptype.value[:3].upper() if short else ptype.value.upper()
    return f"[{style}] {label} [/{style}]"


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


def _stat_bar(stat_val: int, max_scale: int = 220, width: int = 10, color: str = "bright_cyan") -> str:
    ratio = max(0.05, min(1.0, stat_val / max_scale))
    filled = round(ratio * width)
    return f"[{color}]{'█' * filled}[/{color}][grey23]{'░' * (width - filled)}[/grey23]"


def _render_breadcrumb(path_steps: list[str]) -> None:
    """Muestra una barra de navegación (Breadcrumb) en la parte superior para saber siempre en qué pantalla estás."""
    trail = " [dim]➔[/dim] ".join(f"[bold bright_cyan]{step}[/bold bright_cyan]" if i == len(path_steps) - 1 else f"[dim white]{step}[/dim white]" for i, step in enumerate(path_steps))
    console.print(Panel(f"📍 [bold white]Estás en:[/bold white] {trail}", box=box.ROUNDED, border_style="dim cyan", padding=(0, 1)))


def _render_header() -> Panel:
    title = Text()
    title.append("⚡ POKESTAT ", style="bold bright_yellow")
    title.append("TEAM AUDITOR & EV OPTIMIZER", style="bold bright_white")
    subtitle = Text("Diagnóstico de Sinergias (Dúos VGC & 6v6 Singles) • Motor Exacto Gen 9", style="dim cyan")
    return Panel(
        Align.center(Group(title, subtitle)),
        box=box.DOUBLE_EDGE,
        border_style="bright_cyan",
        padding=(0, 2),
    )


# ============================================================================
# RENDERIZADO VISUAL DE EQUIPO COMPLETO Y AUDITORÍA (6v6 vs DÚOS)
# ============================================================================

def _render_pokemon_member_card(idx: int, state: PokemonState) -> Panel:
    """Construye una tarjeta visual rica para un Pokémon del equipo (Stats reales, EVs, Naturaleza, Moves)."""
    stats = calculate_all_stats(state)
    badges = " ".join(_type_badge(t) for t in state.pokemon.types)
    if state.tera_type:
        badges += f" [dim]│[/dim] [bold magenta]Tera:[/bold magenta] {_type_badge(state.tera_type, short=True)}"

    stat_colors = {
        StatName.HP: "bright_green",
        StatName.ATK: "bright_red",
        StatName.DEF: "bright_yellow",
        StatName.SPA: "bright_magenta",
        StatName.SPD: "bright_cyan",
        StatName.SPE: "bright_white",
    }
    stat_labels = {
        StatName.HP: "HP ",
        StatName.ATK: "Atk",
        StatName.DEF: "Def",
        StatName.SPA: "SpA",
        StatName.SPD: "SpD",
        StatName.SPE: "Spe",
    }

    stat_lines = []
    for st in StatName:
        val = stats[st]
        ev = state.evs.get(st)
        mod = state.nature.get_modifier(st)
        nat_sym = "[bold bright_green]+[/bold bright_green]" if mod > 1.0 else ("[bold bright_red]-[/bold bright_red]" if mod < 1.0 else " ")
        ev_str = f"[yellow]{ev:>3} EV[/yellow]" if ev > 0 else "[dim]  0 EV[/dim]"
        bar = _stat_bar(val, max_scale=230 if st == StatName.HP else 210, width=8, color=stat_colors[st])
        stat_lines.append(f"[bold]{stat_labels[st]}[/bold]{nat_sym} [bold white]{val:>3}[/bold white] {bar} ({ev_str})")

    moves_lines = []
    for mv in state.moves[:4]:
        cat_ic = "💥" if mv.category == MoveCategory.PHYSICAL else ("✨" if mv.category == MoveCategory.SPECIAL else "🛡️")
        bp_txt = f"{mv.base_power} BP" if mv.base_power > 0 else "Status"
        moves_lines.append(f"• {_type_badge(mv.type, short=True)} {cat_ic} [bold white]{mv.name}[/bold white] [dim]({bp_txt})[/dim]")
    while len(moves_lines) < 4:
        moves_lines.append("[dim]• (Ranura vacía)[/dim]")

    rem_evs = state.evs.remaining_evs
    ev_status = (
        f"[bold bright_green]508/508 EVs Completos[/bold bright_green]"
        if rem_evs == 0
        else f"[bold yellow]{state.evs.total}/508 EVs ({rem_evs} libres)[/bold yellow]"
    )

    body = (
        f"{badges}\n"
        f"[cyan]Habilidad:[/cyan] [bold yellow]{state.ability or 'Ninguna'}[/bold yellow] │ "
        f"[cyan]Objeto:[/cyan] [bold white]{state.item or 'Ninguno'}[/bold white]\n"
        f"[cyan]Naturaleza:[/cyan] [bold bright_cyan]{state.nature.value}[/bold bright_cyan] │ {ev_status}\n"
        f"[dim]{'─' * 36}[/dim]\n"
        + "\n".join(stat_lines)
        + f"\n[dim]{'─' * 36}[/dim]\n"
        + "\n".join(moves_lines)
    )

    # Formateo de título con Apodo y Género
    title_parts = [f"#{idx}"]
    if state.nickname:
        title_parts.append(f'"{state.nickname}" ({state.pokemon.name})')
    else:
        title_parts.append(state.pokemon.name)
    title_parts.append(_gender_badge(state.gender))
    title_parts.append(f"[dim](Nvl {state.level})[/dim]")
    card_title = f"[bold bright_white]{' '.join(title_parts)}[/bold bright_white]"

    return Panel(
        body,
        title=card_title,
        border_style="bright_blue",
        box=box.ROUNDED,
        expand=True,
    )


def render_team_dashboard(report: TeamAnalysisReport, source_label: str = "") -> None:
    """Renderiza en terminal las tarjetas de todo el equipo, matriz defensiva, speed tiers y diagnóstico."""
    team = report.team
    fmt_badge = (
        "[bold black on bright_magenta] FORMATO: DÚOS / VGC (DOBLES) [/bold black on bright_magenta]"
        if report.team_format == TeamFormat.DOUBLES
        else "[bold black on bright_cyan] FORMATO: 6v6 SINGLES / RANDOMLOCKE [/bold black on bright_cyan]"
    )

    console.print(
        Rule(
            f"[bold bright_yellow]📋 ROSTER DEL EQUIPO ({len(team)} POKÉMON)[/bold bright_yellow] {fmt_badge}",
            style="bright_cyan",
        )
    )

    # Mostrar tarjetas de Pokémon en filas de 2 columnas
    for i in range(0, len(team), 2):
        row_grid = Table.grid(expand=True, padding=(0, 1))
        row_grid.add_column(ratio=1)
        row_grid.add_column(ratio=1)
        left_card = _render_pokemon_member_card(i + 1, team[i])
        right_card = _render_pokemon_member_card(i + 2, team[i + 1]) if (i + 1) < len(team) else Text("")
        row_grid.add_row(left_card, right_card)
        console.print(row_grid)

    # 2. Tabla de Sinergia Defensiva y Vulnerabilidades + Speed Tiers lado a lado
    def_table = Table(
        title="🛡️ Matriz de Resistencias y Debilidades Defensivas (Incluye Habilidades)",
        caption="[dim]Leyenda: [bold bright_cyan]INM[/bold bright_cyan] = Daño 0x │ [bold bright_green]¼x[/bold bright_green]/[green]½x[/green] = Resistido │ [dim]·[/dim] = Daño 1x Neutro │ [bold yellow]2x[/bold yellow]/[bold white on red]4x[/bold white on red] = Débil[/dim]",
        box=box.SIMPLE_HEAVY,
        header_style="bold bright_cyan",
        expand=True,
    )
    def_table.add_column("Tipo Atacante", justify="left")
    for m in team:
        display_label = m.nickname if m.nickname else m.pokemon.name
        g_sym = "♂" if m.gender == Gender.MALE else ("♀" if m.gender == Gender.FEMALE else "⚲")
        short_name = f"{display_label[:8]} {g_sym}"
        def_table.add_column(short_name, justify="center")
    def_table.add_column("Balance", justify="right")

    for t in CORE_TYPES:
        summ = report.defensive_matrix[t]
        # Mostramos en la tabla todos los tipos donde hay alguna debilidad relevante o inmunidad destacada
        cells = []
        for mult in summ.per_member_multiplier:
            if mult == 0.0:
                cells.append("[bold bright_cyan]INM[/bold bright_cyan]")
            elif mult == 0.25:
                cells.append("[bold bright_green]¼x[/bold bright_green]")
            elif mult == 0.5:
                cells.append("[green]½x[/green]")
            elif mult == 1.0:
                cells.append("[dim]·[/dim]")
            elif mult == 2.0:
                cells.append("[bold yellow]2x[/bold yellow]")
            else:
                cells.append("[bold white on red]4x[/bold white on red]")

        if summ.weak_count >= 3:
            bal_str = f"[bold bright_red]⚠️ -{summ.weak_count} Déb[/bold bright_red]"
        elif summ.weak_count >= 2 and (summ.resist_count + summ.immune_count) == 0:
            bal_str = "[bold yellow]⚠️ Sin Res[/bold yellow]"
        elif (summ.resist_count + summ.immune_count) > summ.weak_count:
            bal_str = f"[bright_green]+{summ.resist_count + summ.immune_count} Res[/bright_green]"
        else:
            bal_str = "[dim]Neutro[/dim]"

        def_table.add_row(_type_badge(t, short=True), *cells, bal_str)

    console.print(def_table)

    # 3. Speed Tiers + Cobertura Ofensiva lado a lado
    sp_table = Table(
        title="⚡ Speed Tiers del Equipo (Nivel Real)",
        caption="[dim]Tip: Mayor velocidad ataca primero antes de cambios de prioridad.[/dim]",
        box=box.ROUNDED,
        border_style="yellow",
        expand=True,
    )
    sp_table.add_column("#", justify="right", style="dim")
    sp_table.add_column("Pokémon", style="bold white")
    sp_table.add_column("Spe Final", justify="right", style="bold bright_yellow")
    sp_table.add_column("Inversión / Naturaleza", style="cyan")
    for rank, (p_name, spe_v, desc) in enumerate(report.speed_tiers, start=1):
        sp_table.add_row(str(rank), p_name, str(spe_v), desc)

    cov_badges = " ".join(_type_badge(t, short=True) for t in sorted(report.offensive_super_effective_coverage, key=lambda x: x.value))
    uncov_badges = (
        " ".join(_type_badge(t, short=True) for t in report.uncovered_offensive_types)
        if report.uncovered_offensive_types
        else "[bold bright_green]¡Cobertura Total 18/18 Tipos![/bold bright_green]"
    )
    cov_panel = Panel(
        f"[bold white]Perfil Ofensivo:[/bold white] [bold bright_red]{report.physical_attackers} Físicos[/bold bright_red] │ "
        f"[bold bright_magenta]{report.special_attackers} Especiales[/bold bright_magenta]\n\n"
        f"[bold bright_green]Golpea Supereficaz ({len(report.offensive_super_effective_coverage)}/18 tipos):[/bold bright_green]\n{cov_badges}\n\n"
        f"[bold yellow]Tipos sin respuesta Supereficaz ({len(report.uncovered_offensive_types)}):[/bold yellow]\n{uncov_badges}\n"
        f"[dim]Tip: Añadir ataques de estos tipos te ayudará a no quedarte sin opciones.[/dim]",
        title="🎯 Cobertura Ofensiva del Equipo",
        border_style="bright_magenta",
        box=box.ROUNDED,
        expand=True,
    )

    mid_grid = Table.grid(expand=True, padding=(0, 1))
    mid_grid.add_column(ratio=1)
    mid_grid.add_column(ratio=1)
    mid_grid.add_row(sp_table, cov_panel)
    console.print(mid_grid)

    # 4. Sección especial: Vulnerabilidad FÍSICA vs ESPECIAL y Tipos más Peligrosos
    phys_col = "bright_red"
    spec_col = "bright_magenta"
    diff_val = report.bulk_differential_pct
    diff_desc = f"+{diff_val}% SpD" if diff_val > 0 else f"{diff_val}% Def"
    bulk_verdict_col = (
        "bright_green"
        if "EQUILIBRADO" in report.bulk_orientation_verdict
        else ("gold1" if "FÍSICOS" in report.bulk_orientation_verdict else "bright_magenta")
    )

    phys_fragile_str = (
        ", ".join(f"{p[0]} (Def {p[2]})" for p in report.physically_fragile_members)
        if report.physically_fragile_members
        else "[green]Ninguno (Gran bulk físico en todo el equipo)[/green]"
    )
    spec_fragile_str = (
        ", ".join(f"{p[0]} (SpD {p[2]})" for p in report.specially_fragile_members)
        if report.specially_fragile_members
        else "[green]Ninguno (Gran bulk especial en todo el equipo)[/green]"
    )

    bulk_body = (
        f"Diagnóstico de Resistencia Mixta: [bold {bulk_verdict_col}]{report.bulk_orientation_verdict}[/bold {bulk_verdict_col}]\n"
        f"• Defensa Física Media: [bold {phys_col}]{report.avg_team_def}[/bold {phys_col}]  "
        f"{_stat_bar(int(report.avg_team_def), max_scale=180, width=12, color=phys_col)}\n"
        f"• Defensa Especial Media: [bold {spec_col}]{report.avg_team_spd}[/bold {spec_col}]  "
        f"{_stat_bar(int(report.avg_team_spd), max_scale=180, width=12, color=spec_col)}  [dim]({diff_desc})[/dim]\n\n"
        f"[bold yellow]Miembros vulnerables a Físico:[/bold yellow] [dim]{phys_fragile_str}[/dim]\n"
        f"[bold cyan]Miembros vulnerables a Especial:[/bold cyan] [dim]{spec_fragile_str}[/dim]"
    )

    bulk_panel = Panel(
        bulk_body,
        title="⚔️ Vulnerabilidad ante Atacante Físico vs Especial",
        border_style="bright_yellow",
        box=box.ROUNDED,
        expand=True,
    )

    # Ranking de Tipos más peligrosos (ante qué tipos eres más débil)
    type_threat_lines = []
    for rank, (t, weak_cnt, res_cnt) in enumerate(report.top_weakness_types[:4], start=1):
        warn_style = "bold bright_red" if weak_cnt >= 3 else "bold yellow"
        type_threat_lines.append(
            f"[dim]#{rank}[/dim] {_type_badge(t, short=True)} ➔ [{warn_style}]{weak_cnt} débiles[/{warn_style}] / [green]{res_cnt} res-inm[/green]"
        )
    if not type_threat_lines:
        type_threat_lines.append("[bold bright_green]¡Sin debilidades acumuladas destacadas![/bold bright_green]")

    res_lines = []
    for rank, (t, cnt) in enumerate(report.top_resistance_types[:4], start=1):
        res_lines.append(f"[dim]#{rank}[/dim] {_type_badge(t, short=True)} ➔ [bold bright_green]{cnt} Pokémon resisten/inmunes[/bold bright_green]")

    type_threat_body = (
        "[bold red]Tipos más peligrosos (mayor acumulación de debilidades):[/bold red]\n"
        + "\n".join(type_threat_lines)
        + "\n\n[bold green]Tipos mejor cubiertos (mayor resistencia/inmunidad):[/bold green]\n"
        + "\n".join(res_lines)
    )

    type_threat_panel = Panel(
        type_threat_body,
        title="⚠️ Tipos ante los que eres más Débil / Fuerte",
        border_style="red",
        box=box.ROUNDED,
        expand=True,
    )

    threat_grid = Table.grid(expand=True, padding=(0, 1))
    threat_grid.add_column(ratio=1)
    threat_grid.add_column(ratio=1)
    threat_grid.add_row(bulk_panel, type_threat_panel)
    console.print(threat_grid)

    # 5. Panel de Diagnóstico de Equilibrio y Propuestas de Mejora
    score = report.balance_score
    score_color = "bright_green" if score >= 85 else ("gold1" if score >= 70 else "bright_red")
    score_bar = _hp_bar(score, 100, width=25).replace("HP", "Pts")

    diag_lines = [
        f"Puntuación Global de Equilibrio ({report.team_format.value.upper()}): {score_bar} — [bold {score_color}]{report.verdict_label}[/bold {score_color}]\n"
    ]

    if report.strengths:
        diag_lines.append("[bold bright_green]✅ PUNTOS FUERTES DETECTADOS:[/bold bright_green]")
        for s in report.strengths:
            diag_lines.append(f"   • [green]{s}[/green]")
        diag_lines.append("")

    if report.warnings:
        diag_lines.append("[bold yellow]⚠️  DESEQUILIBRIOS Y PROBLEMAS DETECTADOS:[/bold yellow]")
        for w in report.warnings:
            diag_lines.append(f"   • [yellow]{w}[/yellow]")
        diag_lines.append("")

    if report.recommendations:
        diag_lines.append("[bold bright_cyan]💡 OPCIONES RECOMENDADAS PARA MEJORAR EL EQUIPO:[/bold bright_cyan]")
        for r in report.recommendations:
            diag_lines.append(f"   ➔ [bright_white]{r}[/bright_white]")

    console.print(
        Panel(
            "\n".join(diag_lines),
            title=f"🧠 AUDITORÍA TÁCTICA Y RECOMENDACIONES ({'DÚOS / VGC' if report.team_format == TeamFormat.DOUBLES else '6v6 SINGLES'})",
            border_style=score_color,
            box=box.HEAVY,
        )
    )


# ============================================================================
# RENDERIZADO DEL OPTIMIZADOR DE EVs INDIVIDUAL (CONTRA AMENAZA ESPECÍFICA)
# ============================================================================

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

    atk_disp_name = f'"{attacker.nickname}" ({attacker.pokemon.name})' if attacker.nickname else attacker.pokemon.name
    atk_card = Panel(
        f"[bold white]{atk_disp_name}[/bold white] {_gender_badge(attacker.gender)} [dim](Nvl {attacker.level})[/dim]\n"
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
    def_disp_name = f'"{defender.nickname}" ({defender.pokemon.name})' if defender.nickname else defender.pokemon.name
    def_card = Panel(
        f"[bold white]{def_disp_name}[/bold white] {_gender_badge(defender.gender)} [dim](Nvl {defender.level})[/dim]\n"
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
    def_label = "Def" if cand.def_stat_name == StatName.DEF else "SpD"
    ev_parts = []
    if cand.hp_evs > 0:
        ev_parts.append(f"{cand.hp_evs} HP")
    if cand.def_evs > 0:
        ev_parts.append(f"{cand.def_evs} {def_label}")
    ev_line = " / ".join(ev_parts) if ev_parts else "0 HP"

    lines = []
    header_name = f"{defender.nickname} ({defender.pokemon.name})" if defender.nickname else defender.pokemon.name
    gender_suffix = f" ({defender.gender.value})" if defender.gender != Gender.GENDERLESS else ""
    item_suffix = f" @ {defender.item}" if defender.item else ""
    lines.append(f"[bold bright_white]{header_name}{gender_suffix}{item_suffix}[/bold bright_white]")
    if defender.ability:
        lines.append(f"[cyan]Ability:[/cyan] {defender.ability}")
    lines.append(f"[cyan]Level:[/cyan] {defender.level}")
    if defender.tera_type:
        lines.append(f"[cyan]Tera Type:[/cyan] {defender.tera_type.value}")
    lines.append(f"[cyan]EVs:[/cyan] [bold yellow]{ev_line}[/bold yellow]  [dim](# + {cand.remaining_evs} EVs libres)[/dim]")
    lines.append(f"[cyan]{cand.nature.value} Nature[/cyan]")
    for mv in defender.moves[:4]:
        lines.append(f"- {mv.name}")

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
) -> OptimizationCandidate | None:
    def_poke = defender_state.pokemon
    level = defender_state.level
    preferred_penalty = (
        StatName.ATK if def_poke.base_stats.spa >= def_poke.base_stats.atk else StatName.SPA
    )

    # Limpiamos EVs previos del defensor al calcular el mínimo desde cero contra este golpe
    clean_defender = defender_state.model_copy(update={"evs": StatSpread()})

    report = optimize_defense(
        attacker=attacker_state,
        defender=clean_defender,
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
        return None

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
    return best


# ============================================================================
# COMANDO 1: ANALIZAR ARCHIVO DE EQUIPO (NO INTERACTIVO O CON CENTRO INTERACTIVO)
# ============================================================================

@app.command("team")
def team_command(
    file: str = typer.Option(
        "team_example.txt",
        "--file",
        "-f",
        help="Ruta al archivo del equipo en formato Showdown / PokéPaste (.txt) o .json.",
    ),
    mode: TeamFormat = typer.Option(
        TeamFormat.DOUBLES,
        "--format",
        "-m",
        help="Orientación táctica del equipo: 'duos' (VGC/Dobles) o '6v6' (Singles/Randomlocke).",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Abre el centro de mando interactivo tras visualizar el análisis del equipo.",
    ),
) -> None:
    """
    Carga un archivo de equipo, muestra visualmente todos sus Pokémon (stats reales, EVs, naturaleza,
    movimientos) y diagnostica si está equilibrado para 6v6 o Dúos con opciones de mejora.
    """
    try:
        team = load_team_from_file(file)
    except Exception as err:
        console.print(Panel(f"[bold red]{err}[/bold red]", title="❌ Error al Cargar Equipo", border_style="red"))
        raise typer.Exit(code=1)

    console.print()
    console.print(_render_header())
    report = analyze_team(team, team_format=mode)
    render_team_dashboard(report, source_label=file)

    if interactive:
        _interactive_team_loop(team, mode, file)


def _interactive_team_loop(team: list[PokemonState], current_format: TeamFormat, current_file: str) -> None:
    """Bucle interactivo centrado en el equipo cargado con migas de pan y ayuda clara."""
    while True:
        fmt_name = "Dúos / VGC (Dobles)" if current_format == TeamFormat.DOUBLES else "6v6 Singles"
        console.print()
        _render_breadcrumb(["Inicio", f"Equipo: {Path(current_file).name}", "Menú de Acciones"])
        console.print(
            Panel(
                f"[bold white]Equipo activo:[/bold white] [cyan]{current_file}[/cyan] ({len(team)} Pokémon) │ "
                f"[bold white]Modo actual:[/bold white] [bold magenta]{fmt_name}[/bold magenta]\n\n"
                "  [bold cyan][1][/bold cyan] 🛡️  [bold white]Optimizar EVs de un Pokémon:[/bold white] Elige a un miembro de tu equipo y calcula los EVs exactos para resistir un ataque rival.\n"
                "  [bold cyan][2][/bold cyan] 🔄 [bold white]Cambiar formato:[/bold white] Alterna al instante entre [bold]Dúos / VGC[/bold] ⇄ [bold]6v6 Singles[/bold] y re-evalúa el equilibrio.\n"
                "  [bold cyan][3][/bold cyan] 📂 [bold white]Cargar otro equipo:[/bold white] Analiza otro archivo .txt o .json sin reiniciar el programa.\n"
                "  [bold cyan][4][/bold cyan] 📖 [bold white]Ver catálogo integrado:[/bold white] Consulta especies y movimientos rápidos.\n"
                "  [bold cyan][5][/bold cyan] 🚪 [bold red]Salir del programa[/bold red]",
                title="🎮 Centro de Mando del Equipo — PokeStat",
                border_style="bright_cyan",
                box=box.ROUNDED,
            )
        )
        choice = Prompt.ask("Elige una acción [1-5]", choices=["1", "2", "3", "4", "5"], default="1")

        if choice == "5":
            console.print("[bold bright_cyan]¡Equipo listo para el combate! Hasta pronto.[/bold bright_cyan]")
            break

        if choice == "4":
            list_catalog()
            continue

        if choice == "3":
            console.print()
            _render_breadcrumb(["Inicio", "Cargar Nuevo Equipo"])
            new_path = Prompt.ask("Ruta del archivo de equipo (.txt o .json)", default=current_file)
            fmt_choice = Prompt.ask("¿Para qué formato está orientado? [duos/6v6]", choices=["duos", "6v6"], default=current_format.value)
            try:
                team = load_team_from_file(new_path)
                current_file = new_path
                current_format = TeamFormat(fmt_choice)
                console.print()
                _render_breadcrumb(["Inicio", f"Dashboard del Equipo ({current_format.value.upper()})"])
                report = analyze_team(team, team_format=current_format)
                render_team_dashboard(report, source_label=current_file)
            except Exception as err:
                console.print(f"[bold red]Error al cargar '{new_path}':[/bold red] {err}")
            continue

        if choice == "2":
            current_format = TeamFormat.SINGLES if current_format == TeamFormat.DOUBLES else TeamFormat.DOUBLES
            console.print()
            _render_breadcrumb(["Inicio", f"Dashboard del Equipo ({current_format.value.upper()})"])
            report = analyze_team(team, team_format=current_format)
            render_team_dashboard(report, source_label=current_file)
            continue

        if choice == "1":
            console.print()
            _render_breadcrumb(["Inicio", "Optimizar Pokémon del Equipo", "Paso 1: Seleccionar Defensor"])
            console.print(Rule("[bold bright_blue]PASO 1: SELECCIONA EL POKÉMON DE TU EQUIPO A OPTIMIZAR[/bold bright_blue]"))
            for idx, m in enumerate(team, start=1):
                name_lbl = f'"{m.nickname}" ({m.pokemon.name})' if m.nickname else m.pokemon.name
                g_str = f"[{m.gender.value}]" if m.gender != Gender.GENDERLESS else "[N]"
                console.print(f"  [bold cyan][{idx}][/bold cyan] {name_lbl} {g_str} ({m.nature.value}, Objeto: {m.item or 'Ninguno'}, Habilidad: {m.ability or 'Ninguna'})")
            valid_indices = [str(i) for i in range(1, len(team) + 1)]
            sel_idx = int(Prompt.ask("Número de Pokémon a mejorar [1-6]", choices=valid_indices, default="1")) - 1
            defender_member = team[sel_idx]

            console.print()
            _render_breadcrumb(["Inicio", f"Optimizar {defender_member.pokemon.name}", "Paso 2: Configurar Amenaza Rival"])
            console.print(Rule("[bold red]PASO 2: CONFIGURA EL ATACANTE Y ATAQUE RIVAL[/bold red]", style="red"))
            atk_name = Prompt.ask("  Pokémon Atacante rival", default="Dragonite")
            in_cat = atk_name.strip().lower() in POKEMON_CATALOG
            c_types = None
            c_stats = None
            if not in_cat:
                c_types = Prompt.ask("  Tipos del atacante (separados por coma)", default="Normal")
                c_stats = Prompt.ask("  Base Stats (HP,Atk,Def,SpA,SpD,Spe)", default="90,120,90,90,90,100")
            atk_poke = resolve_pokemon(atk_name, custom_types=c_types, custom_base_stats=c_stats)

            atk_ab = Prompt.ask("  Habilidad del atacante [dim](Enter = Ninguna / Neutra)[/dim]", default="").strip() or None
            atk_item = Prompt.ask("  Objeto del atacante [dim](ej. Choice Band, Choice Specs, Life Orb | Enter = Ninguno)[/dim]", default="Choice Band").strip() or None

            move_name = Prompt.ask("  Movimiento del atacante", default="Earthquake")
            move_obj = resolve_move(move_name)
            default_nat = "Adamant" if move_obj.category == MoveCategory.PHYSICAL else "Modest"
            atk_nat_str = Prompt.ask("  Naturaleza del atacante", default=default_nat)
            atk_nature = Nature(atk_nat_str.strip().capitalize())
            atk_evs = IntPrompt.ask("  EVs ofensivos del atacante (0-252)", default=252)
            target_str = Prompt.ask(
                "  Objetivo de supervivencia [survive-1-hit = aguantar 1 golpe | survive-2-hits = aguantar 2 golpes]",
                choices=["survive-1-hit", "survive-2-hits", "survive-3-hits"],
                default="survive-1-hit",
            )

            atk_spread = StatSpread(atk=atk_evs) if move_obj.category == MoveCategory.PHYSICAL else StatSpread(spa=atk_evs)
            attacker_state = PokemonState(
                pokemon=atk_poke,
                level=defender_member.level,
                nature=atk_nature,
                evs=atk_spread,
                item=atk_item,
                ability=atk_ab,
            )
            field = BattleField(is_doubles=(current_format == TeamFormat.DOUBLES))

            console.print()
            _render_breadcrumb(["Inicio", f"Optimizar {defender_member.pokemon.name}", "Resultado Óptimo de EVs"])
            best_cand = _execute_and_render_optimization(
                attacker_state=attacker_state,
                defender_state=defender_member,
                move_obj=move_obj,
                target=SurvivalTarget(target_str),
                field=field,
                show_header=False,
            )

            if best_cand is not None and Confirm.ask(
                f"¿Quieres guardar este spread óptimo ({best_cand.hp_evs} HP / {best_cand.def_evs} {best_cand.def_stat_name.value.upper()}, {best_cand.nature.value}) en tu equipo en memoria?",
                default=True,
            ):
                new_evs = defender_member.evs.model_copy(
                    update={
                        "hp": best_cand.hp_evs,
                        "def_": best_cand.def_evs if best_cand.def_stat_name == StatName.DEF else defender_member.evs.def_,
                        "spd": best_cand.def_evs if best_cand.def_stat_name == StatName.SPD else defender_member.evs.spd,
                    }
                )
                team[sel_idx] = defender_member.model_copy(update={"nature": best_cand.nature, "evs": new_evs})
                console.print(f"[bold bright_green]✅ ¡Spread actualizado en {defender_member.pokemon.name}! Puedes seguir analizando tu equipo.[/bold bright_green]")


@app.command("interactive")
def interactive_command() -> None:
    """
    [MODO INTERACTIVO] Te pide el archivo de tu equipo y si es para Dúos o 6v6, muestra todo el
    análisis visual y abre el Centro de Mando del Equipo.
    """
    console.print()
    _render_breadcrumb(["Inicio", "Seleccionar Archivo y Formato"])
    console.print(_render_header())
    
    console.print(
        Panel(
            "💡 [bold white]¿Cómo empezar?[/bold white]\n"
            "• Si ya tienes un archivo de equipo (.txt Showdown/PokéPaste), escribe su nombre o ruta.\n"
            "• Si solo quieres probar cómo funciona, presiona [bold cyan]Enter[/bold cyan] directamente para cargar el ejemplo.",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
    )

    default_file = "team_example.txt" if Path("team_example.txt").exists() else ""
    file_path = Prompt.ask(
        "📂 Ruta del archivo de tu equipo",
        default=default_file,
    )
    
    console.print(
        Panel(
            "🎮 [bold white]Selecciona el formato de combate:[/bold white]\n"
            "• [bold cyan]duos[/bold cyan]  ➔ Dobles / VGC (Evalúa Protect, Control de Velocidad, Fake Out, Intimidate)\n"
            "• [bold cyan]6v6[/bold cyan]   ➔ Singles / 6v6 (Evalúa Entry Hazards como Stealth Rock, Spikes, Rapid Spin y Pivotes)",
            border_style="dim cyan",
            box=box.ROUNDED,
        )
    )
    fmt_choice = Prompt.ask(
        "🎯 ¿Para qué formato está orientado tu equipo?",
        choices=["duos", "6v6"],
        default="duos",
    )
    mode = TeamFormat(fmt_choice)

    try:
        team = load_team_from_file(file_path)
    except Exception as err:
        console.print(Panel(f"[bold red]{err}[/bold red]", title="❌ Error al Cargar Equipo", border_style="red"))
        raise typer.Exit(code=1)

    console.print()
    _render_breadcrumb(["Inicio", f"Dashboard del Equipo ({mode.value.upper()})"])
    report = analyze_team(team, team_format=mode)
    render_team_dashboard(report, source_label=file_path)
    _interactive_team_loop(team, mode, file_path)


# ============================================================================
# COMANDO 2: OPTIMIZADOR INDIVIDUAL POR ARGUMENTOS DIRECTOS
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
    gender_attacker: Gender = typer.Option(
        Gender.GENDERLESS,
        "--gender-attacker",
        help="Género del atacante: 'M' (Macho), 'F' (Hembra) o 'N' (Sin género). Relevante para Rivalidad.",
    ),
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
    gender_defender: Gender = typer.Option(
        Gender.GENDERLESS,
        "--gender-defender",
        help="Género del defensor: 'M' (Macho), 'F' (Hembra) o 'N' (Sin género). Relevante para Rivalidad.",
    ),
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
    move_type: Optional[PokemonType] = typer.Option(None, "--move-type", help="Tipo del movimiento (si es personalizado o modificado)."),
    move_category: Optional[MoveCategory] = typer.Option(None, "--move-category", help="Categoría del movimiento (Physical / Special)."),
    move_bp: Optional[int] = typer.Option(None, "--move-bp", help="Potencia base del movimiento."),
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
    Calcula el spread óptimo de EVs y Naturaleza directamente para un enfrentamiento 1v1 o Dobles.
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
        gender=gender_attacker,
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
        gender=gender_defender,
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


@app.callback()
def main_callback(ctx: typer.Context) -> None:
    """Si se ejecuta sin argumentos (`python main.py`), abre el modo interactivo de análisis de equipo."""
    if ctx.invoked_subcommand is None:
        interactive_command()


@app.command("catalog")
def list_catalog() -> None:
    """Muestra los Pokémon y Movimientos predefinidos en el catálogo con badges de color."""
    console.print()
    console.print(_render_header())

    p_table = Table(
        title="📖 Pokémon en Catálogo Integrado",
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
        title="⚔️ Movimientos en Catálogo Integrado",
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
        cat_str = "💥 Physical" if m.category == MoveCategory.PHYSICAL else ("✨ Special" if m.category == MoveCategory.SPECIAL else "🛡️ Status")
        m_table.add_row(
            m.name,
            _type_badge(m.type),
            cat_str,
            str(m.base_power),
            ", ".join(flags) if flags else "—",
        )
    console.print(m_table)
    console.print()
