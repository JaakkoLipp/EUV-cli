"""Game engine: player/AI actions, monthly tick, combat, sieges, peace."""
from __future__ import annotations

import math
from collections import deque

from . import data
from .model import Army, Game, Nation, Province, War


# ================================================================== queries

def can_pass(g: Game, tag: str, pid: int) -> bool:
    owner = g.provinces[pid].owner
    if owner == tag or owner in g.nations[tag].allies:
        return True
    if g.at_war_with(tag, owner):
        return True
    # co-belligerents: anyone on our side in any of our wars
    for w in g.wars_of(tag):
        side = w.attackers if w.side_of(tag) == "att" else w.defenders
        if owner in side:
            return True
    return False


def find_path(g: Game, tag: str, start: int, goal: int) -> list[int] | None:
    """BFS path through passable provinces. Returns [start..goal] or None."""
    if start == goal:
        return [start]
    prev = {start: -1}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in sorted(g.provinces[cur].neighbors):
            if nb in prev:
                continue
            if nb != goal and not can_pass(g, tag, nb):
                continue
            prev[nb] = cur
            if nb == goal:
                path = [goal]
                while path[-1] != start:
                    path.append(prev[path[-1]])
                return path[::-1]
            q.append(nb)
    return None


def morale_max(g: Game, tag: str) -> float:
    n = g.nations[tag]
    return max(1.0, data.MORALE_BASE * (1 - 0.03 * n.war_exhaustion)
               + 0.1 * max(0, n.stability))


def supply_limit(g: Game, tag: str, pid: int) -> int:
    """Regiments province pid can supply for armies of nation tag."""
    p = g.provinces[pid]
    # tiny epsilon so float fuzz (e.g. 5 * 0.6) never inflates the ceil
    limit = data.SUPPLY_BASE + math.ceil(p.dev * data.SUPPLY_PER_DEV - 1e-9)
    limit += data.SUPPLY_TERRAIN.get(p.terrain, 0)
    if p.owner == tag or p.owner in g.nations[tag].allies:
        limit += data.SUPPLY_FRIENDLY_BONUS
    return max(1, limit)


def attrition_fraction(g: Game, army: Army) -> float:
    """Monthly fraction of men the army loses where it stands (0 if fed).

    Stacking rule: all of one nation's regiments in a province are summed
    against the supply limit, so splitting a doomstack into several armies
    on the same spot does not dodge attrition - spreading out does.
    """
    tag, pid = army.owner, army.location
    limit = supply_limit(g, tag, pid)
    regs = sum(a.regiments for a in g.armies.values()
               if a.owner == tag and a.location == pid)
    if regs <= limit:
        return 0.0
    frac = data.ATTRITION_PER_EXCESS * (regs / limit - 1)
    if g.at_war_with(tag, g.provinces[pid].owner):
        frac += data.ATTRITION_HOSTILE
    return min(data.ATTRITION_MAX, frac)


def army_upkeep(g: Game, tag: str) -> float:
    regs = sum(a.regiments for a in g.armies_of(tag))
    fl = g.force_limit(tag)
    over = max(0, regs - fl)
    return ((regs - over) * data.REGIMENT_UPKEEP
            + over * data.REGIMENT_UPKEEP * data.OVER_LIMIT_MULT)


def monthly_balance(g: Game, tag: str) -> tuple[float, float, float]:
    """(income, expenses, net) for the ledger."""
    stab_mult = 1 + 0.03 * g.nations[tag].stability
    income = sum(p.tax_income() for p in g.provinces_of(tag)) * stab_mult
    forts = sum(1 for p in g.provinces_of(tag) if "fort" in p.buildings)
    expense = army_upkeep(g, tag) + forts * data.FORT_UPKEEP * 2
    n = g.nations[tag]
    if n.gold < 0:
        expense += -n.gold * 0.02   # interest on debt
    return income, expense, income - expense


def score(g: Game, tag: str) -> float:
    n = g.nations[tag]
    return g.total_dev(tag) * 2 + n.prestige + max(0.0, n.gold) / 20


# =========================================================== player actions
# All return (ok, message). They are also used by the AI.

def develop(g: Game, tag: str, pid: int):
    p, n = g.provinces[pid], g.nations[tag]
    if p.owner != tag:
        return False, "Not your province."
    cost = p.dev_cost()
    if n.gold < cost:
        return False, f"Need {cost} gold."
    n.gold -= cost
    p.dev += 1
    return True, f"{p.name} developed to {p.dev}."


def build(g: Game, tag: str, pid: int, key: str):
    p, n = g.provinces[pid], g.nations[tag]
    if p.owner != tag:
        return False, "Not your province."
    if key in p.buildings:
        return False, "Already built."
    if len(p.buildings) >= data.MAX_BUILDINGS:
        return False, "No building slots left."
    name, cost, *_ = data.BUILDINGS[key]
    if n.gold < cost:
        return False, f"Need {cost} gold."
    n.gold -= cost
    p.buildings.append(key)
    return True, f"{name} built in {p.name}."


def recruit(g: Game, tag: str, pid: int, regiments: int = 1):
    p, n = g.provinces[pid], g.nations[tag]
    if p.owner != tag:
        return False, "Not your province."
    if p.occupier:
        return False, "Province is occupied."
    cost = data.RECRUIT_COST * regiments
    men = data.RECRUIT_MANPOWER * regiments
    if n.gold < cost:
        return False, f"Need {cost} gold."
    if n.manpower < men:
        return False, f"Need {men} manpower."
    n.gold -= cost
    n.manpower -= men
    here = [a for a in g.armies_of(tag) if a.location == pid]
    if here:
        here[0].regiments += regiments
        here[0].men += men
    else:
        g.new_army(tag, pid, regiments)
    return True, f"Recruited {regiments} regiment(s) in {p.name}."


def move_army(g: Game, aid: int, target: int):
    a = g.armies[aid]
    if target == a.location:
        a.move_target = None
        return True, "Order cancelled."
    path = find_path(g, a.owner, a.location, target)
    if not path:
        return False, "No route there (need own/allied/enemy territory)."
    a.move_target = target
    return True, f"Moving to {g.provinces[target].name}."


