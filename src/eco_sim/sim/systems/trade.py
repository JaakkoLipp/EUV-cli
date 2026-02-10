"""Inter-market trade system."""

from __future__ import annotations

from eco_sim.sim.state import GameState, add_event


def execute_trade(state: GameState) -> None:
    for route_id in sorted(state.routes.keys()):
        route = state.routes[route_id]
        src_market = state.markets[route.src_market_id]
        dst_market = state.markets[route.dst_market_id]
        src_good = src_market.goods[route.good_id]
        dst_good = dst_market.goods[route.good_id]

        tariff_cost = route.tariff * dst_good.price
        profit_per_unit = dst_good.price - src_good.price - route.cost - tariff_cost
        if profit_per_unit <= 0.0:
            route.last_moved = 0.0
            route.last_profit = 0.0
            continue

        moved = min(route.capacity, src_good.stock)
        if moved <= 0.0:
            route.last_moved = 0.0
            route.last_profit = 0.0
            continue

        src_good.stock -= moved
        dst_good.stock += moved
        route.last_moved = moved
        route.last_profit = moved * profit_per_unit

        add_event(
            state,
            "trade",
            f"Route {route.id} moved {moved:.2f} {route.good_id}",
            {"route_id": route.id, "good_id": route.good_id},
        )
