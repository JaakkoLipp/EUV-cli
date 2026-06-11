"""Procedural-but-deterministic world generation for the continent of Eryndor.

A hand-drawn landmass mask is partitioned into provinces by flood fill from
spread-out seed points, grouped into nations, and flavoured with terrain,
cultures and names. The same seed always produces the same world.
"""
from __future__ import annotations

import random
from collections import deque

from . import data
from .model import Game, Nation, Province

# 60 x 22 cells. '#' land, '.' sea. Hand-shaped continent.
LAND_MASK = [
    "............................................................",
    "......####......####################........###.............",
    "....########..########################....######............",
    "...#########################################......##........",
    "...###########################################..####........",
    "....#################################################.......",
    ".....###############################################........",
    "......#########...###################################.......",
    "....########.......##################################.......",
    "...#########......###################################.......",
    "..##########....######################################......",
    "..###########..########################################.....",
    "...#####################################################....",
    "....####################################################....",
    ".....##################################################.....",
    "....##################################################......",
    "...#######..########################################........",
    "..######......####################################..........",
    "..#####.........###############################.............",
    "...###...####.....########################..#####...........",
    "..........######.....##############.........#######.........",
    "............................................................",
]

NATION_SIZES = [6, 6, 5, 5, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2]


def _land_cells(mask: list[str]) -> list[tuple[int, int]]:
    return [(x, y) for y, row in enumerate(mask)
            for x, ch in enumerate(row) if ch == "#"]


def _farthest_point_seeds(cells: list[tuple[int, int]], n: int,
                          rng: random.Random) -> list[tuple[int, int]]:
    """Greedy farthest-point sampling for evenly spread seeds."""
    seeds = [rng.choice(cells)]
    dist = {c: _d2(c, seeds[0]) for c in cells}
    while len(seeds) < n:
        best = max(cells, key=lambda c: dist[c])
        seeds.append(best)
        for c in cells:
            d = _d2(c, best)
            if d < dist[c]:
                dist[c] = d
    return seeds


def _d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 * 4  # y weighted: cells are tall


def _flood_partition(cells, seeds):
    """Multi-source BFS: assign every land cell to nearest seed."""
    cellset = set(cells)
    owner = {}
    q = deque()
    for i, s in enumerate(seeds):
        owner[s] = i
        q.append(s)
    while q:
        x, y = q.popleft()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            c = (nx, ny)
            if c in cellset and c not in owner:
                owner[c] = owner[(x, y)]
                q.append(c)
    return owner


def _culture_for(x: int, y: int, w: int, h: int, rng: random.Random) -> str:
    fy, fx = y / h, x / w
    jitter = rng.uniform(-0.06, 0.06)
    if fy + jitter < 0.30:
        return "valdric"
    if fy + jitter > 0.74:
        return "qessari"
    if fx + jitter < 0.30:
        return "lyrian"
    if fx + jitter > 0.68:
        return "tervani"
    return "aurean"


def _terrain_for(culture: str, coastal: bool, y: int, h: int,
                 rng: random.Random) -> str:
    r = rng.random()
    if culture == "valdric":
        return "forest" if r < 0.45 else ("mountains" if r < 0.65 else
                                          ("hills" if r < 0.8 else "plains"))
    if culture == "qessari":
        return "desert" if r < 0.6 else ("hills" if r < 0.75 else "plains")
    if culture == "tervani":
        return "plains" if r < 0.5 else ("forest" if r < 0.7 else
                                         ("marsh" if r < 0.8 else "hills"))
    if culture == "lyrian":
        return "hills" if r < 0.35 else ("plains" if r < 0.65 else
                                         ("forest" if r < 0.85 else "marsh"))
    # aurean heartland
    return "plains" if r < 0.55 else ("hills" if r < 0.75 else
                                      ("forest" if r < 0.9 else "mountains"))


def _make_name(culture: str, used: set[str], rng: random.Random) -> str:
    c = data.CULTURES[culture]
    for _ in range(200):
        name = rng.choice(c["prov"]) + rng.choice(c["suff"])
        if name not in used:
            used.add(name)
            return name
    name = rng.choice(c["prov"]) + rng.choice(c["suff"]) + str(len(used))
    used.add(name)
    return name