def split_army(g: Game, aid: int):
    a = g.armies[aid]
    if a.regiments < 2:
        return False, "Too small to split."
    half = a.regiments // 2
    men_half = a.men * half // a.regiments
    a.regiments -= half
    a.men -= men_half
    b = g.new_army(a.owner, a.location, half, men_half)
    b.morale = a.morale
    return True, f"Split off {b.name}."


def disband_army(g: Game, aid: int):
    a = g.armies.pop(aid)
    n = g.nations[a.owner]
    n.manpower = min(g.manpower_max(a.owner), n.manpower + a.men * 0.5)
    return True, f"{a.name} disbanded."


def hire_general(g: Game, aid: int):
    a = g.armies[aid]
    n = g.nations[a.owner]
    if a.general:
        return False, f"{a.general_name} already commands this army."
    if n.gold < data.GENERAL_COST:
        return False, f"Need {data.GENERAL_COST} gold."
    n.gold -= data.GENERAL_COST
    # skill 1-5, weighted toward the middle
    a.general = 1 + g.rng.randint(0, 2) + g.rng.randint(0, 2)
    first = g.rng.choice(data.RULER_FIRST[n.culture])
    a.general_name = f"General {first}"
    return True, f"{a.general_name} (skill {a.general}) takes command."


def stability_cost(g: Game, tag: str) -> int:
    """Base cost rises with current stability and with empire size."""
    n = g.nations[tag]
    base = data.STAB_COST + 40 * (n.stability + 3)
    return int(base * (1 + g.total_dev(tag) / data.STAB_DEV_DIVISOR))


def raise_stability(g: Game, tag: str):
    n = g.nations[tag]
    if n.stability >= data.MAX_STAB:
        return False, "Stability is already maximal."
    cost = stability_cost(g, tag)
    if n.gold < cost:
        return False, f"Need {cost} gold."
    n.gold -= cost
    n.stability += 1
    return True, f"Stability raised to {n.stability:+d}."


def fabricate_claim(g: Game, tag: str, pid: int):
    n = g.nations[tag]
    p = g.provinces[pid]
    if p.owner == tag:
        return False, "You own this province."
    if pid in n.claims:
        return False, "Already claimed."
    if n.fabricating:
        return False, "Spies are already busy elsewhere."
    own_border = any(g.provinces[nb].owner == tag for nb in p.neighbors)
    if not own_border:
        return False, "Can only claim provinces bordering your realm."
    if n.gold < data.CLAIM_COST:
        return False, f"Need {data.CLAIM_COST} gold."
    n.gold -= data.CLAIM_COST
    n.fabricating = (pid, data.CLAIM_MONTHS)
    return True, f"Spies sent to {p.name} ({data.CLAIM_MONTHS} months)."


def improve_relations(g: Game, tag: str, other: str):
    n, o = g.nations[tag], g.nations[other]
    if other in n.rivals or tag in o.rivals:
        return False, f"Impossible: {o.name} is a rival. End the " \
                      f"rivalry first."
    if n.gold < data.IMPROVE_COST:
        return False, f"Need {data.IMPROVE_COST} gold."
    n.gold -= data.IMPROVE_COST
    o.opinions[tag] = min(100.0, o.opinion_of(tag) + 12)
    return True, f"Envoys sent to {o.name} (+12 opinion)."


# ---------------------------------------------------------------- rivalries

def rival_candidates(g: Game, tag: str) -> list[str]:
    """Nearby nations (neighbours or their neighbours) of comparable
    strength that could be declared rivals."""
    n = g.nations[tag]

    def neighbours_of(t: str) -> set[str]:
        return {g.provinces[nb].owner for p in g.provinces_of(t)
                for nb in p.neighbors if g.provinces[nb].owner != t}

    near = neighbours_of(tag)
    for t in list(near):
        near |= neighbours_of(t)
    near.discard(tag)
    my = g.nation_strength(tag)
    lo, hi = data.RIVAL_BAND
    out = []
    for t in sorted(near):
        o = g.nations[t]
        if not o.alive or t in n.allies or t in n.rivals:
            continue
        if my * lo <= g.nation_strength(t) <= my * hi:
            out.append(t)
    return out


def declare_rival(g: Game, tag: str, other: str):
    n, o = g.nations[tag], g.nations[other]
    if other in n.rivals:
        return False, f"{o.name} is already your rival."
    if len(n.rivals) >= data.MAX_RIVALS:
        return False, f"You can have at most {data.MAX_RIVALS} rivals."
    if other in n.allies:
        return False, "You cannot rival an ally."
    if not o.alive:
        return False, "That nation is no more."
    if other not in rival_candidates(g, tag):
        return False, ("Not a valid rival: they must be nearby and of "
                       "comparable strength.")
    n.rivals.add(other)
    g.say("diplo", f"{n.name} declares {o.name} its rival!")
    _maybe_reciprocate_rival(g, tag, other)
    return True, f"{o.name} is now your rival."


def end_rivalry(g: Game, tag: str, other: str):
    n = g.nations[tag]
    if other not in n.rivals:
        return False, "They are not your rival."
    n.rivals.discard(other)
    n.prestige -= data.END_RIVAL_PRESTIGE
    g.say("diplo", f"{n.name} sets aside its rivalry with "
                   f"{g.nations[other].name}.")
    return True, (f"Rivalry with {g.nations[other].name} ended "
                  f"(-{data.END_RIVAL_PRESTIGE:.0f} prestige).")


def _maybe_reciprocate_rival(g: Game, actor: str, target: str):
    """The target of a rivalry usually answers in kind (AI only)."""
    o = g.nations[target]
    if o.is_player or not o.alive:
        return
    if actor in o.rivals or len(o.rivals) >= data.MAX_RIVALS \
            or actor in o.allies:
        return
    if g.rng.random() < data.RIVAL_RECIPROCATE_CHANCE:
        o.rivals.add(actor)
        g.say("diplo", f"{o.name} answers in kind: "
                       f"{g.nations[actor].name} is now its rival.")


