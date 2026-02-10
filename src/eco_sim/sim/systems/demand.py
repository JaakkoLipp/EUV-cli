"""Demand intent system."""

from __future__ import annotations

from eco_sim.sim.rules.demand import adjusted_need
from eco_sim.sim.state import GameState


def compute_demand_intents(state: GameState) -> None:
    for pop_id in sorted(state.pops.keys()):
        pop = state.pops[pop_id]
        country = state.countries[pop.country_id]
        market = state.markets[country.market_id]
        for good_id, per_capita in pop.needs.items():
            need = per_capita * pop.size
            if need <= 0.0:
                continue
            good_state = market.goods[good_id]
            effective_need = adjusted_need(need, good_state.price, good_state.base_price)
            market.goods[good_id].demanded += effective_need
