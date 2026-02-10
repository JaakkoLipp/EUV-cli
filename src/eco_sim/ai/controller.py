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
        _maybe_tax(state, country_id)
        _maybe_tariffs(state, country_id)
        _maybe_build(state, country_id)
        _maybe_trade(state, country_id)
        _maybe_annex(state, country_id)


def _maybe_tax(state: GameState, country_id: str) -> None:
    country = state.countries[country_id]
    satisfaction = _country_satisfaction(state, country_id)
    target = country.tax_rate
    if satisfaction < 0.75:
        target = country.tax_rate - 0.02
    elif satisfaction > 0.95 and country.treasury < 120.0:
        target = country.tax_rate + 0.02
    target = clamp(target, 0.05, 0.35)
    if abs(target - country.tax_rate) >= 0.005:
        country.tax_rate = target
        add_event(
            state,
            "ai_tax",
            f"{country.name} set tax to {country.tax_rate:.2f}",
            {"country_id": country_id},
        )


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
    for good_id in market.goods.keys():
        best = None
        best_profit = 0.0
        for other in other_markets:
            src_good = other.goods[good_id]
            dst_good = market.goods[good_id]
            import_cost = src_good.price + 0.2 + (0.05 * dst_good.price)
            profit = dst_good.price - import_cost
            if profit > 0.2 and profit > best_profit:
                best = (other.id, market.id, profit)
                best_profit = profit

            src_good = market.goods[good_id]
            dst_good = other.goods[good_id]
            export_cost = src_good.price + 0.2 + (0.05 * dst_good.price)
            export_profit = dst_good.price - export_cost
            if export_profit > 0.2 and export_profit > best_profit:
                best = (market.id, other.id, export_profit)
                best_profit = export_profit

        if best is None:
            continue

        src_market_id, dst_market_id, _profit = best
        existing = None
        for route in state.routes.values():
            if (
                route.good_id == good_id
                and (route.src_market_id == market.id or route.dst_market_id == market.id)
            ):
                existing = route
                break

        if existing and existing.src_market_id == src_market_id and existing.dst_market_id == dst_market_id:
            continue

        if existing:
            existing.src_market_id = src_market_id
            existing.dst_market_id = dst_market_id
            add_event(
                state,
                "ai_trade",
                f"{country.name} retargeted {existing.id} for {good_id}",
                {"country_id": country_id, "route_id": existing.id},
            )
            continue

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


def _maybe_tariffs(state: GameState, country_id: str) -> None:
    country = state.countries[country_id]
    satisfaction = _country_satisfaction(state, country_id)
    for route in state.routes.values():
        dst_market = state.markets[route.dst_market_id]
        if dst_market.country_id != country_id:
            continue
        good_state = dst_market.goods[route.good_id]
        demand = max(0.01, good_state.demanded)
        supply = max(0.01, good_state.stock)
        shortage_ratio = demand / supply

        target = route.tariff
        if shortage_ratio > 1.2:
            target = route.tariff - 0.02
        elif shortage_ratio < 0.8:
            target = route.tariff + 0.01
        elif satisfaction > 0.95 and country.treasury < 120.0:
            target = route.tariff + 0.005

        target = clamp(target, 0.0, 0.2)
        if abs(target - route.tariff) >= 0.001:
            route.tariff = target
            add_event(
                state,
                "ai_tariff",
                f"{country.name} set tariff on {route.id} to {route.tariff:.2f}",
                {"country_id": country_id, "route_id": route.id},
            )


def _country_satisfaction(state: GameState, country_id: str) -> float:
    country = state.countries[country_id]
    total = 0.0
    count = 0
    for pop_id in country.pop_ids:
        total += state.pops[pop_id].satisfaction_avg
        count += 1
    if count == 0:
        return 1.0
    return total / float(count)
