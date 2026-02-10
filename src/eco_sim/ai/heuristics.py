"""Heuristics for AI economic decisions."""

from __future__ import annotations

from eco_sim.sim.state import GameState
from eco_sim.util.math import safe_div


def shortage_scores(state: GameState, country_id: str) -> dict[str, float]:
    market = state.markets[state.countries[country_id].market_id]
    scores: dict[str, float] = {}
    for good_id, good_state in market.goods.items():
        price_factor = safe_div(good_state.price, good_state.base_price, 1.0)
        unmet = good_state.unmet
        scores[good_id] = (unmet + 1.0) * price_factor
    return scores


def region_value(state: GameState, region_id: str) -> float:
    region = state.regions[region_id]
    value = 0.0
    for good_id, amount in region.outputs.items():
        value += amount * state.goods[good_id].base_price
    return value
