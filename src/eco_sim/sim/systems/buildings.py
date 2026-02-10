"""Building processing system."""

from __future__ import annotations

from eco_sim.sim.rules.recipes import max_process_runs
from eco_sim.sim.state import GameState


def process_buildings(state: GameState) -> None:
    for building_id in sorted(state.buildings.keys()):
        building = state.buildings[building_id]
        if not building.enabled:
            continue
        region = state.regions[building.region_id]
        if region.market_id is None:
            continue
        market = state.markets[region.market_id]
        building_type = state.building_types[building.type_id]
        capacity = building_type.base_capacity * building.level * building.capacity_multiplier
        input_cost = 0.0
        output_value = 0.0
        for good_id, amount in building_type.inputs.items():
            input_cost += market.goods[good_id].price * amount
        for good_id, amount in building_type.outputs.items():
            output_value += market.goods[good_id].price * amount
        if output_value <= input_cost * 0.9:
            continue
        runs = max_process_runs(market, building_type.inputs, capacity)
        if runs <= 0.0:
            continue
        for good_id, amount in building_type.inputs.items():
            market.goods[good_id].stock -= amount * runs
        for good_id, amount in building_type.outputs.items():
            good_state = market.goods[good_id]
            produced = amount * runs
            good_state.stock += produced
            good_state.produced += produced
