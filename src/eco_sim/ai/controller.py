"""Simple deterministic AI controller."""

from __future__ import annotations

from eco_sim.ai.heuristics import region_value, shortage_scores
from eco_sim.sim.state import BuildingInstance, GameState, TradeRoute, add_event
from eco_sim.util.ids import next_id
from eco_sim.util.math import clamp


def run_ai(state: GameState) -> None:
    if not state.ai_enabled or state.ai_interval <= 0:
        return
    if state.tick % state.ai_interval != 0:
        return
    for country_id in state.ai_countries:
        if country_id not in state.countries:
            continue
        _maybe_build(state, country_id)
        _maybe_trade(state, country_id)
        _maybe_annex(state, country_id)


def _maybe_build(state: GameState, country_id: str) -> None:
    country = state.countries[country_id]
    market = state.markets[country.market_id]
    scores = shortage_scores(state, country_id)
    if not scores:
        return
    target_good = max(scores, key=scores.get)
    if scores[target_good] < 1.2:
        return

    candidates = []
    for building_type in state.building_types.values():
        if target_good in building_type.outputs:
            candidates.append(building_type)
    if not candidates:
        return

    building_type = min(candidates, key=lambda item: item.cost)
    if country.treasury < building_type.cost:
        return

    if not country.region_ids:
        return
    region_id = country.region_ids[0]

    building_id = next_id(state, "bld")
    state.buildings[building_id] = BuildingInstance(
        id=building_id,
        type_id=building_type.id,
        region_id=region_id,
        level=1,
        capacity_multiplier=1.0,
        enabled=True,
    )
    state.regions[region_id].building_ids.append(building_id)
    country.treasury -= building_type.cost

    add_event(
        state,
        "ai_build",
        f"{country.name} built {building_type.id} in {region_id}",
        {"country_id": country_id, "building_id": building_id},
    )


def _maybe_trade(state: GameState, country_id: str) -> None:
    country = state.countries[country_id]
    market = state.markets[country.market_id]
    other_markets = [m for m in state.markets.values() if m.id != market.id]
    if not other_markets:
        return

    best: tuple[str, str, str, float] | None = None
    best_profit = 0.0
    for good_id, good_state in market.goods.items():
        for other in other_markets:
            other_good = other.goods[good_id]
            import_cost = other_good.price + 0.2 + (0.05 * good_state.price)
            profit = good_state.price - import_cost
            if profit > 0.5 and profit > best_profit:
                best = (other.id, market.id, good_id, profit)
                best_profit = profit

            export_cost = good_state.price + 0.2 + (0.05 * other_good.price)
            export_profit = other_good.price - export_cost
            if export_profit > 0.5 and export_profit > best_profit:
                best = (market.id, other.id, good_id, export_profit)
                best_profit = export_profit

    if best is None:
        return

    src_market_id, dst_market_id, good_id, _profit = best
    for route in state.routes.values():
        if (
            route.src_market_id == src_market_id
            and route.dst_market_id == dst_market_id
            and route.good_id == good_id
        ):
            return

    route_id = next_id(state, "route")
    state.routes[route_id] = TradeRoute(
        id=route_id,
        src_market_id=src_market_id,
        dst_market_id=dst_market_id,
        good_id=good_id,
        capacity=8.0,
        tariff=0.05,
        cost=0.2,
    )

    add_event(
        state,
        "ai_trade",
        f"{country.name} added route {route_id} for {good_id}",
        {"country_id": country_id, "route_id": route_id},
    )


def _maybe_annex(state: GameState, country_id: str) -> None:
    country = state.countries[country_id]
    if country.treasury < state.annex_cost:
        return

    neutral = [r for r in state.regions.values() if r.owner_id is None]
    if not neutral:
        return

    best_region = max(neutral, key=lambda region: region_value(state, region.id))
    if region_value(state, best_region.id) < 10.0:
        return

    best_region.owner_id = country_id
    best_region.market_id = country.market_id
    country.region_ids.append(best_region.id)
    country.treasury = clamp(country.treasury - state.annex_cost, 0.0, country.treasury)

    add_event(
        state,
        "ai_annex",
        f"{country.name} annexed {best_region.id}",
        {"country_id": country_id, "region_id": best_region.id},
    )
