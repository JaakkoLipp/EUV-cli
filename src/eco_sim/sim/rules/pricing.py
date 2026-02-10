"""Pricing adjustment rules."""

from __future__ import annotations

from eco_sim.util.math import clamp, safe_div


def adjusted_price(
    current: float,
    base: float,
    k: float,
    demand: float,
    supply: float,
    min_price: float,
    max_price: float,
) -> float:
    ratio = safe_div(demand, max(1.0, supply), 1.0)
    delta = current * k * (ratio - 1.0)
    return clamp(current + delta, min_price, max_price)
