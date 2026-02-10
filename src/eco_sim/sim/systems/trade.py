"""Inter-market trade system."""

from __future__ import annotations

from eco_sim.sim.state import GameState, add_event
from eco_sim.util.math import clamp


def execute_trade(state: GameState) -> None:
    for route_id in sorted(state.routes.keys()):
        route = state.routes[route_id]
        src_market = state.markets[route.src_market_id]
        dst_market = state.markets[route.dst_market_id]
        src_good = src_market.goods[route.good_id]
        dst_good = dst_market.goods[route.good_id]

        tariff_cost = route.tariff * dst_good.price
        effective_src = src_good.price + route.cost + tariff_cost
        price_spread = dst_good.price - effective_src
        if price_spread <= 0.0:
            route.last_moved = 0.0
            route.last_profit = 0.0
            route.last_tariff = 0.0
            continue

        move_factor = clamp(price_spread / max(1.0, dst_good.price), 0.0, 1.0)
        target_move = route.capacity * move_factor
        reserve = src_good.stock * 0.1
        available = max(0.0, src_good.stock - reserve)
        moved = min(target_move, available)
        if moved <= 0.0:
            route.last_moved = 0.0
            route.last_profit = 0.0
            route.last_tariff = 0.0
            continue

        src_good.stock -= moved
        if src_good.stock < 0.0:
            moved += src_good.stock
            src_good.stock = 0.0
        if moved <= 0.0:
            route.last_moved = 0.0
            route.last_profit = 0.0
            route.last_tariff = 0.0
            continue
        dst_good.stock += moved
        src_good.traded_out += moved
        dst_good.traded_in += moved
        route.last_moved = moved
        route.last_profit = moved * price_spread
        route.last_tariff = moved * tariff_cost

        dst_country = state.countries[state.markets[route.dst_market_id].country_id]
        dst_country.treasury += route.last_tariff

        add_event(
            state,
            "trade",
            f"Route {route.id} moved {moved:.2f} {route.good_id}",
            {"route_id": route.id, "good_id": route.good_id},
        )
