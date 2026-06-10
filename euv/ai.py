"""AI nation behaviour: economy, war planning, army control, peace, coalitions."""
from __future__ import annotations

from . import data, engine
from .model import Army, Game, Nation, War


def run_all(g: Game):
    for tag in sorted(g.nations):
        n = g.nations[tag]
        if not n.alive or n.is_player:
            continue
        _economy(g, tag)
        _diplomacy(g, tag)
        _military(g, tag)
        _consider_peace(g, tag)
    _coalitions(g)


# ----------------------------------------------------------------- economy

def _economy(g: Game, tag: str):
    n = g.nations[tag]
    _, expense, net = engine.monthly_balance(g, tag)
    buffer = 40 + expense * 6
    at_war = bool(g.wars_of(tag))

    # insolvency: shed troops until the books balance
    if n.gold < 0 and net < 0:
        armies = sorted(g.armies_of(tag), key=lambda a: a.men)
        if armies and (not at_war or len(armies) > 1):
            a = armies[0]
            if a.regiments > 1:
                a.regiments -= 1
                a.men = min(a.men, a.regiments * data.RECRUIT_MANPOWER)
            else:
                engine.disband_army(g, a.aid)
        return

    # stability first
    if n.stability < 0:
        engine.raise_stability(g, tag)

    # keep the army near force limit when at war, ~70% in peace
    fl = g.force_limit(tag)
    regs = sum(a.regiments for a in g.armies_of(tag))
    want = fl if at_war else int(fl * 0.7)
    if regs < want and n.gold > (20 if at_war else buffer):
        home = [p for p in g.provinces_of(tag) if not p.occupier]
        if home:
            safe = [p for p in home
                    if not any(g.at_war_with(tag, g.provinces[nb].owner)
                               for nb in p.neighbors)] or home
            spot = max(safe, key=lambda p: p.dev)
            engine.recruit(g, tag, spot.pid,
                           min(want - regs, 2 if at_war else 1))

    if at_war or n.gold < buffer:
        return

    # peacetime investment: buildings, then development
    provs = sorted(g.provinces_of(tag), key=lambda p: -p.dev)
    for p in provs:
        if len(p.buildings) >= data.MAX_BUILDINGS:
            continue
        for key in ("farm", "market", "barracks", "temple", "fort"):
            if key in p.buildings:
                continue
            cost = data.BUILDINGS[key][1]
            if n.gold - cost >= buffer * 0.7:
                engine.build(g, tag, p.pid, key)
                return
    # develop; rich nations invest several times a month
    for _ in range(3 if n.gold > buffer * 4 else 1):
        best = min(g.provinces_of(tag), key=lambda p: p.dev_cost())
        if n.gold - best.dev_cost() >= buffer * 0.7:
            engine.develop(g, tag, best.pid)


# --------------------------------------------------------------- diplomacy

