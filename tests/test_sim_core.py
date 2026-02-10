"""Minimal sim core tests."""

from __future__ import annotations

from eco_sim.content.scenarios import default_scenario
from eco_sim.sim.engine import tick
from eco_sim.sim.systems.trade import execute_trade


def test_tick_determinism() -> None:
    state_a = default_scenario()
    state_b = default_scenario()
    state_a.ai_enabled = False
    state_b.ai_enabled = False
    tick(state_a, 5)
    tick(state_b, 5)

    for market_id in state_a.markets.keys():
        market_a = state_a.markets[market_id]
        market_b = state_b.markets[market_id]
        for good_id in market_a.goods.keys():
            good_a = market_a.goods[good_id]
            good_b = market_b.goods[good_id]
            assert good_a.price == good_b.price
            assert good_a.stock == good_b.stock


def test_no_negative_stock_or_cash() -> None:
    state = default_scenario()
    state.ai_enabled = False
    tick(state, 10)

    for market in state.markets.values():
        for good_state in market.goods.values():
            assert good_state.stock >= 0.0

    for pop in state.pops.values():
        assert pop.cash >= 0.0

    for country in state.countries.values():
        assert country.treasury >= 0.0


def test_price_clamp() -> None:
    state = default_scenario()
    state.ai_enabled = False
    tick(state, 3)
    for market in state.markets.values():
        for good_state in market.goods.values():
            assert good_state.min_price <= good_state.price <= good_state.max_price


def test_trade_capacity_respected() -> None:
    state = default_scenario()
    state.ai_enabled = False
    route = state.routes["route_grain"]
    src_market = state.markets[route.src_market_id]
    src_market.goods[route.good_id].stock = 50.0
    tick(state, 1)
    assert route.last_moved <= route.capacity


def test_trade_goods_conservation() -> None:
    state = default_scenario()
    state.ai_enabled = False
    good_id = "grain"
    total_before = sum(market.goods[good_id].stock for market in state.markets.values())
    execute_trade(state)
    total_after = sum(market.goods[good_id].stock for market in state.markets.values())
    assert total_before == total_after


def test_ai_does_not_overspend() -> None:
    state = default_scenario()
    state.ai_enabled = True
    state.ai_interval = 1
    ai_country = state.countries[state.ai_countries[0]]
    ai_country.treasury = 0.0
    tick(state, 1)
    assert ai_country.treasury >= 0.0
