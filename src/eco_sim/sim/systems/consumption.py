"""Consumption system for pops."""

from __future__ import annotations

from eco_sim.sim.rules.allocation import affordable_purchase
from eco_sim.sim.state import GameState
from eco_sim.util.math import safe_div


def allocate_and_consume(state: GameState) -> None:
    for pop_id in sorted(state.pops.keys()):
        pop = state.pops[pop_id]
        country = state.countries[pop.country_id]
        market = state.markets[country.market_id]
        satisfaction_total = 0.0
        satisfaction_count = 0

        for good_id in pop.priority:
            per_capita = pop.needs.get(good_id, 0.0)
            need = per_capita * pop.size
            if need <= 0.0:
                continue
            market_state = market.goods[good_id]

            bought = affordable_purchase(
                need=need,
                price=market_state.price,
                stock=market_state.stock,
                cash=pop.cash,
            )
            if bought > 0.0:
                cost = bought * market_state.price
                pop.cash -= cost
                market_state.stock -= bought
                market_state.bought += bought
            unmet = need - bought
            if unmet > 0.0:
                market_state.unmet += unmet

            satisfaction = safe_div(bought, need, 1.0)
            pop.satisfaction[good_id] = satisfaction
            satisfaction_total += satisfaction
            satisfaction_count += 1

        pop.satisfaction_avg = safe_div(satisfaction_total, float(satisfaction_count), 1.0)
