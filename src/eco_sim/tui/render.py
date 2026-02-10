"""Rendering helpers for the Textual UI."""

from __future__ import annotations

from eco_sim.sim.state import GameState
from eco_sim.util.math import safe_div


def header_text(state: GameState, country_id: str) -> str:
    country = state.countries.get(country_id)
    if country is None:
        return f"Tick {state.tick}"
    satisfaction = _country_satisfaction(state, country_id)
    return (
        f"Tick {state.tick} | Country: {country.name} | "
        f"Treasury: {country.treasury:.2f} | Tax: {country.tax_rate:.2f} | "
        f"Satisfaction: {satisfaction:.2f}"
    )


def market_rows(state: GameState, market_id: str) -> list[tuple[str, str, str, str, str, str, str, str]]:
    market = state.markets[market_id]
    satisfaction_by_good = _market_satisfaction(state, market_id)
    rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    for good_id in sorted(market.goods.keys()):
        good_state = market.goods[good_id]
        trade_net = good_state.traded_in - good_state.traded_out
        satisfaction = satisfaction_by_good.get(good_id, 1.0)
        rows.append(
            (
                good_id,
                f"{good_state.price:.2f}",
                f"{good_state.stock:.2f}",
                f"{good_state.produced:.2f}",
                f"{good_state.demanded:.2f}",
                f"{good_state.bought:.2f}",
                f"{trade_net:+.2f}",
                f"{satisfaction:.2f}",
            )
        )
    return rows


def regions_text(state: GameState, country_id: str) -> str:
    country = state.countries.get(country_id)
    if country is None:
        return ""
    lines = ["Regions:"]
    for region_id in country.region_ids:
        region = state.regions[region_id]
        outputs = ", ".join(f"{k}:{v:.1f}" for k, v in region.outputs.items())
        buildings = ", ".join(region.building_ids) if region.building_ids else "None"
        lines.append(f"- {region.id} ({region.name}) outputs [{outputs}] buildings [{buildings}]")
    return "\n".join(lines)


def trade_text(state: GameState) -> str:
    lines = ["Trade Routes:"]
    for route_id in sorted(state.routes.keys()):
        route = state.routes[route_id]
        lines.append(
            f"- {route.id} {route.src_market_id}->{route.dst_market_id} {route.good_id} "
            f"cap {route.capacity:.1f} moved {route.last_moved:.1f} "
            f"profit {route.last_profit:.2f} tariff {route.last_tariff:.2f}"
        )
    return "\n".join(lines)


def log_text(state: GameState, limit: int = 8) -> str:
    lines = ["Events:"]
    for event in state.events[-limit:]:
        lines.append(f"- T{event.tick} [{event.type}] {event.message}")
    return "\n".join(lines)


def footer_text(message: str, error: str) -> str:
    base = "Keys: q quit | t tick | T tick 10 | tab cycle market"
    if error:
        return f"{base} | Error: {error}"
    if message:
        return f"{base} | {message}"
    return base


def status_text(state: GameState, country_id: str) -> str:
    country = state.countries.get(country_id)
    if country is None:
        return "No country selected"
    satisfaction = _country_satisfaction(state, country_id)
    return (
        f"{country.name} treasury {country.treasury:.2f} tax {country.tax_rate:.2f} "
        f"satisfaction {satisfaction:.2f} regions {len(country.region_ids)}"
    )


def _country_satisfaction(state: GameState, country_id: str) -> float:
    country = state.countries[country_id]
    total = 0.0
    count = 0
    for pop_id in country.pop_ids:
        total += state.pops[pop_id].satisfaction_avg
        count += 1
    return safe_div(total, float(count), 1.0)


def _market_satisfaction(state: GameState, market_id: str) -> dict[str, float]:
    market = state.markets[market_id]
    country = state.countries[market.country_id]
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for pop_id in country.pop_ids:
        pop = state.pops[pop_id]
        for good_id, value in pop.satisfaction.items():
            totals[good_id] = totals.get(good_id, 0.0) + value
            counts[good_id] = counts.get(good_id, 0) + 1
    averages: dict[str, float] = {}
    for good_id, total in totals.items():
        averages[good_id] = safe_div(total, float(counts.get(good_id, 1)), 1.0)
    return averages