def offer_alliance(g: Game, tag: str, other: str):
    n, o = g.nations[tag], g.nations[other]
    if other in n.allies:
        return False, "Already allied."
    if g.at_war_with(tag, other):
        return False, "You are at war with them."
    if o.is_player:
        # the player decides via popup
        if not any("alliance" in e and e.get("alliance") == tag
                   for e in g.pending_events):
            g.pending_events.append({"alliance": tag})
        return False, "Offer sent to their court..."
    # AI acceptance: opinion + relative strength considerations
    accept = (o.opinion_of(tag) >= 25
              and o.ae.get(tag, 0) < 30
              and not o.in_coalition_against == tag)
    if not accept:
        return False, f"{o.name} declines (opinion {o.opinion_of(tag):.0f})."
    n.allies.add(other)
    o.allies.add(tag)
    n.opinions[other] = n.opinion_of(other) + 10
    o.opinions[tag] = o.opinion_of(tag) + 10
    g.say("diplo", f"{n.name} and {o.name} form an alliance.")
    return True, f"{o.name} accepts the alliance!"


def break_alliance(g: Game, tag: str, other: str):
    n, o = g.nations[tag], g.nations[other]
    n.allies.discard(other)
    o.allies.discard(tag)
    o.opinions[tag] = o.opinion_of(tag) - 40
    g.say("diplo", f"{n.name} breaks its alliance with {o.name}.")
    return True, f"Alliance with {o.name} dissolved."


def declare_war(g: Game, tag: str, target: str,
                coalition: list[str] | None = None):
    n, t = g.nations[tag], g.nations[target]
    if g.at_war_with(tag, target):
        return False, "Already at war."
    if g.truce_between(tag, target):
        return False, "A truce forbids war."
    if target in n.allies:
        break_alliance(g, tag, target)
    claim = next((pid for pid in n.claims
                  if g.provinces[pid].owner == target), None)
    if claim is None:
        n.stability = max(data.MIN_STAB,
                          n.stability - data.WAR_STAB_HIT_NO_CB)
    attackers = [tag]
    defenders = [target]
    player_cta: str | None = None        # side the player may join via popup
    if coalition:
        attackers += [c for c in coalition if c != tag]
    else:
        for ally in sorted(n.allies):
            a = g.nations[ally]
            if a.alive and not g.at_war_with(ally, target) \
                    and not g.truce_between(ally, target):
                if a.is_player:
                    player_cta = "att"
                elif a.opinion_of(tag) >= 0 and not g.wars_of(ally):
                    # busy allies decline offensive calls
                    attackers.append(ally)
    for ally in sorted(t.allies):
        a = g.nations[ally]
        if a.alive and ally not in attackers \
                and not any(g.at_war_with(ally, x) for x in attackers):
            if a.is_player:
                player_cta = "def"
            else:
                defenders.append(ally)
    w = g.new_war(attackers, defenders, claim)
    if player_cta:
        g.pending_events.append(
            {"cta": {"wid": w.wid, "side": player_cta,
                     "caller": tag if player_cta == "att" else target}})
    if any(g.nations[x].is_player for x in defenders):
        g.pending_events.append({"war_decl": w.wid})
    if coalition:
        w.name = f"Coalition War against {t.name}"
    for x in attackers + defenders:
        g.nations[x].last_war_month = g.abs_month
    for x in attackers:
        for y in defenders:
            g.nations[y].opinions[x] = g.nations[y].opinion_of(x) - 50
    g.say("war", f"{n.name} declares war on {t.name}! "
                 f"({'+'.join(attackers)} vs {'+'.join(defenders)})")
    return True, f"War declared on {t.name}!"


# ----------------------------------------------------------------- warscore

def occupation_score(g: Game, w: War) -> float:
    """Net occupation warscore from the attackers' perspective."""
    def side_occ(holders: list[str], victims: list[str]) -> float:
        total_dev = sum(g.total_dev(v) for v in victims) or 1
        got = 0.0
        for v in victims:
            for p in g.provinces_of(v):
                if p.occupier in holders:
                    worth = p.dev / total_dev * 70
                    if p.pid == g.nations[v].capital:
                        worth += 10
                    if p.pid == w.cb_target:
                        worth += 10
                    got += worth
        return got
    return side_occ(w.attackers, w.defenders) - side_occ(w.defenders,
                                                         w.attackers)


def update_warscore(g: Game, w: War):
    w.score = max(-100.0, min(100.0, occupation_score(g, w)
                              + w.battles_score + w.goal_score))


def _tick_goal_score(g: Game, w: War):
    """The side controlling the war-goal province slowly gains warscore.

    Control = the province's occupier if set, else its owner; allies on
    either side count. This makes claim-wars decisive over time.
    """
    if w.cb_target is None or w.cb_target not in g.provinces:
        return
    p = g.provinces[w.cb_target]
    holder = p.occupier or p.owner
    if holder in w.attackers:
        w.goal_score = min(data.GOAL_SCORE_CAP,
                           w.goal_score + data.GOAL_SCORE_MONTHLY)
    elif holder in w.defenders:
        w.goal_score = max(-data.GOAL_SCORE_CAP,
                           w.goal_score - data.GOAL_SCORE_MONTHLY)


def province_peace_cost(g: Game, w: War, taker: str, pid: int) -> float:
    p = g.provinces[pid]
    cost = p.dev * 1.6
    if pid in g.nations[taker].claims or pid == w.cb_target:
        cost *= 0.6
    if pid == g.nations[p.owner].capital:
        cost *= 1.5
    return cost


def offer_peace(g: Game, w: War, proposer: str, demand_pids: list[int],
                demand_gold: float,
                beneficiary: str | None = None) -> tuple[bool, str]:
    """proposer offers terms; beneficiary (default proposer) takes the spoils.

    beneficiary != proposer means the proposer is surrendering.
    Empty demands = white peace. Returns (accepted, message).
    """
    beneficiary = beneficiary or proposer
    recipient = (w.defenders if w.side_of(proposer) == "att"
                 else w.attackers)[0]
    cost = sum(province_peace_cost(g, w, beneficiary, pid)
               for pid in demand_pids)
    cost += max(0.0, demand_gold) / data.PEACE_GOLD_PER_WARSCORE
    rec = g.nations[recipient]
    if rec.is_player:
        g.pending_events.append({
            "peace": {"wid": w.wid, "proposer": proposer,
                      "beneficiary": beneficiary, "pids": demand_pids,
                      "gold": demand_gold, "cost": cost}})
        return False, "Offer sent to their court..."
    rec_score = w.score_for(recipient)
    ben_score = w.score_for(beneficiary)
    desperate = (rec.war_exhaustion > 8 or not g.armies_of(recipient)
                 or rec.manpower < 500)
    if w.side_of(beneficiary) == w.side_of(recipient):
        # we are being offered the spoils (enemy surrenders)
        accept = (cost >= rec_score - 15 or rec.war_exhaustion > 6
                  or rec_score < 5)
        if not demand_pids and demand_gold <= 0:   # white peace
            accept = rec_score < 15 or rec.war_exhaustion > 6
        if not accept:
            return False, (f"{rec.name} rejects the offer; they demand "
                           f"more ({rec_score:.0f}% warscore).")
    else:
        # demands against the recipient
        threshold = ben_score - (0 if desperate else 12)
        if ben_score >= 99:
            threshold = 100   # total victory: anything goes
        if not demand_pids and demand_gold <= 0:
            if rec_score > 20 and not desperate:
                return False, (f"{rec.name} rejects white peace; "
                               f"they are winning.")
        elif cost > threshold:
            return False, (f"{rec.name} rejects the terms ({cost:.0f}% "
                           f"asked, {ben_score:.0f}% warscore).")
    execute_peace(g, w, beneficiary, demand_pids, demand_gold)
    return True, "Peace concluded."