def _diplomacy(g: Game, tag: str):
    n = g.nations[tag]
    rng = g.rng
    at_war = bool(g.wars_of(tag))
    neighbours = {g.provinces[nb].owner
                  for p in g.provinces_of(tag) for nb in p.neighbors
                  if g.provinces[nb].owner != tag}
    neighbours = {t for t in neighbours if g.nations[t].alive}

    # court strong neighbours: improve relations, then ally
    if not at_war and len(n.allies) < 2 and rng.random() < 0.15:
        cands = [t for t in neighbours
                 if t not in n.allies and not g.truce_between(tag, t)
                 and not g.nations[t].is_player
                 and g.nations[t].ae.get(tag, 0) < 30]
        if cands:
            pick = max(cands, key=lambda t: g.nation_strength(t)
                       + (200000 if g.nations[t].culture == n.culture else 0)
                       + g.nations[t].opinion_of(tag) * 1000)
            if g.nations[pick].opinion_of(tag) >= 25:
                engine.offer_alliance(g, tag, pick)
            elif n.gold > 60:
                engine.improve_relations(g, tag, pick)

    # fabricate claims on tempting weak neighbours
    if not at_war and n.fabricating is None and rng.random() < 0.08:
        targets = []
        for t in neighbours:
            if g.truce_between(tag, t) or t in n.allies:
                continue
            if g.nation_strength(tag) > g.nation_strength(t) * 1.1:
                border = [p.pid for p in g.provinces_of(t)
                          if any(g.provinces[nb].owner == tag
                                 for nb in p.neighbors)
                          and p.pid not in n.claims]
                targets += border
        if targets:
            pid = max(targets, key=lambda pid: g.provinces[pid].dev)
            engine.fabricate_claim(g, tag, pid)

    # declare war when clearly stronger (claims make it likelier)
    aggression = 0.035 if n.culture in ("valdric", "tervani") else 0.025
    if not at_war and n.stability >= 0 and rng.random() < aggression:
        best, best_ratio = None, 0.0
        for t in neighbours:
            o = g.nations[t]
            if g.truce_between(tag, t) or t in n.allies or not o.alive:
                continue
            my = g.nation_strength(tag) + sum(
                g.nation_strength(a) * 0.5 for a in n.allies)
            their = g.nation_strength(t) + sum(
                g.nation_strength(a) * 0.7 for a in o.allies)
            ratio = my / max(their, 1)
            has_claim = any(g.provinces[c].owner == t for c in n.claims)
            need = 1.3 if has_claim else 1.7
            if n.opinion_of(t) > 40:
                need += 0.5
            if ratio > need and ratio > best_ratio:
                best, best_ratio = t, ratio
        if best:
            engine.declare_war(g, tag, best)


# ---------------------------------------------------------------- military

def _military(g: Game, tag: str):
    enemies = g.enemies_of(tag)
    if not enemies:
        # peacetime: drift the main stack home
        for a in g.armies_of(tag):
            if a.move_target is None and \
                    g.provinces[a.location].owner != tag:
                home = g.nations[tag].capital
                if engine.find_path(g, tag, a.location, home):
                    a.move_target = home
        return

    my_armies = g.armies_of(tag)
    if not my_armies:
        return
    enemy_armies = [a for a in g.armies.values() if a.owner in enemies]

    for a in my_armies:
        if a.morale < 1.0:      # recovering, stay put unless threatened
            continue
        # 1) defend home: enemy army on our soil we can beat
        threats = [e for e in enemy_armies
                   if g.provinces[e.location].owner == tag]
        threats = [e for e in threats if _local_power(g, a) >
                   _enemy_power_at(g, enemies, e.location) * 1.05]
        if threats:
            target = min(threats, key=lambda e: _dist(g, a.location,
                                                      e.location))
            engine.move_army(g, a.aid, target.location)
            continue
        # 2) avoid doom: much stronger enemy stack adjacent
        near_threat = any(
            e.location in g.provinces[a.location].neighbors
            and e.men > a.men * 1.6 and e.morale > 1.0
            for e in enemy_armies)
        if near_threat:
            home = g.nations[tag].capital
            if a.location != home and engine.find_path(g, tag, a.location,
                                                       home):
                engine.move_army(g, a.aid, home)
                continue
        # 3) siege: nearest unoccupied enemy province (prefer war goal)
        if a.move_target is not None:
            continue
        targets = []
        for et in enemies:
            for p in g.provinces_of(et):
                if p.occupier is None:
                    targets.append(p)
        if not targets:
            continue
        def value(p):
            d = _dist(g, a.location, p.pid)
            bonus = -6 if any(p.pid == w.cb_target
                              for w in g.wars_of(tag)) else 0
            return d + p.fort_level * 1.5 + bonus
        best = min(targets, key=value)
        if best.pid != a.location:
            engine.move_army(g, a.aid, best.pid)


def _local_power(g: Game, a: Army) -> float:
    return a.men * max(0.3, a.morale / data.MORALE_BASE)


