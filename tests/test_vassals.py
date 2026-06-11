"""Vassals, cores & reconquest mechanics (headless)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, data, engine, save, worldgen


def fresh(seed=7):
    g = worldgen.generate(seed)
    g.player = ""
    return g


def neighbours_of(g, t):
    out = {g.provinces[nb].owner
           for p in g.provinces_of(t) for nb in p.neighbors
           if g.provinces[nb].owner != t}
    return sorted(x for x in out if x != data.REBEL_TAG)


def pick_pair(g, min_provs=1):
    """A nation and its smallest neighbour (cheap to vassalize)."""
    for t in sorted(g.nations):
        if t == data.REBEL_TAG:
            continue
        nbs = [x for x in neighbours_of(g, t)
               if len(g.provinces_of(x)) >= min_provs]
        if nbs:
            b = min(nbs, key=lambda x: g.total_dev(x))
            return t, b
    raise AssertionError("no neighbour pair found")


def crush(g, w, winner, loser):
    """Occupy the loser completely and max the battle score."""
    for p in g.provinces_of(loser):
        p.occupier = winner
    w.battles_score = 40.0 if w.side_of(winner) == "att" else -40.0
    engine.update_warscore(g, w)


def make_vassal(g, lord, vassal, months_ago=0):
    g.nations[vassal].overlord = lord
    g.nations[vassal].vassal_since = g.abs_month - months_ago


# ------------------------------------------------------------------- tests

def test_vassalize_peace():
    g = fresh()
    a, b = pick_pair(g)
    ok, msg = engine.declare_war(g, a, b)
    assert ok, msg
    w = next(iter(g.wars.values()))
    crush(g, w, a, b)
    third = [t for t, n in g.nations.items()
             if t not in (a, b, data.REBEL_TAG) and n.alive]
    ae0 = {t: g.nations[t].ae.get(a, 0) for t in third}
    ok, msg = engine.offer_peace(g, w, a, [], 0, vassalize=True)
    assert ok, msg
    nb = g.nations[b]
    assert nb.overlord == a, "loser must become the vassal"
    assert nb.vassal_since == g.abs_month
    assert g.truce_between(a, b), "vassalize peace must set a truce"
    assert g.provinces_of(b), "vassalized nation keeps its provinces"
    assert not nb.allies, "a new vassal keeps no alliances"
    gained = [t for t in third if g.nations[t].ae.get(a, 0) > ae0[t]]
    assert gained, "vassalization must cause AE among third parties"
    # the AE is scaled down vs full conquest of the same dev
    t = gained[0]
    full = data.AE_PER_DEV_TAKEN * g.total_dev(b)
    assert g.nations[t].ae.get(a, 0) - ae0[t] <= \
        full * data.VASSAL_AE_MULT + 1e-9
    print("ok: vassalize peace (overlord, truce, AE)")


def test_tribute():
    g = fresh()
    a, b = pick_pair(g)
    make_vassal(g, a, b)
    for arm in list(g.armies.values()):     # ensure b runs a surplus
        if arm.owner == b:
            del g.armies[arm.aid]
    _, _, net = engine.monthly_balance(g, b)
    assert net > 0, "test setup: vassal must be in the black"
    gold_a = g.nations[a].gold
    gold_b = g.nations[b].gold
    engine._subjects_phase(g)
    paid = net * data.VASSAL_TRIBUTE_FRAC
    assert abs(g.nations[a].gold - (gold_a + paid)) < 1e-6
    assert abs(g.nations[b].gold - (gold_b - paid)) < 1e-6
    print("ok: tribute flows to the overlord")


def test_vassal_joins_wars():
    g = fresh()
    a, b = pick_pair(g)
    v = next(t for t in sorted(g.nations)
             if t not in (a, b, data.REBEL_TAG))
    make_vassal(g, a, v)
    # overlord attacks: vassal joins the attackers
    ok, msg = engine.declare_war(g, a, b)
    assert ok, msg
    w = next(iter(g.wars.values()))
    assert v in w.attackers, "vassal must join its overlord's war"
    del g.wars[w.wid]
    # overlord is attacked: vassal joins the defenders
    for n in g.nations.values():
        n.truces.clear()
    ok, msg = engine.declare_war(g, b, a)
    assert ok, msg
    w = next(iter(g.wars.values()))
    assert v in w.defenders, "vassal must defend its overlord"
    print("ok: vassal auto-joins overlord's wars (both directions)")


def test_war_on_vassal_redirects():
    g = fresh()
    a, b = pick_pair(g)
    make_vassal(g, a, b)
    c = next(t for t in sorted(g.nations)
             if t not in (a, b, data.REBEL_TAG))
    ok, msg = engine.declare_war(g, c, b)
    assert ok, msg
    w = next(iter(g.wars.values()))
    assert w.defenders[0] == a, "war on a vassal must hit the overlord"
    assert b in w.defenders, "the vassal still fights"
    assert "overlord" in msg
    # and you cannot attack your own vassal at all
    del g.wars[w.wid]
    ok, msg = engine.declare_war(g, a, b)
    assert not ok and "your vassal" in msg
    print("ok: war on a vassal redirects to the overlord")


def test_independence():
    g = fresh()
    a, b = pick_pair(g)
    v2 = next(t for t in sorted(g.nations)
              if t not in (a, b, data.REBEL_TAG))
    make_vassal(g, a, b)
    make_vassal(g, a, v2)
    ok, msg = engine.declare_war(g, b, a, independence=True)
    assert ok, msg
    w = next(iter(g.wars.values()))
    assert w.independence
    assert v2 in w.attackers, "fellow vassals rise together"
    # rebels win: white peace on non-negative score frees them all
    w.score = 0.0
    engine.execute_peace(g, w, b, [], 0)
    assert g.nations[b].overlord is None
    assert g.nations[v2].overlord is None
    # second act: a new vassalage, and this time the overlord wins
    for n in g.nations.values():
        n.truces.clear()
    make_vassal(g, a, b)
    ok, msg = engine.declare_war(g, b, a, independence=True)
    assert ok, msg
    w = next(iter(g.wars.values()))
    crush(g, w, a, b)
    engine.execute_peace(g, w, a, [], 50)   # overlord exacts tribute
    assert g.nations[b].overlord == a, "failed independence persists"
    assert g.truce_between(a, b)
    print("ok: independence war frees (or fails to free) vassals")


def test_diplo_annex():
    g = fresh()
    a, b = pick_pair(g)
    make_vassal(g, a, b, months_ago=data.ANNEX_MIN_VASSAL_MONTHS)
    # not yet: a fresh vassal, a hostile vassal, a busy overlord
    g.nations[b].opinions[a] = -5
    ok, msg = engine.start_annex_vassal(g, a, b)
    assert not ok and "resent" in msg
    g.nations[b].opinions[a] = 10
    ok, msg = engine.start_annex_vassal(g, a, b)
    assert ok, msg
    assert g.nations[a].annexing == (b, data.ANNEX_VASSAL_MONTHS)
    provs_b = [p.pid for p in g.provinces_of(b)]
    for _ in range(data.ANNEX_VASSAL_MONTHS):
        engine._subjects_phase(g)
    assert g.nations[a].annexing is None
    assert not g.nations[b].alive, "vassal must be integrated"
    for pid in provs_b:
        p = g.provinces[pid]
        assert p.owner == a
        assert a not in p.cores, "integrated land is not auto-cored"
        assert p.owner_since == g.abs_month
    assert any("integrated" in m for _, m in g.log)
    print("ok: diplomatic annexation completes on the timer")


def test_release_vassal():
    g = fresh()
    a, b = pick_pair(g)
    make_vassal(g, a, b)
    pres0 = g.nations[a].prestige
    ok, msg = engine.release_vassal(g, a, b)
    assert ok, msg
    assert g.nations[b].overlord is None
    assert g.nations[a].prestige == pres0 + 5
    print("ok: release vassal")


def test_coring():
    g = fresh()
    a, b = pick_pair(g)
    p = g.provinces_of(a)[0]
    p.cores = {b}
    p.owner_since = g.abs_month - data.CORE_MONTHS
    engine._subjects_phase(g)
    assert p.cores == {a}, "long-held land cores; foreign cores fade"
    # a freshly taken province does not core
    q = g.provinces_of(a)[1]
    q.cores = {b}
    q.owner_since = g.abs_month - data.CORE_MONTHS + 2
    engine._subjects_phase(g)
    assert q.cores == {b}
    print("ok: coring after CORE_MONTHS removes foreign cores")


def test_non_core_tax():
    g = fresh()
    a, _ = pick_pair(g)
    p = g.provinces_of(a)[0]
    assert p.cores == {a}
    full = p.tax_income()
    p.cores = {"XXX"}
    assert abs(p.tax_income() - full * data.NON_CORE_TAX_MULT) < 1e-9
    print("ok: non-core tax penalty")


def test_reconquest_discount_and_ae():
    g = fresh()
    a, b = pick_pair(g, min_provs=2)
    p = next(q for q in g.provinces_of(b) if q.pid != g.nations[b].capital)
    ok, msg = engine.declare_war(g, a, b)
    assert ok, msg
    w = next(iter(g.wars.values()))
    assert p.pid != w.cb_target and p.pid not in g.nations[a].claims
    plain = engine.province_peace_cost(g, w, a, p.pid)
    assert abs(plain - p.dev * 1.6) < 1e-9
    p.cores.add(a)
    cored = engine.province_peace_cost(g, w, a, p.pid)
    assert abs(cored - plain * data.CORE_PEACE_DISCOUNT) < 1e-9, \
        "core reconquest must be cheaper"
    # reduced AE on reconquest
    crush(g, w, a, b)
    third = next(t for t, n in g.nations.items()
                 if t not in (a, b, data.REBEL_TAG) and n.alive)
    ae0 = g.nations[third].ae.get(a, 0)
    dist = 1.0 if any(g.provinces[nb].owner == third
                      for nb in p.neighbors) else 0.5
    engine.execute_peace(g, w, a, [p.pid], 0)
    delta = g.nations[third].ae.get(a, 0) - ae0
    want = data.AE_PER_DEV_TAKEN * p.dev * dist * data.CORE_RECONQUEST_AE
    assert abs(delta - want) < 1e-9, f"AE {delta} != {want}"
    print("ok: core reconquest discount + reduced AE")


def test_save_load_roundtrip():
    g = fresh()
    a, b = pick_pair(g)
    make_vassal(g, a, b, months_ago=7)
    g.nations[a].annexing = (b, 9)
    p = g.provinces_of(b)[0]
    p.cores = {a, b}
    p.owner_since = 123
    ok, msg = engine.declare_war(g, b, a, independence=True)
    assert ok, msg
    path = os.path.join(tempfile.mkdtemp(), "save.json")
    save.save(g, path)
    g2 = save.load(path)
    assert g2.nations[b].overlord == a
    assert g2.nations[b].vassal_since == g.nations[b].vassal_since
    assert g2.nations[a].annexing == (b, 9)
    p2 = g2.provinces[p.pid]
    assert p2.cores == {a, b}
    assert p2.owner_since == 123
    w2 = next(iter(g2.wars.values()))
    assert w2.independence
    # backward compatibility: old saves lack the new keys entirely
    import json
    with open(path) as f:
        s = json.load(f)
    for d in s["provinces"]:
        d.pop("cores"), d.pop("owner_since")
    for d in s["nations"]:
        d.pop("overlord"), d.pop("vassal_since"), d.pop("annexing")
    for d in s["wars"]:
        d.pop("independence")
    with open(path, "w") as f:
        json.dump(s, f)
    g3 = save.load(path)
    assert g3.nations[b].overlord is None
    assert g3.nations[a].annexing is None
    assert g3.provinces[p.pid].cores == {g3.provinces[p.pid].owner}
    assert g3.provinces[p.pid].owner_since == 0
    assert not next(iter(g3.wars.values())).independence
    print("ok: save/load roundtrip + backward compatibility")


if __name__ == "__main__":
    test_vassalize_peace()
    test_tribute()
    test_vassal_joins_wars()
    test_war_on_vassal_redirects()
    test_independence()
    test_diplo_annex()
    test_release_vassal()
    test_coring()
    test_non_core_tax()
    test_reconquest_discount_and_ae()
    test_save_load_roundtrip()
    print("ALL VASSAL/CORE TESTS PASSED")
