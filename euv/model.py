"""Game state model: provinces, nations, armies, wars."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import data


@dataclass
class Province:
    pid: int
    name: str
    terrain: str
    culture: str
    owner: str                      # nation tag
    dev: int = 3
    buildings: list[str] = field(default_factory=list)
    cells: list[tuple[int, int]] = field(default_factory=list)
    center: tuple[int, int] = (0, 0)
    neighbors: set[int] = field(default_factory=set)
    coastal: bool = False
    # wartime state
    occupier: str | None = None     # tag of occupying nation, None = owner
    siege_progress: float = 0.0
    sieging: str | None = None      # tag currently sieging
    unrest: float = 0.0

    @property
    def fort_level(self) -> int:
        return 1 + (2 if "fort" in self.buildings else 0)

    def tax_income(self) -> float:
        mult = 1.0 + (data.BUILDINGS["farm"][4] if "farm" in self.buildings else 0)
        flat = data.BUILDINGS["market"][4] if "market" in self.buildings else 0
        income = self.dev * data.BASE_TAX_PER_DEV * mult + flat
        if self.occupier is not None:
            income *= 0.25
        return income

    def manpower_cap(self) -> float:
        mult = 1.0 + (data.BUILDINGS["barracks"][4]
                      if "barracks" in self.buildings else 0)
        return self.dev * data.MANPOWER_PER_DEV * mult

    def dev_cost(self) -> int:
        terr_mult = data.TERRAIN[self.terrain][4]
        return int(data.DEV_COST_BASE * terr_mult * (1 + 0.25 * (self.dev - 3)))


@dataclass
class Army:
    aid: int
    owner: str
    location: int                  # province id
    regiments: int
    men: int
    morale: float = data.MORALE_BASE
    move_target: int | None = None  # set when ordered; resolved on tick
    name: str = ""
    general: int = 0                # battle dice bonus, 0 = no general
    general_name: str = ""
    reinforce: bool = True          # draw replacements from manpower

    @property
    def strength(self) -> float:
        return self.men / 1000.0


@dataclass
class War:
    wid: int
    attackers: list[str]
    defenders: list[str]
    cb_target: int | None          # claimed province id, None = no CB
    start: tuple[int, int]         # (year, month)
    # warscore from attacker leader's perspective, -100..100
    score: float = 0.0
    battles_score: float = 0.0     # capped portion from battles
    name: str = ""
    dom_months: int = 0            # consecutive months at total domination
    refusals: int = 0              # rejected offers (escalates AI demands)
    no_offers_until: int = 0       # abs month; cooldown after a refusal

    def side_of(self, tag: str) -> str | None:
        if tag in self.attackers:
            return "att"
        if tag in self.defenders:
            return "def"
        return None

    def enemies_of(self, tag: str) -> list[str]:
        side = self.side_of(tag)
        if side == "att":
            return self.defenders
        if side == "def":
            return self.attackers
        return []

    def score_for(self, tag: str) -> float:
        return self.score if tag in self.attackers else -self.score


@dataclass
class Nation:
    tag: str
    name: str
    culture: str
    color: int                     # palette index
    capital: int
    ruler: str = ""
    is_player: bool = False
    alive: bool = True
    # resources
    gold: float = 100.0
    manpower: float = 5000.0
    stability: int = 1
    prestige: float = 0.0
    war_exhaustion: float = 0.0
    # diplomacy: tag -> value
    opinions: dict[str, float] = field(default_factory=dict)
    ae: dict[str, float] = field(default_factory=dict)        # AE others hold vs us
    truces: dict[str, int] = field(default_factory=dict)      # tag -> abs month expiry
    allies: set[str] = field(default_factory=set)
    claims: set[int] = field(default_factory=set)             # province ids
    fabricating: tuple[int, int] | None = None                # (pid, months left)
    in_coalition_against: str | None = None
    last_war_month: int = 0        # abs month a war last started/ended

    def opinion_of(self, other: str) -> float:
        return self.opinions.get(other, 0.0)


class Game:
    """Top level mutable game state."""

    def __init__(self, seed: int = 7):
        self.seed = seed
        self.rng = random.Random(seed)
        self.year = data.START_YEAR
        self.month = 0                # 0-11
        self.provinces: dict[int, Province] = {}
        self.nations: dict[str, Nation] = {}
        self.armies: dict[int, Army] = {}
        self.wars: dict[int, War] = {}
        self.player: str = ""
        self.grid: list[list[int]] = []   # cell -> province id, -1 = sea
        self.straits: set[tuple[int, int]] = set()  # special sea crossings
        self.width = 0
        self.height = 0
        self.log: list[tuple[str, str]] = []   # (category, message)
        self.pending_events: list[dict] = []   # popups queued for the player
        self.missions: list[dict] = []         # player objectives
        self._next_army = 1
        self._next_war = 1
        self.game_over: str | None = None      # message when player eliminated

    # ------------------------------------------------------------- helpers

    @property
    def abs_month(self) -> int:
        return self.year * 12 + self.month

    @property
    def date_str(self) -> str:
        return f"{data.MONTHS[self.month]}, AE {self.year}"

    def say(self, category: str, msg: str):
        self.log.append((category, msg))
        if len(self.log) > 400:
            del self.log[:100]

    def provinces_of(self, tag: str) -> list[Province]:
        return [p for p in self.provinces.values() if p.owner == tag]

    def armies_of(self, tag: str) -> list[Army]:
        return [a for a in self.armies.values() if a.owner == tag]

    def total_dev(self, tag: str) -> int:
        return sum(p.dev for p in self.provinces_of(tag))

    def force_limit(self, tag: str) -> int:
        return data.FORCE_LIMIT_BASE + int(
            self.total_dev(tag) * data.FORCE_LIMIT_PER_DEV)

    def manpower_max(self, tag: str) -> float:
        return sum(p.manpower_cap() for p in self.provinces_of(tag))

    def at_war_with(self, a: str, b: str) -> bool:
        return any(w.side_of(a) and w.side_of(b)
                   and w.side_of(a) != w.side_of(b)
                   for w in self.wars.values())

    def wars_of(self, tag: str) -> list[War]:
        return [w for w in self.wars.values() if w.side_of(tag)]

    def enemies_of(self, tag: str) -> set[str]:
        out: set[str] = set()
        for w in self.wars_of(tag):
            out.update(w.enemies_of(tag))
        return out

    def truce_between(self, a: str, b: str) -> bool:
        return self.nations[a].truces.get(b, 0) > self.abs_month

    def nation_strength(self, tag: str) -> float:
        """Rough military power score used by AI."""
        n = self.nations[tag]
        men = sum(a.men for a in self.armies_of(tag))
        return men + n.manpower * 0.5 + n.gold * 8

    def war_name(self, attacker: str, defender: str) -> str:
        return (f"{self.nations[attacker].name}-"
                f"{self.nations[defender].name} War")

    def new_army(self, owner: str, location: int, regiments: int,
                 men: int | None = None) -> Army:
        a = Army(self._next_army, owner, location, regiments,
                 men if men is not None else regiments * data.RECRUIT_MANPOWER)
        a.name = f"{self.nations[owner].name} Army #{self._next_army}"
        self._next_army += 1
        self.armies[a.aid] = a
        return a

    def new_war(self, attackers: list[str], defenders: list[str],
                cb_target: int | None) -> War:
        w = War(self._next_war, attackers, defenders, cb_target,
                (self.year, self.month))
        w.name = self.war_name(attackers[0], defenders[0])
        self._next_war += 1
        self.wars[w.wid] = w
        return w
