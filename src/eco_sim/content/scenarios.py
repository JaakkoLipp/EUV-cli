"""Scenario setup."""

from __future__ import annotations

from eco_sim.content.buildings import get_building_types
from eco_sim.content.goods import get_goods
from eco_sim.sim.state import (
    BuildingInstance,
    Country,
    GameState,
    GoodDefinition,
    Market,
    MarketGoodState,
    Pop,
    Region,
    TradeRoute,
)


def default_scenario() -> GameState:
    goods = get_goods()
    building_types = get_building_types()

    markets = {
        "market_north": Market(
            id="market_north",
            name="North Market",
            country_id="country_north",
            goods=_make_market_goods(goods, price_bias={"grain": 0.85, "planks": 0.9}),
        ),
        "market_south": Market(
            id="market_south",
            name="South Market",
            country_id="country_south",
            goods=_make_market_goods(goods, price_bias={"grain": 1.15, "planks": 1.1}),
        ),
    }

    regions = {
        "north_forest": Region(
            id="north_forest",
            name="North Forest",
            owner_id="country_north",
            market_id="market_north",
            outputs={"logs": 5.0},
        ),
        "north_farm": Region(
            id="north_farm",
            name="North Farm",
            owner_id="country_north",
            market_id="market_north",
            outputs={"grain": 8.0},
        ),
        "south_forest": Region(
            id="south_forest",
            name="South Forest",
            owner_id="country_south",
            market_id="market_south",
            outputs={"logs": 3.0},
        ),
        "south_mine": Region(
            id="south_mine",
            name="South Mine",
            owner_id="country_south",
            market_id="market_south",
            outputs={"iron": 5.0},
        ),
        "south_farm": Region(
            id="south_farm",
            name="South Farm",
            owner_id="country_south",
            market_id="market_south",
            outputs={"grain": 5.0},
        ),
        "frontier_forest": Region(
            id="frontier_forest",
            name="Frontier Forest",
            owner_id=None,
            market_id=None,
            outputs={"logs": 7.0},
        ),
    }

    buildings = {
        "bld_north_mill": BuildingInstance(
            id="bld_north_mill",
            type_id="lumber_mill",
            region_id="north_forest",
            level=2,
        ),
        "bld_south_mill": BuildingInstance(
            id="bld_south_mill",
            type_id="lumber_mill",
            region_id="south_forest",
            level=1,
        ),
        "bld_south_tools": BuildingInstance(
            id="bld_south_tools",
            type_id="tool_workshop",
            region_id="south_mine",
            level=1,
        ),
    }
    regions["north_forest"].building_ids.append("bld_north_mill")
    regions["south_forest"].building_ids.append("bld_south_mill")
    regions["south_mine"].building_ids.append("bld_south_tools")

    pops = {
        "pop_north": Pop(
            id="pop_north",
            country_id="country_north",
            size=100.0,
            income_per_capita=1.6,
            cash=120.0,
            needs={"grain": 0.08, "tools": 0.01},
            priority=["grain", "tools"],
        ),
        "pop_south": Pop(
            id="pop_south",
            country_id="country_south",
            size=120.0,
            income_per_capita=1.4,
            cash=110.0,
            needs={"grain": 0.1, "tools": 0.015},
            priority=["grain", "tools"],
        ),
    }

    countries = {
        "country_north": Country(
            id="country_north",
            name="Northland",
            market_id="market_north",
            treasury=80.0,
            tax_rate=0.1,
            region_ids=["north_forest", "north_farm"],
            pop_ids=["pop_north"],
        ),
        "country_south": Country(
            id="country_south",
            name="Southport",
            market_id="market_south",
            treasury=70.0,
            tax_rate=0.12,
            region_ids=["south_forest", "south_mine", "south_farm"],
            pop_ids=["pop_south"],
        ),
    }

    routes = {
        "route_grain": TradeRoute(
            id="route_grain",
            src_market_id="market_north",
            dst_market_id="market_south",
            good_id="grain",
            capacity=8.0,
            tariff=0.05,
            cost=0.2,
        ),
        "route_planks": TradeRoute(
            id="route_planks",
            src_market_id="market_north",
            dst_market_id="market_south",
            good_id="planks",
            capacity=6.0,
            tariff=0.05,
            cost=0.2,
        ),
    }

    state = GameState(
        tick=0,
        goods=goods,
        building_types=building_types,
        markets=markets,
        regions=regions,
        buildings=buildings,
        countries=countries,
        pops=pops,
        routes=routes,
        events=[],
        id_counters={"bld": 3, "route": 2},
        annex_cost=50.0,
        ai_enabled=True,
        ai_countries=["country_north", "country_south"],
        ai_interval=2,
    )

    markets["market_north"].goods["grain"].stock = 30.0
    markets["market_north"].goods["logs"].stock = 10.0
    markets["market_south"].goods["iron"].stock = 8.0

    return state


def _make_market_goods(
    goods: dict[str, GoodDefinition],
    price_bias: dict[str, float] | None = None,
) -> dict[str, MarketGoodState]:
    if price_bias is None:
        price_bias = {}
    market_goods: dict[str, MarketGoodState] = {}
    for good_id, good in goods.items():
        base_price = good.base_price
        bias = price_bias.get(good_id, 1.0)
        price = base_price * bias
        min_price = base_price * good.min_price_factor
        max_price = base_price * good.max_price_factor
        market_goods[good_id] = MarketGoodState(
            price=price,
            stock=0.0,
            base_price=base_price,
            price_k=good.price_k,
            min_price=min_price,
            max_price=max_price,
        )
    return market_goods
