# ⚡ PokeStat — Gen 9 & Randomlocke EV Optimizer

**PokeStat** es una herramienta CLI en Python 3.11+ que resuelve matemáticamente el reparto óptimo de **EVs (Effort Values)** y **Naturalezas** para Pokémon competitivo (VGC / Singles Generación 9) y partidas **Randomlocke** (donde cualquier Pokémon puede tener cualquier ataque, habilidad, tipo o estadísticas base).

Dado un Pokémon defensor, un Pokémon atacante y un movimiento, **PokeStat** encuentra la combinación de `HP + Def/SpD` y `Naturaleza` que garantiza sobrevivir 1, 2 o 3 golpes (`Daño_Máximo < HP_Total`) **gastando la menor cantidad de EVs posibles**, maximizando los EVs sobrantes para invertir en Ataque o Velocidad.

---

## ✨ Características Principales

- **Fórmula Exacta de Generación 9 (Escala 4096):** Implementa el redondeo oficial de Game Freak (*round half down* / `poke_round`) y encadenamiento en punto fijo `floor((M1 * M2 + 2048) / 4096)` en cada paso de la fórmula.
- **Soporte Completo de STAB:**
  - STAB clásico (`x1.5`).
  - **Adaptability** (`x2.0`, o `x2.25` al teracristalizar en su propio tipo).
  - **Protean / Libero** (cambio de tipo dinámico con STAB `x1.5` en cualquier movimiento).
  - **Teracristalización Gen 9** (incluyendo el tipo **Stellar** `x2.0` / `x1.2` y la regla de 60 BP mínimos).
  - Habilidades **-ate** (*Pixilate*, *Aerilate*, *Refrigerate*, *Galvanize*, *Normalize*, *Liquid Voice*) que convierten el tipo del movimiento y otorgan STAB si coincide con el atacante.
- **Soporte Nativo para Randomlocke:**
  - Sin restricciones de *learnset* ni habilidades legales por especie.
  - **Habilidades Ofensivas:** *Huge Power*, *Pure Power*, *Hustle*, *Guts*, *Gorilla Tactics*, *Orichalcum Pulse*, *Hadron Engine*, *Solar Power*, *Technician*, *Iron Fist*, *Strong Jaw*, *Sharpness*, *Mega Launcher*, *Reckless*, *Sheer Force*, *Tough Claws*, *Punk Rock*, *Toxic Boost*, *Flare Boost*, *Sand Force*, *Steelworker*, *Steely Spirit*, *Transistor*, *Dragon's Maw*, *Rocky Payload*, *Water Bubble*, *Tinted Lens*, *Neuroforce*, *Unaware*, *Infiltrator*, *Scrappy*, *Mind's Eye*, *Mold Breaker*, *Teravolt*, *Turboblaze*.
  - **Habilidades Defensivas e Inmunidades:** *Wonder Guard*, *Multiscale*, *Shadow Shield*, *Fur Coat*, *Ice Scales*, *Fluffy*, *Thick Fat*, *Purifying Salt*, *Heatproof*, *Filter*, *Solid Rock*, *Prism Armor*, *Marvel Scale*, *Grass Pelt*, *Friend Guard*, *Levitate*, *Earth Eater*, *Volt Absorb*, *Lightning Rod*, *Motor Drive*, *Water Absorb*, *Storm Drain*, *Dry Skin*, *Flash Fire*, *Well-Baked Body*, *Sap Sipper*, *Bulletproof*, *Soundproof*.
  - **Habilidades Debilitadoras (Leyendas Funestas):** *Tablets of Ruin* (-25% Atk), *Sword of Ruin* (-25% Def), *Vessel of Ruin* (-25% SpA), *Beads of Ruin* (-25% SpD).
- **Doble Modo de Uso:**
  1. **Modo Interactivo Guiado (`python main.py`):** Menú visual paso a paso.
  2. **Modo Directo por Comandos (`python main.py optimize-def ...`):** Para uso rápido o scripts.
- **Interfaz Visual TUI (`rich`):** Badges de tipos con colores RGB oficiales, barra de vida estilo consola, medidor de presupuesto de EVs, matriz de los 16 rolls (`85%` a `100%`) y exportación directa a **Pokémon Showdown / PokéPaste**.

---

## 🚀 Instalación

```bash
pip install -r requirements.txt
```

---

## 🎮 Uso

### 1. Modo Interactivo (Asistente Paso a Paso)
Simplemente ejecuta el programa sin argumentos (o con `interactive`):
```bash
python main.py
```

### 2. Modo No Interactivo (Por Comandos)

#### Ejemplo Competitivo Estándar
```bash
python main.py optimize-def \
  --defender "Flutter Mane" \
  --attacker "Dragonite" \
  --move "Earthquake" \
  --item-attacker "Choice Band" \
  --target "survive-1-hit"
```

#### Ejemplo VGC / Dobles (con reducción 0.75x de daño Spread)
```bash
python main.py optimize-def \
  --defender "Flutter Mane" \
  --attacker "Dragonite" \
  --move "Earthquake" \
  --item-attacker "Choice Band" \
  --doubles
```

#### Ejemplo Randomlocke (Habilidades y Ataques Aleatorios)
```bash
python main.py optimize-def \
  --defender "Incineroar" \
  --ability-defender "Fur Coat" \
  --attacker "Garchomp" \
  --ability-attacker "Protean" \
  --move "Icicle Crash" \
  --item-attacker "Life Orb" \
  --target "survive-1-hit"
```

#### Ejemplo con Pokémon o Movimiento Personalizado (Fuera del Catálogo)
```bash
python main.py optimize-def \
  --defender "Swampert-Random" \
  --defender-types "Water,Grass" \
  --defender-stats "100,110,90,85,90,60" \
  --ability-defender "Thick Fat" \
  --attacker "Dragonite" \
  --ability-attacker "Aerilate" \
  --move "Double-Edge" \
  --move-type "Normal" \
  --move-category "Physical" \
  --move-bp 120
```

### 3. Ver Catálogo Integrado
```bash
python main.py catalog
```

---

## 🧪 Tests Unitarios

```bash
python -m pytest -v
```

---

## 🏛️ Arquitectura del Proyecto

```text
PokeStat/
├── main.py                  # Punto de entrada principal
├── requirements.txt         # Dependencias (pydantic, typer, rich, pytest)
├── pokestat/
│   ├── __init__.py
│   ├── models.py            # Entidades Pydantic (Pokemon, PokemonState, Move, Nature, BattleField)
│   ├── calculator.py        # Cálculo exacto de stats a Nivel 50 (math.floor e IEEE-754 safe)
│   ├── damage_engine.py     # Motor de daño Gen 9 (escala 4096, STAB, habilidades, 16 rolls)
│   ├── optimizer.py         # Algoritmo de minimización de EVs y comparativa de naturalezas
│   ├── catalog.py           # Catálogo integrado + resolución dinámica para Randomlocke
│   └── cli.py               # Interfaz TUI (Modo Interactivo y Modo por Comandos)
└── tests/
    └── test_pokestat.py     # Suite de pruebas unitarias
```
