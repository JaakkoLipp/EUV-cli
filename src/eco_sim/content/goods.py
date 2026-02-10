"""Goods definitions."""

from __future__ import annotations

from eco_sim.sim.state import GoodDefinition


def get_goods() -> dict[str, GoodDefinition]:
    return {
        "logs": GoodDefinition(
            id="logs",
            name="Logs",
            base_price=2.0,
            price_k=0.08,
            min_price_factor=0.5,
            max_price_factor=3.0,
        ),
        "planks": GoodDefinition(
            id="planks",
            name="Planks",
            base_price=5.0,
            price_k=0.07,
            min_price_factor=0.5,
            max_price_factor=3.0,
        ),
        "grain": GoodDefinition(
            id="grain",
            name="Grain",
            base_price=3.0,
            price_k=0.06,
            min_price_factor=0.5,
            max_price_factor=3.0,
        ),
        "tools": GoodDefinition(
            id="tools",
            name="Tools",
            base_price=12.0,
            price_k=0.09,
            min_price_factor=0.5,
            max_price_factor=3.0,
        ),
        "iron": GoodDefinition(
            id="iron",
            name="Iron",
            base_price=6.0,
            price_k=0.08,
            min_price_factor=0.5,
            max_price_factor=3.0,
        ),
    }
