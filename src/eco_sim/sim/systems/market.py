"""Market pricing system."""

from __future__ import annotations

from eco_sim.sim.rules.pricing import adjusted_price
from eco_sim.sim.state import GameState


def update_prices(state: GameState) -> None:
    for market in state.markets.values():
        demand = _estimate_market_demand(state, market.id)
        for good_id, good_state in market.goods.items():
            supply = good_state.stock + good_state.produced
            new_price = adjusted_price(
                current=good_state.price,
                base=good_state.base_price,
                k=good_state.price_k,
                demand=demand.get(good_id, 0.0),
                supply=supply,
                min_price=good_state.min_price,
                max_price=good_state.max_price,
            )
            good_state.last_delta = new_price - good_state.price
            good_state.price = new_price


def _estimate_market_demand(state: GameState, market_id: str) -> dict[str, float]:
    market = state.markets[market_id]
    country = state.countries[market.country_id]
    totals: dict[str, float] = {}
    for pop_id in country.pop_ids:
        pop = state.pops[pop_id]
        for good_id, per_capita in pop.needs.items():
            totals[good_id] = totals.get(good_id, 0.0) + (per_capita * pop.size)
    return totals