def _make_tag(name: str, used: set[str]) -> str:
    base = "".join(ch for ch in name.upper() if ch.isalpha())
    for cand in (base[:3], base[0] + base[2:4], base[:2] + base[-1]):
        if len(cand) == 3 and cand not in used:
            used.add(cand)
            return cand
    for i in range(10):
        cand = base[:2] + str(i)
        if cand not in used:
            used.add(cand)
            return cand
    raise ValueError("tag space exhausted")


def generate(seed: int = 7) -> Game:
    g = Game(seed)
    rng = g.rng
    mask = LAND_MASK
    g.height, g.width = len(mask), len(mask[0])
    cells = _land_cells(mask)

    n_prov = 52
    seeds = _farthest_point_seeds(cells, n_prov, rng)
    owner = _flood_partition(cells, seeds)

    # group cells per province, drop tiny fragments into neighbours
    prov_cells: dict[int, list[tuple[int, int]]] = {}
    for c, pid in owner.items():
        prov_cells.setdefault(pid, []).append(c)

    g.grid = [[-1] * g.width for _ in range(g.height)]
    used_names: set[str] = set()
    for pid, pcells in sorted(prov_cells.items()):
        cx = sum(c[0] for c in pcells) / len(pcells)
        cy = sum(c[1] for c in pcells) / len(pcells)
        center = min(pcells, key=lambda c: (c[0]-cx)**2 + (c[1]-cy)**2)
        culture = _culture_for(center[0], center[1], g.width, g.height, rng)
        coastal = any(
            not (0 <= ny < g.height and 0 <= nx < len(mask[ny])
                 and mask[ny][nx] == "#")
            for x, y in pcells for nx, ny in ((x+1, y), (x-1, y),
                                              (x, y+1), (x, y-1)))
        terr = _terrain_for(culture, coastal, center[1], g.height, rng)
        p = Province(pid, _make_name(culture, used_names, rng), terr, culture,
                     owner="", dev=rng.randint(3, 7) + (1 if coastal else 0),
                     cells=sorted(pcells), center=center, coastal=coastal)
        g.provinces[pid] = p
        for x, y in pcells:
            g.grid[y][x] = pid

    # adjacency
    for y in range(g.height):
        for x in range(g.width):
            pid = g.grid[y][x]
            if pid < 0:
                continue
            for nx, ny in ((x+1, y), (x, y+1)):
                if 0 <= nx < g.width and 0 <= ny < g.height:
                    other = g.grid[ny][nx]
                    if other >= 0 and other != pid:
                        g.provinces[pid].neighbors.add(other)
                        g.provinces[other].neighbors.add(pid)

    _connect_islands(g)
    _assign_nations(g, rng)
    make_rebels(g)
    return g


def make_rebels(g: Game):
    """The special REB nation: owns nothing, hostile to all, gray.

    Also called on load for saves predating the rebel system.
    """
    if data.REBEL_TAG in g.nations:
        return
    g.nations[data.REBEL_TAG] = Nation(
        tag=data.REBEL_TAG, name="Rebels", culture="aurean",
        color=14, capital=min(g.provinces), ruler="The Mob",
        gold=0.0, manpower=0.0, stability=0)


def _connect_islands(g: Game):
    """Add strait crossings so every landmass joins the main graph."""
    pids = list(g.provinces)
    comp: dict[int, int] = {}
    cid = 0
    for pid in pids:
        if pid in comp:
            continue
        q = deque([pid])
        comp[pid] = cid
        while q:
            cur = q.popleft()
            for nb in g.provinces[cur].neighbors:
                if nb not in comp:
                    comp[nb] = cid
                    q.append(nb)
        cid += 1
    if cid <= 1:
        return
    sizes = {i: sum(1 for p in comp.values() if p == i) for i in range(cid)}
    main = max(sizes, key=lambda i: sizes[i])
    for i in range(cid):
        if i == main:
            continue
        island = [p for p in pids if comp[p] == i]
        mainland = [p for p in pids if comp[p] == main]
        a, b = min(((a, b) for a in island for b in mainland),
                   key=lambda ab: _d2(g.provinces[ab[0]].center,
                                      g.provinces[ab[1]].center))
        g.provinces[a].neighbors.add(b)
        g.provinces[b].neighbors.add(a)
        g.straits.add((min(a, b), max(a, b)))


