"""TUI war-flow test: load a crafted at-war save, negotiate peace, move army."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import engine, save, worldgen
from tui_driver import Driver, expect, ENTER, ESC, KEY_DOWN, KEY_RIGHT


def build_save():
    g = worldgen.generate(7)
    g.player = "ZAR"
    g.nations["ZAR"].is_player = True
    # find a weak neighbour of ZAR
    neigh = {g.provinces[nb].owner
             for p in g.provinces_of("ZAR") for nb in p.neighbors
             if g.provinces[nb].owner != "ZAR"}
    target = min(neigh, key=lambda t: g.total_dev(t))
    ok, msg = engine.declare_war(g, "ZAR", target)
    assert ok, msg
    w = next(iter(g.wars.values()))
    # simulate total occupation -> ~100% warscore
    for t in w.enemies_of("ZAR"):
        for p in g.provinces_of(t):
            p.occupier = "ZAR"
    engine.update_warscore(g, w)
    assert w.score_for("ZAR") > 60, w.score
    save.save(g)
    # diplomacy list is sorted by -dev among alive non-player nations
    tags = sorted((t for t, n in g.nations.items()
                   if n.alive and t != "ZAR"),
                  key=lambda t: -g.total_dev(t))
    return tags.index(w.enemies_of("ZAR")[0]), target


def main():
    idx, target = build_save()
    print(f"target index in diplomacy list: {idx} ({target})")
    d = Driver()
    d.pump(1.2)
    expect(d, "New Game", "title screen")
    d.send_key(KEY_DOWN, 0.2)
    d.send_key(ENTER, 0.8)                     # Load Game
    if "Load which save" in d.text():
        d.send_key(ENTER, 0.8)                 # manual save is listed first
    expect(d, "AT WAR", "loaded at-war game")
    d.send("D", 0.5)
    expect(d, "Diplomacy with...", "diplomacy list")
    for _ in range(idx):
        d.send_key(KEY_DOWN, 0.1)
    d.send_key(ENTER, 0.5)
    expect(d, "Negotiate peace", "war diplomacy menu")
    d.send_key(ENTER, 0.5)                     # negotiate peace
    expect(d, "Demand terms", "peace mode menu")
    d.send_key(ENTER, 0.5)                     # demand terms
    expect(d, "Demand provinces", "province toggle list")
    d.send(" ", 0.3)                           # toggle first province
    d.send_key(ENTER, 0.8)                     # offer
    expect(d, "Peace concluded", "peace accepted")
    d.dump("after peace")
    # army movement
    d.send("\t", 0.3)
    expect(d, "regiments", "army selected")
    d.send("m", 0.3)
    expect(d, "MOVE", "move mode banner")
    for _ in range(4):
        d.send_key(KEY_RIGHT, 0.1)
    d.send_key(ENTER, 0.5)
    txt = d.text()
    assert ("Moving to" in txt or "Order cancelled" in txt
            or "No route" in txt or "march" in txt), "no move feedback"
    print("ok: move order feedback")
    d.send(" ", 1.0)                           # end turn
    d.send_key(ENTER, 0.3)
    if not d.alive():
        d.dump("CRASHED")
        sys.exit("FAIL: died after war flow")
    print("ALL WAR-FLOW CHECKS PASSED")
    d.quit()


if __name__ == "__main__":
    main()
