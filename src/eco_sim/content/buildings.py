"""Building type definitions."""

from __future__ import annotations

from eco_sim.sim.state import BuildingType


def get_building_types() -> dict[str, BuildingType]:
    return {
        "lumber_mill": BuildingType(
            id="lumber_mill",
            name="Lumber Mill",
            inputs={"logs": 2.0},
            outputs={"planks": 1.0},
            base_capacity=10.0,
            cost=40.0,
            upkeep=1.0,
        ),
        "tool_workshop": BuildingType(
            id="tool_workshop",
            name="Tool Workshop",
            inputs={"planks": 2.0, "iron": 1.0},
            outputs={"tools": 1.0},
            base_capacity=6.0,
            cost=70.0,
            upkeep=2.0,
        ),
    }
