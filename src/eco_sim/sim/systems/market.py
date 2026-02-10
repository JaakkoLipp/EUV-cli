"""Market pricing system."""

from __future__ import annotations

from eco_sim.sim.rules.pricing import adjusted_price
from eco_sim.sim.state import GameState


def update_prices(state: GameState) -> None:
    for market in state.markets.values():
        for good_id, good_state in market.goods.items():
            supply = max(0.0, good_state.stock)
            new_price = adjusted_price(
                current=good_state.price,
                base=good_state.base_price,
                k=good_state.price_k,
                demand=good_state.demanded,
                supply=supply,
                min_price=good_state.min_price,
                max_price=good_state.max_price,
            )
            good_state.last_delta = new_price - good_state.price
            good_state.price = new_price