def peace_refusal_penalty(g: Game, w: War, offer: dict) -> bool:
    """Refusing costs stability when the terms are fair and you are losing.

    'Fair' = the demands are within the warscore the proposer has earned.
    Refusing an enemy's surrender, or unearned demands, stays free.
    """
    recipient = (w.defenders if w.side_of(offer["proposer"]) == "att"
                 else w.attackers)[0]
    if w.side_of(offer["beneficiary"]) == w.side_of(recipient):
        return False               # they are conceding to us
    rec_score = w.score_for(recipient)
    prop_score = w.score_for(offer["proposer"])
    return rec_score <= -25 and offer["cost"] <= prop_score - 5


def refuse_peace(g: Game, w: War, offer: dict) -> bool:
    """Apply the consequences of the recipient rejecting an offer."""
    recipient = (w.defenders if w.side_of(offer["proposer"]) == "att"
                 else w.attackers)[0]
    n = g.nations[recipient]
    prop = g.nations[offer["proposer"]]
    w.refusals += 1
    w.no_offers_until = g.abs_month + data.REFUSAL_COOLDOWN_MONTHS
    prop.opinions[recipient] = prop.opinion_of(recipient) - 10
    if peace_refusal_penalty(g, w, offer):
        n.stability = max(data.MIN_STAB,
                          n.stability - data.REFUSAL_STAB_HIT)
        n.war_exhaustion = min(15.0,
                               n.war_exhaustion + data.REFUSAL_WE_HIT)
        g.say("war", f"The court rejects {prop.name}'s terms; the war "
                     f"grinds on. (-{data.REFUSAL_STAB_HIT} stability)")
        return True
    g.say("diplo", f"You refused the peace offer from {prop.name}.")
    return False


def execute_peace(g: Game, w: War, winner: str, pids: list[int],
                  gold: float):
    win_side = w.attackers if w.side_of(winner) == "att" else w.defenders
    lose_side = w.defenders if w.side_of(winner) == "att" else w.attackers
    loser_leader = lose_side[0]
    # prestige stakes between rivals (judged before any annexation)
    rival_stake = (pids or gold > 0) and \
        (loser_leader in g.nations[winner].rivals
         or winner in g.nations[loser_leader].rivals)
    terms = []
    for pid in pids:
        p = g.provinces[pid]
        old = p.owner
        _transfer_province(g, pid, winner)
        terms.append(p.name)
        # aggressive expansion among everyone who isn't the winner
        for tag, n in g.nations.items():
            if tag == winner or not n.alive or tag == data.REBEL_TAG:
                continue
            dist = 1.0 if any(g.provinces[nb].owner == tag
                              for nb in p.neighbors) else 0.5
            n.ae[winner] = n.ae.get(winner, 0) + \
                data.AE_PER_DEV_TAKEN * p.dev * dist
            n.opinions[winner] = n.opinion_of(winner) - p.dev * dist
        if old in g.nations:
            g.nations[winner].prestige += p.dev * 0.5
    if gold > 0:
        lo = g.nations[loser_leader]
        pay = min(gold, max(0.0, lo.gold))
        lo.gold -= gold
        g.nations[winner].gold += pay
        terms.append(f"{gold:.0f} gold")
    if rival_stake:
        g.nations[winner].prestige += data.RIVAL_PRESTIGE_STAKE
        g.nations[loser_leader].prestige -= data.RIVAL_PRESTIGE_STAKE
        g.say("diplo", f"{g.nations[winner].name} humbles its rival "
                       f"{g.nations[loser_leader].name}!")
    # lift occupations between the two sides, set truces
    for tag in win_side + lose_side:
        for p in g.provinces_of(tag):
            if p.occupier and (p.occupier in win_side
                               or p.occupier in lose_side):
                p.occupier = None
                p.siege_progress = 0.0
                p.sieging = None
    until = g.abs_month + data.TRUCE_YEARS * 12
    for a in win_side:
        for b in lose_side:
            if a in g.nations and b in g.nations:
                g.nations[a].truces[b] = until
                g.nations[b].truces[a] = until
    for tag in win_side + lose_side:
        if tag in g.nations:
            g.nations[tag].war_exhaustion = max(
                0.0, g.nations[tag].war_exhaustion - 2)
            g.nations[tag].last_war_month = g.abs_month
    g.wars.pop(w.wid, None)   # may already be gone if a side was annexed
    _send_strays_home(g, win_side + lose_side)
    what = ", ".join(terms) if terms else "white peace"
    g.say("war", f"Peace in the {w.name}: "
                 f"{g.nations[winner].name} gains {what}." if terms else
                 f"The {w.name} ends in a white peace.")


def _transfer_province(g: Game, pid: int, to: str):
    p = g.provinces[pid]
    old = p.owner
    p.owner = to
    p.occupier = None
    p.siege_progress = 0.0
    p.sieging = None
    p.unrest = 4.0
    g.nations[to].claims.discard(pid)
    if old in g.nations:
        n = g.nations[old]
        if not g.provinces_of(old):
            _eliminate(g, old, to)
        elif pid == n.capital:
            n.capital = max(g.provinces_of(old), key=lambda q: q.dev).pid


