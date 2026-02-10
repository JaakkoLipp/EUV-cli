"""Command parsing and dispatch for the TUI."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Optional

from eco_sim.sim.engine import tick
from eco_sim.sim.state import BuildingInstance, GameState, TradeRoute, add_event
from eco_sim.tui.render import status_text
from eco_sim.util.ids import next_id
from eco_sim.util.math import clamp


@dataclass
class CommandResult:
    message: str
    error: bool = False
    help_text: str = ""
    output_text: str = ""
    selected_market_id: Optional[str] = None
    selected_country_id: Optional[str] = None
    quit_app: bool = False


def execute_command(
    state: GameState,
    command_text: str,
    selected_country_id: str,
    selected_market_id: str,
) -> CommandResult:
    parts = shlex.split(command_text)
    if not parts:
        return CommandResult(message="")

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "tick":
        ticks = _parse_int(args, default=1)
        if ticks <= 0:
            return CommandResult(message="Tick count must be positive", error=True)
        tick(state, ticks)
        add_event(state, "tick", f"Advanced {ticks} ticks")
        return CommandResult(message=f"Advanced {ticks} ticks")

    if cmd == "status":
        text = status_text(state, selected_country_id)
        return CommandResult(message=text, output_text=text)

    if cmd == "markets":
        lines = ["Markets:"]
        for market_id in sorted(state.markets.keys()):
            market = state.markets[market_id]
            lines.append(f"- {market.id} ({market.name})")
        text = "\n".join(lines)
        return CommandResult(message=text, output_text=text)

    if cmd == "market":
        if not args:
            return CommandResult(message="Usage: market <id>", error=True)
        market_id = args[0]
        if market_id not in state.markets:
            return CommandResult(message="Unknown market id", error=True)
        market = state.markets[market_id]
        return CommandResult(
            message=f"Selected market {market_id}",
            output_text=f"Selected market {market_id}",
            selected_market_id=market_id,
            selected_country_id=market.country_id,
        )

    if cmd == "country":
        if not args:
            return CommandResult(message="Usage: country <id>", error=True)
        country_id = args[0]
        country = state.countries.get(country_id)
        if country is None:
            return CommandResult(message="Unknown country id", error=True)
        return CommandResult(
            message=f"Selected country {country_id}",
            output_text=f"Selected country {country_id}",
            selected_country_id=country_id,
            selected_market_id=country.market_id,
        )

    if cmd == "goods":
        lines = ["Goods:"]
        for good_id, good in sorted(state.goods.items()):
            lines.append(f"- {good_id} ({good.name})")
        text = "\n".join(lines)
        return CommandResult(message=text, output_text=text)

    if cmd == "regions":
        lines = ["Regions:"]
        for region_id in sorted(state.regions.keys()):
            region = state.regions[region_id]
            owner = region.owner_id or "neutral"
            lines.append(f"- {region.id} ({region.name}) owner {owner}")
        text = "\n".join(lines)
        return CommandResult(message=text, output_text=text)

    if cmd == "buildings":
        lines = ["Buildings:"]
        for building_id in sorted(state.buildings.keys()):
            building = state.buildings[building_id]
            region = state.regions.get(building.region_id)
            region_label = region.name if region else building.region_id
            lines.append(
                f"- {building.id} {building.type_id} region {region_label} "
                f"lvl {building.level} {'on' if building.enabled else 'off'}"
            )
        text = "\n".join(lines)
        return CommandResult(message=text, output_text=text)

    if cmd == "region":
        if not args:
            return CommandResult(message="Usage: region <id>", error=True)
        region_id = args[0]
        region = state.regions.get(region_id)
        if region is None:
            return CommandResult(message="Unknown region id", error=True)
        outputs = ", ".join(f"{k}:{v:.1f}" for k, v in region.outputs.items())
        buildings = ", ".join(region.building_ids) if region.building_ids else "None"
        text = f"{region.id} owner {region.owner_id} outputs [{outputs}] buildings [{buildings}]"
        return CommandResult(message=text, output_text=text)

    if cmd == "build":
        if len(args) < 2:
            return CommandResult(message="Usage: build <region_id> <building_type> [level]", error=True)
        region_id = args[0]
        building_type_id = args[1]
        level = _parse_int(args[2:], default=1)
        region = state.regions.get(region_id)
        if region is None:
            return CommandResult(message="Unknown region id", error=True)
        if region.owner_id != selected_country_id:
            return CommandResult(message="Region not owned by selected country", error=True)
        if building_type_id not in state.building_types:
            return CommandResult(message="Unknown building type", error=True)
        if level <= 0:
            return CommandResult(message="Level must be positive", error=True)

        country = state.countries[selected_country_id]
        building_type = state.building_types[building_type_id]
        if country.treasury < building_type.cost:
            return CommandResult(message="Insufficient treasury for build", error=True)

        building_id = next_id(state, "bld")
        state.buildings[building_id] = BuildingInstance(
            id=building_id,
            type_id=building_type_id,
            region_id=region_id,
            level=level,
            capacity_multiplier=1.0,
            enabled=True,
        )
        region.building_ids.append(building_id)
        country.treasury -= building_type.cost
        add_event(state, "build", f"Built {building_type_id} in {region_id}")
        text = f"Built {building_type_id} ({building_id})"
        return CommandResult(message=text, output_text=text)

    if cmd == "toggle_building":
        if not args:
            return CommandResult(message="Usage: toggle_building <building_id>", error=True)
        building_id = args[0]
        building = state.buildings.get(building_id)
        if building is None:
            return CommandResult(message="Unknown building id", error=True)
        building.enabled = not building.enabled
        status = "enabled" if building.enabled else "disabled"
        add_event(state, "build", f"Toggled {building_id} {status}")
        text = f"Building {building_id} {status}"
        return CommandResult(message=text, output_text=text)

    if cmd == "route" and args and args[0] == "add":
        if len(args) < 7:
            return CommandResult(
                message="Usage: route add <src_market> <dst_market> <good> <cap> <transport_cost> <tariff_rate>",
                error=True,
            )
        src_market, dst_market, good_id = args[1], args[2], args[3]
        if src_market not in state.markets or dst_market not in state.markets:
            return CommandResult(message="Unknown market id", error=True)
        if good_id not in state.goods:
            return CommandResult(message="Unknown good id", error=True)
        cap = _parse_float(args[4], 0.0)
        cost = _parse_float(args[5], 0.0)
        tariff = _parse_float(args[6], 0.0)
        if cap <= 0.0:
            return CommandResult(message="Capacity must be positive", error=True)

        route_id = next_id(state, "route")
        state.routes[route_id] = TradeRoute(
            id=route_id,
            src_market_id=src_market,
            dst_market_id=dst_market,
            good_id=good_id,
            capacity=cap,
            tariff=max(0.0, tariff),
            cost=max(0.0, cost),
        )
        add_event(state, "trade", f"Added route {route_id}")
        text = f"Added route {route_id}"
        return CommandResult(message=text, output_text=text)

    if cmd == "annex":
        if not args:
            return CommandResult(message="Usage: annex <region_id>", error=True)
        region_id = args[0]
        region = state.regions.get(region_id)
        if region is None:
            return CommandResult(message="Unknown region id", error=True)
        if region.owner_id is not None:
            return CommandResult(message="Region already owned", error=True)
        country = state.countries[selected_country_id]
        if country.treasury < state.annex_cost:
            return CommandResult(message="Insufficient treasury to annex", error=True)
        region.owner_id = selected_country_id
        region.market_id = country.market_id
        country.region_ids.append(region_id)
        country.treasury -= state.annex_cost
        add_event(state, "annex", f"Annexed {region_id} for {country.name}")
        text = f"Annexed {region_id}"
        return CommandResult(message=text, output_text=text)

    if cmd == "set" and len(args) >= 3 and args[0] == "tax":
        country_id = args[1]
        rate = _parse_float(args[2], 0.0)
        country = state.countries.get(country_id)
        if country is None:
            return CommandResult(message="Unknown country id", error=True)
        country.tax_rate = clamp(rate, 0.0, 1.0)
        add_event(state, "policy", f"Set tax for {country.name} to {country.tax_rate:.2f}")
        text = f"Tax set to {country.tax_rate:.2f}"
        return CommandResult(message=text, output_text=text)

    if cmd == "ai" and args:
        value = args[0].lower()
        if value not in {"on", "off"}:
            return CommandResult(message="Usage: ai on|off", error=True)
        state.ai_enabled = value == "on"
        add_event(state, "ai", f"AI set to {value}")
        text = f"AI set to {value}"
        return CommandResult(message=text, output_text=text)

    if cmd == "help":
        return CommandResult(message="Help", help_text=_help_text(), output_text=_help_text())

    if cmd == "quit":
        return CommandResult(message="Quitting", quit_app=True)

    return CommandResult(message="Unknown command", error=True)


def _parse_int(args: list[str], default: int) -> int:
    if not args:
        return default
    try:
        return int(args[0])
    except ValueError:
        return default


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except ValueError:
        return default


def _help_text() -> str:
    return "\n".join(
        [
            "Commands:",
            "- tick [n]",
            "- status",
            "- markets | market <id>",
            "- country <country_id>",
            "- goods",
            "- regions | region <id>",
            "- buildings",
            "- build <region_id> <building_type> [level]",
            "- toggle_building <building_id>",
            "- route add <src_market> <dst_market> <good> <cap> <transport_cost> <tariff_rate>",
            "- annex <region_id>",
            "- set tax <country_id> <rate>",
            "- ai on|off",
            "- help",
            "- quit",
        ]
    )
