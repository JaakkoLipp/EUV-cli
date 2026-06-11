"""Peace-pressure mechanics: refusal penalties, weariness, capitulation."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, data, engine, worldgen


def setup_losing_player():
    """ZAR (player) fully occupied by a stronger neighbour's war."""
    g = worldgen.generate(7)
    g.player = "ZAR"
    g.nations["ZAR"].is_player = True
    neigh = {g.provinces[nb].owner
             for p in g.provinces_of("ZAR") for nb in p.neighbors
             if g.provinces[nb].owner != "ZAR"}
    foe = max(neigh, key=lambda t: g.total_dev(t))
    ok, msg = engine.declare_war(g, foe, "ZAR")
    assert ok, msg
    g.pending_events.clear()
    w = next(iter(g.wars.values()))
    for p in g.provinces_of("ZAR"):
        p.occupier = foe
    for a in list(g.armies.values()):       # the field army is destroyed
        if a.owner == "ZAR":
            del g.armies[a.aid]
    w.battles_score = 40.0 if w.side_of(foe) == "att" else -40.0
    engine.update_warscore(g, w)
    assert abs(w.score_for(foe)) >= data.CAPITULATION_SCORE, w.score
    return g, w, foe


def test_refusal_penalty():
    g, w, foe = setup_losing_player()
    me = g.nations["ZAR"]
    stab0, we0 = me.stability, me.war_exhaustion
    pid = g.provinces_of("ZAR")[0].pid
    offer = {"wid": w.wid, "proposer": foe, "beneficiary": foe,
             "pids": [pid], "gold": 0,
             "cost": engine.province_peace_cost(g, w, foe, pid)}
    assert engine.peace_refusal_penalty(g, w, offer), \
        "fair demand while losing must carry a penalty"
    engine.refuse_peace(g, w, offer)
    assert me.stability == stab0 - data.REFUSAL_STAB_HIT
    assert me.war_exhaustion == we0 + data.REFUSAL_WE_HIT
    assert w.refusals == 1
    assert w.no_offers_until > g.abs_month
    # refusing the enemy's SURRENDER is free
    offer2 = dict(offer, beneficiary="ZAR")
    assert not engine.peace_refusal_penalty(g, w, offer2)
    print("ok: refusal penalties")


def test_war_weariness_spiral():
    g, w, foe = setup_losing_player()
    me = g.nations["ZAR"]
    me.war_exhaustion = 12.0
    me.stability = 3
    drops = 0
    for _ in range(24):
        before = me.stability
        engine.advance_month(g)        # no AI: war can't end by offer
        if w.wid not in g.wars:
            break                      # capitulation fired first - fine
        if me.stability < before:
            drops += 1
    assert drops > 0 or w.wid not in g.wars, \
        "losing badly at high exhaustion must threaten stability"
    print(f"ok: war weariness ({drops} stability drops before the end)")


def test_capitulation():
    g, w, foe = setup_losing_player()
    provs0 = len(g.provinces_of("ZAR"))
    for _ in range(data.CAPITULATION_MONTHS + 1):
        if w.wid not in g.wars:
            break
        engine.advance_month(g)        # player never answers any offer
    assert w.wid not in g.wars, "war must end by forced capitulation"
    left = len(g.provinces_of("ZAR"))
    assert left < provs0, "capitulation must transfer provinces"
    assert any("capitulates" in m for _, m in g.log)
    print(f"ok: capitulation ({provs0} -> {left} provinces; "
          f"{'eliminated' if not g.nations['ZAR'].alive else 'survives'})")


def test_ai_cooldown_and_escalation():
    g, w, foe = setup_losing_player()
    # partially lift occupation so the score is high but below capitulation
    for p in g.provinces_of("ZAR")[:2]:
        p.occupier = None
    w.battles_score = max(-20.0, min(20.0, w.battles_score))
    engine.update_warscore(g, w)
    g.pending_events.clear()
    engine.refuse_peace(g, w, {"wid": w.wid, "proposer": foe,
                               "beneficiary": foe, "pids": [], "gold": 0,
                               "cost": 0})
    until = w.no_offers_until
    offers = 0
    for _ in range(data.REFUSAL_COOLDOWN_MONTHS - 2):
        engine.advance_month(g, ai_module=ai)
        if w.wid not in g.wars:
            break
        offers += sum(1 for e in g.pending_events if "peace" in e)
        g.pending_events.clear()
    assert offers == 0 or g.abs_month >= until, \
        f"AI offered during cooldown ({offers} offers)"
    print("ok: AI respects refusal cooldown")


if __name__ == "__main__":
    test_refusal_penalty()
    test_war_weariness_spiral()
    test_capitulation()
    test_ai_cooldown_and_escalation()
    print("ALL PEACE-PRESSURE TESTS PASSED")