def _assign_nations(g: Game, rng: random.Random):
    pids = list(g.provinces)
    centers = {pid: g.provinces[pid].center for pid in pids}

    # nation capitals: farthest-point sampling over province centers
    cap_cells = _farthest_point_seeds([centers[p] for p in pids],
                                      len(NATION_SIZES), rng)
    cell_to_pid = {centers[p]: p for p in pids}
    capitals = [cell_to_pid[c] for c in cap_cells]

    sizes = list(NATION_SIZES)
    rng.shuffle(sizes)
    used_tags: set[str] = set()
    used_nation_names: set[str] = set()
    assignment: dict[int, int] = {}      # pid -> nation index
    frontier: list[list[int]] = [[c] for c in capitals]
    counts = [0] * len(capitals)
    for i, c in enumerate(capitals):
        assignment[c] = i
        counts[i] = 1

    # round-robin growth so nations get contiguous, varied territory
    grew = True
    while grew:
        grew = False
        order = sorted(range(len(capitals)),
                       key=lambda i: counts[i] / max(sizes[i], 1))
        for i in order:
            if counts[i] >= sizes[i]:
                continue
            options = [nb for p in frontier[i]
                       for nb in g.provinces[p].neighbors
                       if nb not in assignment]
            if not options:
                continue
            pick = rng.choice(options)
            assignment[pick] = i
            frontier[i].append(pick)
            counts[i] += 1
            grew = True

    # leftover provinces join an adjacent nation (smallest first)
    leftovers = [p for p in pids if p not in assignment]
    while leftovers:
        progressed = False
        for p in list(leftovers):
            adj = [assignment[nb] for nb in g.provinces[p].neighbors
                   if nb in assignment]
            if adj:
                i = min(adj, key=lambda i: counts[i])
                assignment[p] = i
                counts[i] += 1
                leftovers.remove(p)
                progressed = True
        if not progressed:   # isolated island: make it part of nearest nation
            p = leftovers.pop()
            i = min(range(len(capitals)),
                    key=lambda i: _d2(centers[p], centers[capitals[i]]))
            assignment[p] = i
            counts[i] += 1

    # create nations
    palette = list(range(len(capitals)))
    for i, cap in enumerate(capitals):
        culture = g.provinces[cap].culture
        names = [n for n in data.CULTURES[culture]["nation"]
                 if n not in used_nation_names]
        if not names:
            names = [n for c in data.CULTURES.values() for n in c["nation"]
                     if n not in used_nation_names]
        name = rng.choice(names)
        used_nation_names.add(name)
        tag = _make_tag(name, used_tags)
        ruler = (f"{data.RULER_TITLE[culture]} "
                 f"{rng.choice(data.RULER_FIRST[culture])}")
        n = Nation(tag=tag, name=name, culture=culture, color=palette[i],
                   capital=cap, ruler=ruler)
        g.nations[tag] = n

    tags = list(g.nations)
    for pid, i in assignment.items():
        g.provinces[pid].owner = tags[i]

    # capitals are developed; give every nation a starting army
    for tag, n in g.nations.items():
        cap = g.provinces[n.capital]
        cap.dev = max(cap.dev, rng.randint(8, 10))
        n.manpower = g.manpower_max(tag) * 0.7
        regs = max(2, int(g.force_limit(tag) * 0.6))
        g.new_army(tag, n.capital, regs)
        n.gold = 80 + g.total_dev(tag) * 1.5

    # initial opinions: neighbours start wary, same culture friendlier
    for a in tags:
        for b in tags:
            if a == b:
                continue
            na, nb = g.nations[a], g.nations[b]
            base = rng.uniform(-20, 20)
            if na.culture == nb.culture:
                base += 15
            na.opinions[b] = base
    for n in g.nations.values():
        n.last_war_month = g.abs_month