def _eliminate(g: Game, tag: str, by: str):
    n = g.nations[tag]
    n.alive = False
    for a in list(g.armies.values()):
        if a.owner == tag:
            del g.armies[a.aid]
    for w in list(g.wars.values()):
        for side in (w.attackers, w.defenders):
            if tag in side:
                side.remove(tag)
        if not w.attackers or not w.defenders:
            del g.wars[w.wid]
    for o in g.nations.values():
        o.allies.discard(tag)
        o.rivals.discard(tag)
        o.truces.pop(tag, None)
        if o.in_coalition_against == tag:
            o.in_coalition_against = None
    g.say("war", f"*** {n.name} has been annexed by {g.nations[by].name}! ***")
    if n.is_player:
        g.game_over = (f"{n.name} has fallen. "
                       f"Your realm was annexed by {g.nations[by].name}.")


def _send_strays_home(g: Game, tags: list[str]):
    for a in list(g.armies.values()):
        if a.owner not in tags:
            continue
        if not can_pass(g, a.owner, a.location):
            n = g.nations[a.owner]
            a.location = n.capital
            a.move_target = None


# ================================================================= the tick

def advance_month(g: Game, ai_module=None):
    """Advance the world by one month. ai_module avoids a circular import."""
    g.month += 1
    if g.month >= 12:
        g.month = 0
        g.year += 1
    _movement_phase(g)
    _battle_phase(g)
    _siege_phase(g)
    _economy_phase(g)
    _supply_attrition(g)
    _attrition_and_recovery(g)
    _unrest_phase(g)
    _diplomacy_phase(g)
    for w in g.wars.values():
        _tick_goal_score(g, w)
        update_warscore(g, w)
    if ai_module:
        ai_module.run_all(g)
    for w in g.wars.values():
        update_warscore(g, w)
    _capitulation_phase(g)
    _missions_phase(g)
    _events_phase(g)
    _check_end(g)


def _capitulation_phase(g: Game):
    """A year of total domination forces the loser to capitulate.

    This is the backstop that guarantees wars end even if the beaten
    side refuses every offer: the winner dictates terms outright.
    """
    for w in list(g.wars.values()):
        if abs(w.score) < data.CAPITULATION_SCORE:
            w.dom_months = 0
            continue
        w.dom_months += 1
        if w.dom_months < data.CAPITULATION_MONTHS:
            continue
        winner = (w.attackers if w.score > 0 else w.defenders)[0]
        loser = (w.defenders if w.score > 0 else w.attackers)[0]
        pids = _capitulation_terms(g, w, winner, loser)
        name, loser_name = w.name, g.nations[loser].name
        player_involved = bool(g.player) and w.side_of(g.player) is not None
        execute_peace(g, w, winner, pids, 0)
        g.say("war", f"{loser_name} capitulates! Total defeat in "
                     f"the {name}.")
        if player_involved:
            g.pending_events.append({"notice": {
                "title": "Capitulation!",
                "body": f"After a year of total domination, {loser_name} "
                        f"capitulates in the {name}. "
                        f"{g.nations[winner].name} dictates the terms."}})


def _capitulation_terms(g: Game, w: War, winner: str,
                        loser: str) -> list[int]:
    """Winner takes up to 100 warscore worth of the loser's provinces."""
    win_side = w.attackers if w.side_of(winner) == "att" else w.defenders

    def key(p):
        s = float(p.dev)
        if p.pid == w.cb_target:
            s -= 40
        if p.pid in g.nations[winner].claims:
            s -= 25
        if p.occupier in win_side:
            s -= 20
        return s

    picks: list[int] = []
    spent = 0.0
    for p in sorted(g.provinces_of(loser), key=key):
        cost = province_peace_cost(g, w, winner, p.pid)
        if spent + cost <= 100.0:
            picks.append(p.pid)
            spent += cost
    return picks


def _movement_phase(g: Game):
    for a in sorted(g.armies.values(), key=lambda a: a.aid):
        if a.aid not in g.armies or a.move_target is None:
            continue
        if a.move_target == a.location:
            a.move_target = None
            continue
        path = find_path(g, a.owner, a.location, a.move_target)
        if not path or len(path) < 2:
            a.move_target = None
            continue
        a.location = path[1]
        if a.location == a.move_target:
            a.move_target = None
        # auto-merge with friendly army present
        for b in list(g.armies.values()):
            if (b.aid != a.aid and b.owner == a.owner
                    and b.location == a.location):
                b.regiments += a.regiments
                b.men += a.men
                b.morale = min(a.morale, b.morale)
                if a.general > b.general:
                    b.general, b.general_name = a.general, a.general_name
                if a.move_target and not b.move_target:
                    b.move_target = a.move_target
                del g.armies[a.aid]
                break


def _battle_phase(g: Game):
    # find provinces holding mutually hostile armies
    by_loc: dict[int, list[Army]] = {}
    for a in g.armies.values():
        by_loc.setdefault(a.location, []).append(a)
    for pid, armies in by_loc.items():
        tags = {a.owner for a in armies}
        if len(tags) < 2:
            continue
        # rebels fight everyone: all other armies present unite vs them
        rebs = [a for a in armies if a.owner == data.REBEL_TAG]
        if rebs:
            loyal = [a for a in armies if a.owner != data.REBEL_TAG]
            _resolve_battle(g, pid, loyal, rebs)
            continue
        # group into two sides by the first war found
        sides: tuple[list[Army], list[Army]] | None = None
        for w in g.wars.values():
            att = [a for a in armies if a.owner in w.attackers]
            dfn = [a for a in armies if a.owner in w.defenders]
            if att and dfn:
                sides = (att, dfn)
                break
        if not sides:
            continue
        _resolve_battle(g, pid, sides[0], sides[1])


