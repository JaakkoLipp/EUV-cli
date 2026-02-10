"""Raw resource production system."""

from __future__ import annotations

from eco_sim.sim.state import GameState


def produce_resources(state: GameState) -> None:
    for region_id in sorted(state.regions.keys()):
        region = state.regions[region_id]
        if region.owner_id is None or region.market_id is None:
            continue
        market = state.markets[region.market_id]
        for good_id, amount in region.outputs.items():
            good_state = market.goods[good_id]
            good_state.stock += amount
            good_state.produced += amount
