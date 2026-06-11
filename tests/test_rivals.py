"""Rivalries, ticking war-goal warscore, stability cost scaling."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, data, engine, save, worldgen


def fresh(seed=7):
    g = worldgen.generate(seed)
    g.player = ""   # all AI
    return g


def two_nations(g):
    """Two distinct alive nations, deterministic order."""
    tags = sorted(t for t, n in g.nations.items() if n.alive)
    return tags[0], tags[1]


def test_rivals_emerge():
    g = fresh(7)
    first = None
    for m in range(20 * 12):
        engine.advance_month(g, ai_module=ai)
        if first is None and any(n.rivals for n in g.nations.values()):
            first = m / 12
    assert first is not None, "no rivalries formed within 20 years"
    pairs = mutual = 0
    for t, n in g.nations.items():
        if not n.alive:
            continue
        assert len(n.rivals) <= data.MAX_RIVALS, f"{t} has >2 rivals"
        for r in n.rivals:
            assert g.nations[r].alive, "rival of a dead nation kept"
            assert r not in n.allies, "rival is also an ally"
            pairs += 1
            mutual += t in g.nations[r].rivals
    assert pairs > 0
    print(f"ok: rivalries emerge (first after {first:.1f}y; "
          f"{pairs} links, {mutual} reciprocated)")


def test_rival_opinion_drift():
    g = fresh(7)
    a, b = two_nations(g)
    g.nations[a].rivals.add(b)
    for _ in range(300):
        engine._diplomacy_phase(g)
    # both directions drift toward -40 (a rivals b => mutual pressure)
    assert g.nations[b].opinion_of(a) <= -35, g.nations[b].opinion_of(a)
    assert g.nations[a].opinion_of(b) <= -35, g.nations[a].opinion_of(b)
    assert g.nations[b].opinion_of(a) >= -45
    print("ok: opinions drift toward -40 between rivals")


def test_improve_relations_blocked():
    g = fresh(7)
    tags = sorted(t for t, n in g.nations.items() if n.alive)
    a, b, c = tags[0], tags[1], tags[2]
    g.nations[a].rivals.add(b)
    for t in (a, b, c):
        g.nations[t].gold = 1000.0
    ok, msg = engine.improve_relations(g, a, b)
    assert not ok and "rival" in msg.lower(), msg
    ok, msg = engine.improve_relations(g, b, a)   # reverse direction too
    assert not ok and "rival" in msg.lower(), msg
    assert g.nations[a].gold == 1000.0, "gold spent on blocked action"
    ok, _ = engine.improve_relations(g, a, c)
    assert ok, "non-rival improve must still work"
    print("ok: improve relations blocked between rivals")


def test_goal_score_ticks_and_flips():
    g = fresh(7)
    a, b = two_nations(g)
    p = g.provinces_of(b)[0]
    w = g.new_war([a], [b], p.pid)
    for _ in range(10):
        engine._tick_goal_score(g, w)
    # defender owns the goal -> ticks against the attacker
    assert abs(w.goal_score - (-10 * data.GOAL_SCORE_MONTHLY)) < 1e-9
    p.occupier = a                     # attacker takes the goal
    for _ in range(20):
        engine._tick_goal_score(g, w)
    assert w.goal_score > 0, "goal score must flip with control"
    for _ in range(500):
        engine._tick_goal_score(g, w)
    assert w.goal_score == data.GOAL_SCORE_CAP, "cap at +20"
    # warscore sum includes goal_score
    w.battles_score = 0.0
    engine.update_warscore(g, w)
    expect = max(-100.0, min(100.0, engine.occupation_score(g, w)
                             + w.goal_score))
    assert abs(w.score - expect) < 1e-9
    # an ally on a side counts as control for that side
    g2 = fresh(13)
    t2 = sorted(t for t, n in g2.nations.items() if n.alive)
    a2, b2, c2 = t2[0], t2[1], t2[2]
    p2 = g2.provinces_of(b2)[0]
    w2 = g2.new_war([a2, c2], [b2], p2.pid)
    p2.occupier = c2
    engine._tick_goal_score(g2, w2)
    assert w2.goal_score == data.GOAL_SCORE_MONTHLY, "ally control counts"
    print("ok: war-goal warscore ticks, flips, caps, and is summed")


def test_stability_cost_scales():
    g = fresh(7)
    tags = sorted((t for t, n in g.nations.items() if n.alive),
                  key=lambda t: g.total_dev(t))
    small, big = tags[0], tags[-1]
    assert g.total_dev(small) < g.total_dev(big)
    for t in (small, big):
        g.nations[t].stability = 0
        g.nations[t].gold = 100000.0
    base = data.STAB_COST + 40 * 3
    for t in (small, big):
        before = g.nations[t].gold
        ok, _ = engine.raise_stability(g, t)
        assert ok
        spent = before - g.nations[t].gold
        want = int(base * (1 + g.total_dev(t) / data.STAB_DEV_DIVISOR))
        assert spent == want, (t, spent, want)
    cost_small = int(base * (1 + g.total_dev(small)
                             / data.STAB_DEV_DIVISOR))
    cost_big = int(base * (1 + g.total_dev(big) / data.STAB_DEV_DIVISOR))
    assert cost_big > cost_small, "bigger realm must pay more"
    print(f"ok: stability cost scales with dev "
          f"({cost_small}g vs {cost_big}g)")


def test_rival_peace_prestige():
    g = fresh(7)
    # loser must keep >1 province so it is not annexed mid-peace
    tags = sorted((t for t, n in g.nations.items() if n.alive),
                  key=lambda t: -len(g.provinces_of(t)))
    a, b = tags[0], tags[1]
    g.nations[a].rivals.add(b)
    take = next(p for p in g.provinces_of(b)
                if p.pid != g.nations[b].capital)
    w = g.new_war([a], [b], None)
    pa0, pb0 = g.nations[a].prestige, g.nations[b].prestige
    engine.execute_peace(g, w, a, [take.pid], 0)
    gain = take.dev * 0.5 + data.RIVAL_PRESTIGE_STAKE
    assert abs(g.nations[a].prestige - (pa0 + gain)) < 1e-9
    assert abs(g.nations[b].prestige
               - (pb0 - data.RIVAL_PRESTIGE_STAKE)) < 1e-9
    # white peace between rivals carries no prestige stake
    g2 = fresh(7)
    g2.nations[a].rivals.add(b)
    w2 = g2.new_war([a], [b], None)
    pa0, pb0 = g2.nations[a].prestige, g2.nations[b].prestige
    engine.execute_peace(g2, w2, a, [], 0)
    assert g2.nations[a].prestige == pa0
    assert g2.nations[b].prestige == pb0
    print("ok: prestige stakes on rival peace (none on white peace)")


def test_end_rivalry_costs_prestige():
    g = fresh(7)
    a, b = two_nations(g)
    g.nations[a].rivals.add(b)
    p0 = g.nations[a].prestige
    ok, _ = engine.end_rivalry(g, a, b)
    assert ok
    assert b not in g.nations[a].rivals
    assert g.nations[a].prestige == p0 - data.END_RIVAL_PRESTIGE
    ok, _ = engine.end_rivalry(g, a, b)
    assert not ok, "cannot end a rivalry twice"
    print("ok: ending a rivalry costs prestige")


def test_save_roundtrip():
    g = fresh(7)
    a, b = two_nations(g)
    g.nations[a].rivals = {b}
    g.nations[b].rivals = {a}
    pid = g.provinces_of(b)[0].pid
    w = g.new_war([a], [b], pid)
    w.goal_score = -7.5
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "save.json")
        save.save(g, path)
        g2 = save.load(path)
    assert g2.nations[a].rivals == {b}
    assert g2.nations[b].rivals == {a}
    assert g2.wars[w.wid].goal_score == -7.5
    print("ok: save/load roundtrip keeps rivals and goal_score")


if __name__ == "__main__":
    test_rival_opinion_drift()
    test_improve_relations_blocked()
    test_goal_score_ticks_and_flips()
    test_stability_cost_scales()
    test_rival_peace_prestige()
    test_end_rivalry_costs_prestige()
    test_save_roundtrip()
    test_rivals_emerge()
    print("ALL RIVALRY/WAR-GOAL/STABILITY TESTS PASSED")
