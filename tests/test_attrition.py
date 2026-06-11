"""Supply limits, attrition and the reinforcement toggle (headless)."""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, data, engine, worldgen


def fresh(seed=7):
    g = worldgen.generate(seed)
    g.player = ""               # all AI
    return g


def clear_armies(g):
    for aid in list(g.armies):
        del g.armies[aid]


def test_supply_limit_formula():
    g = fresh()
    for p in g.provinces.values():
        base = (data.SUPPLY_BASE + math.ceil(p.dev * data.SUPPLY_PER_DEV)
                + data.SUPPLY_TERRAIN.get(p.terrain, 0))
        own = engine.supply_limit(g, p.owner, p.pid)
        assert own == max(1, base + data.SUPPLY_FRIENDLY_BONUS), \
            (p.pid, p.terrain, p.dev, own)
        foreign = next(t for t in g.nations
                       if t != p.owner
                       and p.owner not in g.nations[t].allies)
        assert engine.supply_limit(g, foreign, p.pid) == max(1, base)
    # terrain malus visible: same dev, mountains supply less than plains
    devs = {}
    for p in g.provinces.values():
        devs.setdefault((p.terrain, p.dev), p)
    for (terr, dev), p in devs.items():
        if terr in data.SUPPLY_TERRAIN and ("plains", dev) in devs:
            q = devs[("plains", dev)]
            assert engine.supply_limit(g, p.owner, p.pid) \
                == engine.supply_limit(g, q.owner, q.pid) \
                + data.SUPPLY_TERRAIN[terr]
    print("ok: supply limit formula (terrain + friendly bonus)")


def test_attrition_over_supply():
    g = fresh()
    clear_armies(g)
    tag = next(iter(g.nations))
    pid = g.nations[tag].capital
    limit = engine.supply_limit(g, tag, pid)
    a = g.new_army(tag, pid, limit * 2)          # 100% over the limit
    men0 = a.men
    morale0 = a.morale
    mp0 = g.nations[tag].manpower
    engine._supply_attrition(g)
    lost = men0 - a.men
    expect = int(men0 * data.ATTRITION_PER_EXCESS)   # 3% * (2 - 1), no war
    assert lost == max(1, expect), (lost, expect)
    assert a.morale == morale0, "attrition must not touch morale"
    assert g.nations[tag].manpower == mp0, "lost men must not be refunded"
    print(f"ok: over-supply attrition ({lost} men lost, morale intact)")


def test_no_attrition_at_or_under_limit():
    g = fresh()
    clear_armies(g)
    tag = next(iter(g.nations))
    pid = g.nations[tag].capital
    limit = engine.supply_limit(g, tag, pid)
    a = g.new_army(tag, pid, limit)              # exactly at the limit
    men0 = a.men
    engine._supply_attrition(g)
    assert a.men == men0, "army at the limit must not starve"
    assert engine.attrition_fraction(g, a) == 0.0
    print("ok: no attrition at/under the supply limit")


def test_hostile_surcharge():
    g = fresh()
    clear_armies(g)
    tags = sorted(g.nations)
    me, foe = tags[0], tags[1]
    g.nations[me].allies.discard(foe)
    g.nations[foe].allies.discard(me)
    pid = g.nations[foe].capital
    limit_for_me = engine.supply_limit(g, me, pid)
    a = g.new_army(me, pid, limit_for_me * 2)
    frac_peace = engine.attrition_fraction(g, a)
    g.new_war([me], [foe], None)
    frac_war = engine.attrition_fraction(g, a)
    assert abs(frac_war - frac_peace - data.ATTRITION_HOSTILE) < 1e-9, \
        (frac_peace, frac_war)
    men0 = a.men
    engine._supply_attrition(g)
    assert men0 - a.men == max(1, int(men0 * frac_war))
    print(f"ok: hostile surcharge ({frac_peace:.3f} -> {frac_war:.3f})")


def test_per_owner_stacking():
    """Two friendly armies on one spot are summed against the limit."""
    g = fresh()
    clear_armies(g)
    tag = next(iter(g.nations))
    pid = g.nations[tag].capital
    limit = engine.supply_limit(g, tag, pid)
    a = g.new_army(tag, pid, limit)              # each fits alone...
    b = g.new_army(tag, pid, limit)              # ...but not together
    men_a, men_b = a.men, b.men
    assert engine.attrition_fraction(g, a) > 0
    engine._supply_attrition(g)
    assert a.men < men_a and b.men < men_b, \
        "splitting a doomstack in place must not dodge attrition"
    print("ok: per-owner stacking rule (co-located armies summed)")


def test_reinforce_toggle():
    g = fresh()
    clear_armies(g)
    tag = next(iter(g.nations))
    n = g.nations[tag]
    pid = n.capital
    a = g.new_army(tag, pid, 2)
    a.men = 1000                                 # half strength
    n.manpower = 5000
    a.reinforce = False
    engine._attrition_and_recovery(g)
    assert a.men == 1000, "reinforce=False must stop reinforcement"
    a.reinforce = True
    engine._attrition_and_recovery(g)
    assert a.men > 1000, "reinforce=True must refill from manpower"
    print("ok: reinforcement toggle")


class _PeacefulAI:
    """AI that runs economy + army control but never starts wars."""

    @staticmethod
    def run_all(g):
        for tag in sorted(g.nations):
            n = g.nations[tag]
            if not n.alive or n.is_player:
                continue
            ai._economy(g, tag)
            ai._military(g, tag)


def test_peaceful_ai_manpower_trends_up():
    g = fresh(7)
    # deterministic environment: no random events (plague etc.)
    events = engine._events_phase
    engine._events_phase = lambda g: None
    try:
        for _ in range(24):                      # settle: clamp + recruiting
            engine.advance_month(g, ai_module=_PeacefulAI)
        assert not g.wars, "peaceful AI must not be at war"
        start = {t: n.manpower for t, n in g.nations.items() if n.alive}
        for _ in range(10 * 12):
            engine.advance_month(g, ai_module=_PeacefulAI)
        for t, mp0 in start.items():
            n = g.nations[t]
            assert n.manpower >= mp0 - 1e-6, \
                (f"{t} bled manpower in peacetime: "
                 f"{mp0:.0f} -> {n.manpower:.0f}")
            # trends UP: grows 20%+, or sits near the (growing) cap
            assert n.manpower >= min(mp0 * 1.2,
                                     0.9 * g.manpower_max(t)), \
                (f"{t} manpower stagnated: {mp0:.0f} -> "
                 f"{n.manpower:.0f} (max {g.manpower_max(t):.0f})")
        lo = min(g.nations[t].manpower / g.manpower_max(t) for t in start)
    finally:
        engine._events_phase = events
    print(f"ok: peaceful AI manpower trends up "
          f"({len(start)} nations, worst pool {lo:.0%} of max after 10y)")


if __name__ == "__main__":
    test_supply_limit_formula()
    test_attrition_over_supply()
    test_no_attrition_at_or_under_limit()
    test_hostile_surcharge()
    test_per_owner_stacking()
    test_reinforce_toggle()
    test_peaceful_ai_manpower_trends_up()
    print("ALL ATTRITION TESTS PASSED")
