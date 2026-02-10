"""Allocation rules for purchasing."""

from __future__ import annotations


def affordable_purchase(need: float, price: float, stock: float, cash: float) -> float:
    if need <= 0.0 or price <= 0.0 or stock <= 0.0 or cash <= 0.0:
        return 0.0
    affordable = cash / price
    return min(need, stock, affordable)
