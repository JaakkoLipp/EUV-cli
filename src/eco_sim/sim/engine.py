"""Tick orchestration for the simulation."""

from __future__ import annotations

from eco_sim.sim.state import GameState
from eco_sim.ai.controller import run_ai
from eco_sim.sim.systems.buildings import process_buildings
from eco_sim.sim.systems.consumption import allocate_and_consume
from eco_sim.sim.systems.demand import compute_demand_intents
from eco_sim.sim.systems.finance import apply_finance
from eco_sim.sim.systems.market import update_prices
from eco_sim.sim.systems.production import produce_resources
from eco_sim.sim.systems.trade import execute_trade


def tick(state: GameState, ticks: int = 1) -> None:
    for _ in range(ticks):
        state.tick += 1
        _reset_market_stats(state)
        produce_resources(state)
        process_buildings(state)
        execute_trade(state)
        compute_demand_intents(state)
        update_prices(state)
        allocate_and_consume(state)
        apply_finance(state)
        run_ai(state)


def _reset_market_stats(state: GameState) -> None:
    for market in state.markets.values():
        for good_state in market.goods.values():
            good_state.produced = 0.0
            good_state.demanded = 0.0
            good_state.bought = 0.0
            good_state.unmet = 0.0
            good_state.last_delta = 0.0
            good_state.traded_in = 0.0
            good_state.traded_out = 0.0