def _resolve_battle(g: Game, pid: int, side_a: list[Army],
                    side_b: list[Army]):
    p = g.provinces[pid]
    rng = g.rng
    terr_bonus = data.TERRAIN[p.terrain][3]
    # defender = side whose war side controls/owns the field; approximation:
    # owner's side defends, else the side that arrived first (lower aid)
    def is_def(side):
        return any(a.owner == p.owner or p.owner in g.nations[a.owner].allies
                   for a in side)
    b_defends = is_def(side_b) and not is_def(side_a)
    name_a = g.nations[side_a[0].owner].name
    name_b = g.nations[side_b[0].owner].name
    men_a0, men_b0 = sum(a.men for a in side_a), sum(b.men for b in side_b)
    for _round in range(8):
        men_a = sum(a.men for a in side_a)
        men_b = sum(b.men for b in side_b)
        if men_a <= 0 or men_b <= 0:
            break
        if max(a.morale for a in side_a) <= 0:
            break
        if max(b.morale for b in side_b) <= 0:
            break
        gen_a = max((x.general for x in side_a), default=0)
        gen_b = max((x.general for x in side_b), default=0)
        roll_a = rng.randint(0, data.BATTLE_DICE) + gen_a + \
            (terr_bonus if not b_defends else 0)
        roll_b = rng.randint(0, data.BATTLE_DICE) + gen_b + \
            (terr_bonus if b_defends else 0)
        dmg_to_b = (roll_a + 4) * men_a * 0.006
        dmg_to_a = (roll_b + 4) * men_b * 0.006
        _apply_casualties(side_a, dmg_to_a, roll_b)
        _apply_casualties(side_b, dmg_to_b, roll_a)
    men_a = sum(a.men for a in side_a)
    men_b = sum(b.men for b in side_b)
    mor_a = max((a.morale for a in side_a), default=0)
    mor_b = max((b.morale for b in side_b), default=0)
    a_wins = (mor_a > 0 and men_a > 0) and (mor_b <= 0 or men_b <= 0 or
                                            mor_a >= mor_b)
    winner, loser = (side_a, side_b) if a_wins else (side_b, side_a)
    wname, lname = (name_a, name_b) if a_wins else (name_b, name_a)
    lost_w = (men_a0 - men_a) if a_wins else (men_b0 - men_b)
    lost_l = (men_b0 - men_b) if a_wins else (men_a0 - men_a)
    for a in loser:
        _retreat(g, a)
    # warscore from the battle
    for w in g.wars.values():
        if any(a.owner in w.attackers for a in winner) and \
           any(a.owner in w.defenders for a in loser):
            w.battles_score = min(40.0, w.battles_score + lost_l / 800)
            break
        if any(a.owner in w.defenders for a in winner) and \
           any(a.owner in w.attackers for a in loser):
            w.battles_score = max(-40.0, w.battles_score - lost_l / 800)
            break
    for nlist, exh in ((winner, 0.3), (loser, 0.8)):
        for a in nlist:
            g.nations[a.owner].war_exhaustion = min(
                15.0, g.nations[a.owner].war_exhaustion + exh)
    g.say("battle",
          f"Battle of {p.name}: {wname} defeats {lname} "
          f"({lost_w:,} vs {lost_l:,} casualties).")
    for a in list(winner) + list(loser):
        if a.men < 50 and a.aid in g.armies:
            del g.armies[a.aid]


def _apply_casualties(side: list[Army], dmg: float, enemy_roll: int):
    total = sum(a.men for a in side) or 1
    for a in side:
        share = a.men / total
        a.men = max(0, int(a.men - dmg * share))
        a.morale = max(0.0, a.morale - (0.45 + enemy_roll * 0.06) * share
                       * len(side))


def _retreat(g: Game, a: Army):
    if a.aid not in g.armies:
        return
    a.men = int(a.men * 0.85)
    a.morale = 0.4
    a.move_target = None
    if a.men < 50:
        del g.armies[a.aid]
        return
    own = [p.pid for p in g.provinces_of(a.owner) if p.pid != a.location]
    if not own:
        del g.armies[a.aid]
        return
    here = g.provinces[a.location].center
    dest = min(own, key=lambda pid:
               (g.provinces[pid].center[0] - here[0]) ** 2
               + (g.provinces[pid].center[1] - here[1]) ** 2)
    a.location = dest


def _siege_phase(g: Game):
    by_loc: dict[int, list[Army]] = {}
    for a in g.armies.values():
        by_loc.setdefault(a.location, []).append(a)
    for pid, armies in by_loc.items():
        p = g.provinces[pid]
        controller = p.occupier or p.owner
        # armies contesting the current controller (incl. owner retaking)
        hostiles = [a for a in armies
                    if a.owner != controller
                    and (g.at_war_with(a.owner, controller)
                         or (p.occupier and a.owner == p.owner))]
        if not hostiles:
            if p.sieging:
                p.sieging, p.siege_progress = None, 0.0
            continue
        a = max(hostiles, key=lambda a: a.men)
        side_tag = a.owner
        if p.sieging != side_tag:
            p.sieging, p.siege_progress = side_tag, 0.0
        fort = p.fort_level if not p.occupier else 1   # occupiers hold poorly
        gain = max(2.0, 9 + g.rng.uniform(0, 10) - fort * 4
                   + min(6.0, a.regiments * 0.7))
        p.siege_progress += gain
        if p.siege_progress >= 100:
            p.siege_progress = 0.0
            p.sieging = None
            if side_tag == p.owner or side_tag in g.nations[p.owner].allies:
                p.occupier = None
                g.say("siege", f"{g.nations[p.owner].name} retakes "
                               f"{p.name}!")
            else:
                p.occupier = side_tag
                g.nations[p.owner].war_exhaustion = min(
                    15.0, g.nations[p.owner].war_exhaustion + 0.6)
                if side_tag == data.REBEL_TAG:
                    g.say("revolt", f"Rebels seize {p.name}!")
                    if g.nations[p.owner].is_player:
                        g.pending_events.append({"notice": {
                            "title": "Province Lost to Rebels",
                            "body": f"Rebels have seized {p.name}! Send "
                                    f"an army to besiege and retake it "
                                    f"before they lay it to waste."}})
                else:
                    g.say("siege",
                          f"{g.nations[side_tag].name} occupies {p.name}!")


