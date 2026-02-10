# EUV-CLI Economic Simulator

An economic supply and demand market trade simulator with a full-screen Textual TUI. The sim is tick-based, deterministic, and designed to be extended with more goods, buildings, policies, and screens.

## Quick Start (uv)

1. Create a virtual environment:

```bash
uv venv --python 3.11
```

2. Install dependencies:

```bash
uv pip install -r pyproject.toml
```

3. Run the game:

```bash
uv run python -m eco_sim
```

## Game Overview

- Two countries with separate markets and pops.
- Regions produce raw goods each tick.
- Buildings convert inputs into outputs.
- Pops buy goods based on income and priority needs.
- Trade routes move goods when profitable.
- Expand by annexing neutral regions.
- Optional AI country builds, trades, and expands.

## Controls

Key bindings:

- `q` quit
- `t` tick 1
- `T` tick 10
- `tab` cycle market

Command input is at the bottom of the screen. Press Enter to submit.

## Commands

```text
tick [n]
status
markets
market <id>
country <country_id>
goods
regions
region <id>
build <region_id> <building_type> [level]
toggle_building <building_id>
route add <src_market> <dst_market> <good> <cap> <transport_cost> <tariff_rate>
annex <region_id>
set tax <country_id> <rate>
ai on|off
help
quit
```

## Example Session

```text
status
tick 5
markets
market market_south
build south_forest lumber_mill 1
annex frontier_forest
route add market_south market_north logs 5 0.2 0.05
ai off
ai on
```

## Troubleshooting

- If you see `ModuleNotFoundError: eco_sim`, run via module mode:
  - `uv run python -m eco_sim`
- If Textual fails to start, update Textual:
  - `uv pip install -U textual`

## Project Layout

- [src/eco_sim](src/eco_sim) main package
- [src/eco_sim/sim](src/eco_sim/sim) simulation core
- [src/eco_sim/tui](src/eco_sim/tui) Textual UI
- [src/eco_sim/content](src/eco_sim/content) data-driven content
- [tests](tests) minimal tests

## Dev Notes

Add a new good:

- Update [src/eco_sim/content/goods.py](src/eco_sim/content/goods.py) with a new `GoodDefinition`.
- Ensure every market gets an initial `MarketGoodState` in the scenario helper.

Add a new building type:

- Update [src/eco_sim/content/buildings.py](src/eco_sim/content/buildings.py) with a new `BuildingType`.
- Use `build <region_id> <building_type>` to add an instance at runtime.

Add a new region:

- Update [src/eco_sim/content/scenarios.py](src/eco_sim/content/scenarios.py) with a new `Region`.
- For neutral expansion, keep `owner_id=None` and `market_id=None`.

Add a new market:

- Update [src/eco_sim/content/scenarios.py](src/eco_sim/content/scenarios.py) and add a matching `Country`.
- Ensure trade routes reference existing market ids.

Add a new UI panel:

- Create a new render helper in [src/eco_sim/tui/render.py](src/eco_sim/tui/render.py).
- Add a widget in [src/eco_sim/tui/app.py](src/eco_sim/tui/app.py) and update `_refresh_all`.

Adjust AI behavior:

- Edit thresholds and weights in [src/eco_sim/ai/controller.py](src/eco_sim/ai/controller.py).
- Scenario AI settings live in [src/eco_sim/content/scenarios.py](src/eco_sim/content/scenarios.py).
