"""Rebels & unrest: revolts fire, get suppressed, and persist in saves."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, data, engine, save, worldgen


def test_conquest_revolt():
    """A freshly conquered province can revolt while anger is hot."""
    g = worldgen.generate(7)
    tag = "ZAR"
    p = g.provinces_of(tag)[0]
    p.unrest = data.UNREST_CONQUEST
    # keep the owner troubled so the target stays high-ish
    g.nations[tag].stability = -3
    g.nations[tag].war_exhaustion = 12.0
    for a in list(g.armies.values()):       # nobody suppresses
        del g.armies[a.aid]
    spawned = False
    for _ in range(48):
        engine.advance_month(g)             # no AI
        if any(a.location == p.pid for a in g.armies_of(data.REBEL_TAG)):
            spawned = True
            break
    assert spawned, "high unrest never produced a revolt"
    print("ok: conquest-anger revolt spawns")


def test_rebels_take_and_owner_retakes():
    g = worldgen.generate(7)
    tag = "ZAR"
    p = g.provinces_of(tag)[0]
    for a in list(g.armies.values()):
        del g.armies[a.aid]
    reb = g.new_army(data.REBEL_TAG, p.pid, 6)
    reb.name = "Test Rebels"
    for _ in range(24):
        engine.advance_month(g)
        if p.occupier == data.REBEL_TAG:
            break
    assert p.occupier == data.REBEL_TAG, "rebels never sieged the province"
    # the owner sends a strong army to retake it
    g.new_army(tag, p.pid, 12)
    for _ in range(24):
        engine.advance_month(g)
        if p.occupier is None:
            break
    assert p.occupier is None, "owner could not retake from rebels"
    print("ok: rebels occupy, owner retakes")


def test_save_roundtrip_mid_revolt():
    g = worldgen.generate(7)
    p = g.provinces_of("ZAR")[0]
    g.new_army(data.REBEL_TAG, p.pid, 4)
    p.occupier = data.REBEL_TAG
    p.reb_months = 5
    p.unrest = 7.7
    path = "/tmp/euv_test_rebels.json"
    save.save(g, path)
    g2 = save.load(path)
    p2 = g2.provinces[p.pid]
    assert p2.occupier == data.REBEL_TAG
    assert p2.reb_months == 5 and abs(p2.unrest - 7.7) < 1e-9
    assert any(a.owner == data.REBEL_TAG for a in g2.armies.values())
    assert data.REBEL_TAG in g2.nations
    engine.advance_month(g2, ai)            # must not crash
    print("ok: save/load roundtrip mid-revolt")


def test_peaceful_nation_stays_quiet():
    g = worldgen.generate(7)
    tag = "ZAR"
    g.nations[tag].stability = 3
    for _ in range(120):
        engine.advance_month(g)             # no AI: nobody declares wars
        rebs = [a for a in g.armies_of(data.REBEL_TAG)
                if g.provinces[a.location].owner == tag]
        assert not rebs, "revolt in a stable, peaceful nation"
    print("ok: stable peaceful nation has no revolts")


if __name__ == "__main__":
    test_conquest_revolt()
    test_rebels_take_and_owner_retakes()
    test_save_roundtrip_mid_revolt()
    test_peaceful_nation_stays_quiet()
    print("ALL REBEL/UNREST TESTS PASSED")