def _economy_phase(g: Game):
    for tag, n in g.nations.items():
        if not n.alive or tag == data.REBEL_TAG:
            continue
        income, expense, net = monthly_balance(g, tag)
        n.gold += net
        # deep debt punishes stability
        if n.gold < -50 and g.rng.random() < 0.12:
            if n.stability > data.MIN_STAB:
                n.stability -= 1
                if n.is_player:
                    g.say("econ", "Bankruptcy looms! Stability falls.")
        # full bankruptcy: debt wiped, realm shattered for years
        if n.gold < -max(100.0, income * 36):
            n.gold = 0.0
            n.stability = data.MIN_STAB
            n.prestige -= 25
            for a in g.armies_of(tag):
                a.regiments = max(1, a.regiments // 2)
                a.men = min(a.men, a.regiments * data.RECRUIT_MANPOWER)
                a.morale = 0.5
            g.say("econ", f"{n.name} declares bankruptcy! Its armies "
                          f"desert and the realm is in chaos.")


def _supply_attrition(g: Game):
    """Armies stacked beyond the local supply limit starve (monthly).

    Evaluated per (province, owner): a nation's combined regiments in a
    province are checked against the supply limit, and each of its armies
    there loses the same fraction of men. Lost men are gone for good -
    they are NOT refunded to the manpower pool. Morale is untouched.
    Runs before reinforcement, so a stack must draw fresh manpower every
    month merely to stand still.
    """
    by_key: dict[tuple[int, str], list[Army]] = {}
    for a in g.armies.values():
        by_key.setdefault((a.location, a.owner), []).append(a)
    for (pid, tag), armies in sorted(by_key.items()):
        frac = attrition_fraction(g, armies[0])
        if frac <= 0:
            continue
        for a in armies:
            a.men = max(0, a.men - max(1, int(a.men * frac)))


def _attrition_and_recovery(g: Game):
    for tag, n in g.nations.items():
        if not n.alive or tag == data.REBEL_TAG:
            continue
        at_war = bool(g.wars_of(tag))
        regen = g.manpower_max(tag) / (data.MANPOWER_REGEN_YEARS * 12)
        regen *= max(0.3, 1 - 0.05 * n.war_exhaustion)
        n.manpower = min(g.manpower_max(tag), n.manpower + regen)
        if at_war:
            # losing badly makes the realm tire twice as fast, and the
            # court starts demanding peace: refusing to end a lost war
            # must not be free.
            worst = min((w.score_for(tag) for w in g.wars_of(tag)),
                        default=0.0)
            tick = data.WAR_EXHAUSTION_MONTHLY
            if worst <= data.LOSING_BADLY:
                tick *= 2.0
            n.war_exhaustion = min(15.0, n.war_exhaustion + tick)
            if worst <= data.LOSING_BADLY and n.war_exhaustion >= 10 \
                    and n.stability > data.MIN_STAB \
                    and g.rng.random() < 0.10:
                n.stability -= 1
                if n.is_player:
                    g.say("war", "The people demand peace! Stability falls.")
        else:
            n.war_exhaustion = max(0.0, n.war_exhaustion - 0.15)
        if n.fabricating:
            pid, left = n.fabricating
            if g.provinces[pid].owner == tag:
                n.fabricating = None
            elif left <= 1:
                n.fabricating = None
                n.claims.add(pid)
                if n.is_player:
                    g.say("diplo",
                          f"Claim fabricated on {g.provinces[pid].name}!")
            else:
                n.fabricating = (pid, left - 1)
    # army reinforcement & morale recovery (rebels never reinforce)
    for a in g.armies.values():
        n = g.nations[a.owner]
        full = a.regiments * data.RECRUIT_MANPOWER
        if a.reinforce and a.owner != data.REBEL_TAG \
                and a.men < full and n.manpower > 0:
            add = min(full - a.men, int(full * 0.08) + 20, int(n.manpower))
            a.men += add
            n.manpower -= add
        cap = morale_max(g, a.owner)
        hostile = g.at_war_with(a.owner, g.provinces[a.location].owner)
        a.morale = min(cap, a.morale + (0.2 if hostile else 0.4))


def _unrest_phase(g: Game):
    """Unrest drifts toward owner-driven targets; hotspots revolt.

    Provinces held by rebels for over a year start losing development.
    """
    for p in g.provinces.values():
        n = g.nations[p.owner]
        target = (data.UNREST_STAB_COEF * max(0, -n.stability)
                  + data.UNREST_WE_COEF * n.war_exhaustion)
        if "temple" in p.buildings:
            target -= data.UNREST_TEMPLE
        target = max(0.0, min(data.UNREST_MAX, target))
        p.unrest += (target - p.unrest) * data.UNREST_MOVE_RATE
        p.unrest = max(0.0, min(data.UNREST_MAX, p.unrest))
        # devastation under prolonged rebel rule
        if p.occupier == data.REBEL_TAG:
            p.reb_months += 1
            over = p.reb_months - data.REBEL_GRACE_MONTHS
            if over > 0 and over % 12 == 0 and p.dev > 1:
                p.dev -= 1
                g.say("revolt", f"{p.name} is pillaged under rebel rule "
                                f"(dev {p.dev}).")
            continue
        p.reb_months = 0
        # revolt check
        if p.unrest < data.UNREST_REVOLT_AT:
            continue
        chance = (p.unrest - 7.0) * data.REVOLT_CHANCE_PER_POINT
        if g.rng.random() >= chance:
            continue
        regs = max(2, p.dev // 2)
        a = g.new_army(data.REBEL_TAG, p.pid, regs)
        a.name = f"{p.name} Rebels"
        p.unrest = data.UNREST_AFTER_REVOLT
        g.say("revolt", f"Revolt in {p.name}! {regs} rebel regiments "
                        f"rise against {n.name}.")
        if n.is_player:
            g.pending_events.append({"notice": {
                "title": "Revolt!",
                "body": f"Rebels rise in {p.name}! {regs} regiments of "
                        f"insurgents take the field. Crush them before "
                        f"they entrench, or the province will fall to "
                        f"rebel rule and waste away."}})


def _diplomacy_phase(g: Game):
    for tag, n in g.nations.items():
        if not n.alive or tag == data.REBEL_TAG:
            continue
        _rivals_phase(g, tag)
        # opinions drift toward 0, or toward -40 between rivals
        hostile = set(n.rivals)
        hostile |= {t for t, o in g.nations.items()
                    if o.alive and tag in o.rivals}
        for r in hostile:
            n.opinions.setdefault(r, 0.0)
        for other in list(n.opinions):
            v = n.opinions[other]
            target = (data.RIVAL_OPINION_TARGET if other in hostile
                      else 0.0)
            n.opinions[other] = v - min(0.5, max(-0.5,
                                                 (v - target) * 0.01))
        for other in list(n.ae):
            n.ae[other] = max(0.0, n.ae[other]
                              - data.AE_DECAY_PER_YEAR / 12)
        # coalition membership expires as AE decays
        if n.in_coalition_against:
            t = n.in_coalition_against
            if n.ae.get(t, 0) < data.COALITION_AE_THRESHOLD * 0.6 \
                    or not g.nations[t].alive:
                n.in_coalition_against = None


def _rivals_phase(g: Game, tag: str):
    """Drop invalid rivals; AI occasionally picks a new one.

    Rivalries are sticky: a slot only re-opens when a rival dies or
    becomes an ally.
    """
    n = g.nations[tag]
    for r in list(n.rivals):
        o = g.nations.get(r)
        if o is None or not o.alive or r in n.allies:
            n.rivals.discard(r)
    if n.is_player or len(n.rivals) >= data.MAX_RIVALS:
        return
    if g.rng.random() > data.RIVAL_PICK_CHANCE:
        return
    cands = rival_candidates(g, tag)
    if not cands:
        return
    # prefer answering someone who already rivals us, else the
    # strongest candidate; same-culture grudges weigh a little extra
    recip = [t for t in cands if tag in g.nations[t].rivals]
    pool = recip or cands
    pick = max(pool, key=lambda t: g.nation_strength(t)
               * (1.15 if g.nations[t].culture == n.culture else 1.0))
    n.rivals.add(pick)
    g.say("diplo", f"{n.name} declares {g.nations[pick].name} its rival!")
    _maybe_reciprocate_rival(g, tag, pick)


def _events_phase(g: Game):
    from . import data as d
    for tag, n in g.nations.items():
        if not n.alive or tag == d.REBEL_TAG or g.rng.random() > 0.05:
            continue
        ev = g.rng.choices(d.EVENTS, weights=[e[3] for e in d.EVENTS])[0]
        if n.is_player:
            g.pending_events.append({"event": ev[0], "tag": tag})
        else:
            choice = g.rng.randrange(len(ev[4]))
            apply_event_choice(g, tag, ev, choice)


def apply_event_choice(g: Game, tag: str, ev, choice: int):
    n = g.nations[tag]
    label, fx = ev[4][choice]
    n.gold += fx.get("gold", 0)
    n.stability = max(data.MIN_STAB, min(data.MAX_STAB,
                                         n.stability + fx.get("stability", 0)))
    n.prestige += fx.get("prestige", 0)
    if "manpower_frac" in fx:
        n.manpower = max(0.0, n.manpower * (1 + fx["manpower_frac"]))
    if "ae" in fx:
        for o in g.nations.values():
            if o.tag != tag and o.alive and o.tag != data.REBEL_TAG:
                o.ae[tag] = o.ae.get(tag, 0) + fx["ae"] * 0.3
    if fx.get("dev_capital"):
        g.provinces[n.capital].dev += fx["dev_capital"]
    if n.is_player:
        g.say("event", f"{ev[1]}: {label}")


# ---------------------------------------------------------------- missions

def _missions_phase(g: Game):
    if not g.player or g.player not in g.nations:
        return
    n = g.nations[g.player]
    if not n.alive:
        return
    tag = g.player
    for m in list(g.missions):
        if _mission_done(g, tag, m):
            g.missions.remove(m)
            n.gold += m.get("gold", 0)
            n.prestige += m.get("prestige", 0)
            g.say("event", f"Mission complete: {m['desc']} "
                           f"(+{m.get('gold', 0)}g, "
                           f"+{m.get('prestige', 0)} prestige)")
            g.pending_events.append({"mission": m})
    while len(g.missions) < 3:
        m = _gen_mission(g, tag)
        if m is None:
            break
        g.missions.append(m)


def _mission_done(g: Game, tag: str, m: dict) -> bool:
    kind = m["kind"]
    if kind == "conquer":
        return g.provinces[m["pid"]].owner == tag
    if kind == "develop":
        return g.total_dev(tag) >= m["amount"]
    if kind == "build":
        return sum(len(p.buildings)
                   for p in g.provinces_of(tag)) >= m["amount"]
    if kind == "ally":
        return bool(g.nations[tag].allies)
    if kind == "army":
        regs = sum(a.regiments for a in g.armies_of(tag))
        return regs >= g.force_limit(tag) > 0
    if kind == "stability":
        return g.nations[tag].stability >= m["amount"]
    return False


def _gen_mission(g: Game, tag: str) -> dict | None:
    active = {m["kind"] for m in g.missions}
    n = g.nations[tag]
    cands = []
    if "conquer" not in active:
        border = [p for p in g.provinces.values()
                  if p.owner != tag and g.nations[p.owner].alive
                  and p.owner not in n.allies
                  and any(g.provinces[nb].owner == tag
                          for nb in p.neighbors)]
        if border:
            p = max(border, key=lambda p: p.dev)
            cands.append({"kind": "conquer", "pid": p.pid,
                          "desc": f"Conquer {p.name}",
                          "gold": 50, "prestige": 12})
    if "develop" not in active:
        goal = g.total_dev(tag) + 10
        cands.append({"kind": "develop", "amount": goal,
                      "desc": f"Reach {goal} total development",
                      "gold": 60, "prestige": 5})
    if "build" not in active:
        goal = sum(len(p.buildings) for p in g.provinces_of(tag)) + 2
        cands.append({"kind": "build", "amount": goal,
                      "desc": f"Construct {goal} total buildings",
                      "gold": 50, "prestige": 5})
    if "ally" not in active and not n.allies:
        cands.append({"kind": "ally", "desc": "Forge an alliance",
                      "gold": 25, "prestige": 5})
    if "army" not in active:
        cands.append({"kind": "army",
                      "desc": "Field an army at your force limit",
                      "gold": 30, "prestige": 5})
    if "stability" not in active and n.stability < 2:
        cands.append({"kind": "stability", "amount": 2,
                      "desc": "Achieve +2 stability",
                      "gold": 40, "prestige": 5})
    if not cands:
        return None
    m = g.rng.choice(cands)
    if m["kind"] == "conquer":
        n.claims.add(m["pid"])
        m["desc"] += " (claim granted)"
    return m


def _check_end(g: Game):
    n = g.nations.get(g.player)
    if n and not n.alive and not g.game_over:
        g.game_over = "Your nation has been destroyed."
    # prestige slowly decays toward zero; temples add a trickle
    for tag, nat in g.nations.items():
        if not nat.alive:
            continue
        nat.prestige *= 0.999
        temples = sum(1 for p in g.provinces_of(tag)
                      if "temple" in p.buildings)
        nat.prestige += temples * 0.1 / 12
