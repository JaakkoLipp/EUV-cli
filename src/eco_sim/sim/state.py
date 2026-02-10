"""Data model for the simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

GoodId = str
BuildingTypeId = str
BuildingId = str
RegionId = str
MarketId = str
CountryId = str
PopId = str
TradeRouteId = str


@dataclass(frozen=True)
class GoodDefinition:
    id: GoodId
    name: str
    base_price: float
    price_k: float
    min_price_factor: float
    max_price_factor: float


@dataclass
class MarketGoodState:
    price: float
    stock: float
    base_price: float
    price_k: float
    min_price: float
    max_price: float
    last_delta: float = 0.0
    produced: float = 0.0
    demanded: float = 0.0
    bought: float = 0.0
    unmet: float = 0.0
    traded_in: float = 0.0
    traded_out: float = 0.0


@dataclass
class Market:
    id: MarketId
    name: str
    country_id: CountryId
    goods: Dict[GoodId, MarketGoodState]


@dataclass
class Region:
    id: RegionId
    name: str
    owner_id: Optional[CountryId]
    market_id: Optional[MarketId]
    outputs: Dict[GoodId, float]
    building_ids: List[BuildingId] = field(default_factory=list)


@dataclass(frozen=True)
class BuildingType:
    id: BuildingTypeId
    name: str
    inputs: Dict[GoodId, float]
    outputs: Dict[GoodId, float]
    base_capacity: float
    cost: float
    upkeep: float


@dataclass
class BuildingInstance:
    id: BuildingId
    type_id: BuildingTypeId
    region_id: RegionId
    level: int = 1
    capacity_multiplier: float = 1.0
    enabled: bool = True


@dataclass
class Pop:
    id: PopId
    country_id: CountryId
    size: float
    income_per_capita: float
    cash: float
    needs: Dict[GoodId, float]
    priority: List[GoodId]
    satisfaction: Dict[GoodId, float] = field(default_factory=dict)
    satisfaction_avg: float = 1.0


@dataclass
class Country:
    id: CountryId
    name: str
    market_id: MarketId
    treasury: float
    tax_rate: float
    region_ids: List[RegionId] = field(default_factory=list)
    pop_ids: List[PopId] = field(default_factory=list)


@dataclass
class TradeRoute:
    id: TradeRouteId
    src_market_id: MarketId
    dst_market_id: MarketId
    good_id: GoodId
    capacity: float
    tariff: float
    cost: float
    last_moved: float = 0.0
    last_profit: float = 0.0
    last_tariff: float = 0.0


@dataclass
class Event:
    type: str
    message: str
    tick: int
    payload: Dict[str, str] = field(default_factory=dict)


@dataclass
class GameState:
    tick: int
    goods: Dict[GoodId, GoodDefinition]
    building_types: Dict[BuildingTypeId, BuildingType]
    markets: Dict[MarketId, Market]
    regions: Dict[RegionId, Region]
    buildings: Dict[BuildingId, BuildingInstance]
    countries: Dict[CountryId, Country]
    pops: Dict[PopId, Pop]
    routes: Dict[TradeRouteId, TradeRoute]
    events: List[Event] = field(default_factory=list)
    id_counters: Dict[str, int] = field(default_factory=dict)
    annex_cost: float = 50.0
    ai_enabled: bool = False
    ai_countries: List[CountryId] = field(default_factory=list)
    ai_interval: int = 1


def add_event(state: GameState, event_type: str, message: str, payload: Optional[Dict[str, str]] = None) -> None:
    if payload is None:
        payload = {}
    state.events.append(Event(type=event_type, message=message, tick=state.tick, payload=payload))
    if len(state.events) > 200:
        state.events = state.events[-200:]
