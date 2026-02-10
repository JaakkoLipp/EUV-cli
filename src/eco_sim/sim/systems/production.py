"""Raw resource production system."""

from __future__ import annotations

from eco_sim.sim.state import GameState
from eco_sim.util.math import clamp


def produce_resources(state: GameState) -> None:
    for region_id in sorted(state.regions.keys()):
        region = state.regions[region_id]
        if region.owner_id is None or region.market_id is None:
            continue
        market = state.markets[region.market_id]
        for good_id, amount in region.outputs.items():
            good_state = market.goods[good_id]
            if good_state.base_price > 0.0:
                factor = clamp(good_state.price / good_state.base_price, 0.5, 1.5)
            else:
                factor = 1.0
            produced = amount * factor
            good_state.stock += produced
            good_state.produced += produced