def _enemy_power_at(g: Game, enemies: set[str], pid: int) -> float:
    return sum(_local_power(g, e) for e in g.armies.values()
               if e.owner in enemies and e.location == pid)


def _dist(g: Game, a: int, b: int) -> float:
    ca, cb = g.provinces[a].center, g.provinces[b].center
    return ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2 * 4) ** 0.5


# ------------------------------------------------------------------- peace

def _consider_peace(g: Game, tag: str):
    n = g.nations[tag]
    for w in list(g.wars_of(tag)):
        leader = (w.attackers if w.side_of(tag) == "att" else w.defenders)[0]
        if leader != tag:
            continue            # only war leaders negotiate
        enemy_leader = w.enemies_of(tag)[0]
        my = w.score_for(tag)
        months = g.abs_month - (w.start[0] * 12 + w.start[1])
        # losing badly or exhausted: sue for peace
        if (my < -35 or (n.war_exhaustion > 9 and my < 10)
                or (not g.armies_of(tag) and n.manpower < 800)):
            give = _pick_concessions(g, w, enemy_leader, tag, -my)
            engine.offer_peace(g, w, tag, give, max(0.0, -my) * 1.2,
                               beneficiary=enemy_leader)
            continue
        # winning enough: cash in
        if my > 30 and months > 12:
            take = _pick_concessions(g, w, tag, enemy_leader, my - 8)
            if take or my > 45:
                engine.offer_peace(g, w, tag, take, 0 if take else my * 1.5)
        # stalemate fatigue: white peace
        elif months > 36 and abs(my) < 12 and n.war_exhaustion > 4:
            engine.offer_peace(g, w, tag, [], 0)


def _pick_concessions(g: Game, w: War, taker: str, victim: str,
                      budget_ws: float) -> list[int]:
    """Choose provinces for taker worth up to budget_ws warscore."""
    picks: list[int] = []
    spent = 0.0
    cands = [p for p in g.provinces_of(victim)]
    # prefer war goal, claims, occupied, border provinces, low dev first
    def key(p):
        s = p.dev * 1.0
        if p.pid == w.cb_target:
            s -= 50
        if p.pid in g.nations[taker].claims:
            s -= 25
        if p.occupier in (w.attackers if taker in w.attackers
                          else w.defenders):
            s -= 15
        if any(g.provinces[nb].owner == taker for nb in p.neighbors):
            s -= 10
        return s
    for p in sorted(cands, key=key):
        cost = engine.province_peace_cost(g, w, taker, p.pid)
        if spent + cost <= budget_ws:
            picks.append(p.pid)
            spent += cost
        if len(picks) >= 4:
            break
    return picks


# -------------------------------------------------------------- coalitions

def _coalitions(g: Game):
    """Nations with high AE attract defensive coalitions that may strike."""
    for target_tag, target in g.nations.items():
        if not target.alive:
            continue
        members = [t for t, n in g.nations.items()
                   if n.alive and t != target_tag and not n.is_player
                   and n.ae.get(target_tag, 0) > data.COALITION_AE_THRESHOLD
                   and n.opinion_of(target_tag) < 0
                   and not g.at_war_with(t, target_tag)
                   and not g.truce_between(t, target_tag)
                   and target_tag not in n.allies]
        for t in members:
            if g.nations[t].in_coalition_against != target_tag:
                g.nations[t].in_coalition_against = target_tag
                g.say("diplo", f"{g.nations[t].name} joins the coalition "
                               f"against {target.name}!")
        active = [t for t, n in g.nations.items()
                  if n.alive and n.in_coalition_against == target_tag]
        if len(active) < 2:
            continue
        combined = sum(g.nation_strength(t) for t in active)
        if combined > g.nation_strength(target_tag) * 1.2 \
                and g.rng.random() < 0.15:
            leader = max(active, key=lambda t: g.nation_strength(t))
            engine.declare_war(g, leader, target_tag, coalition=active)
            for t in active:
                g.nations[t].in_coalition_against = None
