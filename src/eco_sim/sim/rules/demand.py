"""Demand adjustment rules."""

from __future__ import annotations

from eco_sim.util.math import clamp


def adjusted_need(need: float, price: float, base_price: float) -> float:
    if need <= 0.0:
        return 0.0
    if price <= 0.0 or base_price <= 0.0:
        return need
    factor = clamp(base_price / price, 0.5, 1.5)
    return need * factor
