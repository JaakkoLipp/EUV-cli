"""Recipe processing helpers."""

from __future__ import annotations

from eco_sim.sim.state import Market
from eco_sim.util.math import safe_div


def max_process_runs(market: Market, inputs: dict[str, float], capacity: float) -> float:
    if capacity <= 0.0:
        return 0.0
    if not inputs:
        return capacity
    runs_possible = capacity
    for good_id, amount in inputs.items():
        if amount <= 0.0:
            continue
        available = market.goods[good_id].stock
        runs_possible = min(runs_possible, safe_div(available, amount, 0.0))
    return max(0.0, runs_possible)
