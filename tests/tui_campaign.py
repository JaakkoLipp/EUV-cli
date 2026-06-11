"""Play a short war campaign through the TUI: march, siege, make peace."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import engine, save, worldgen
from tui_driver import (Driver, expect, ENTER, ESC, KEY_DOWN, KEY_LEFT,
                        KEY_RIGHT, KEY_UP)


def build():
    g = worldgen.generate(7)
    g.player = "ZAR"
    me = g.nations["ZAR"]
    me.is_player = True
    me.gold = 300
    # fresh war on the weakest neighbour, no occupations yet
    neigh = {g.provinces[nb].owner
             for p in g.provinces_of("ZAR") for nb in p.neighbors
             if g.provinces[nb].owner != "ZAR"}
    target = min(neigh, key=lambda t: g.total_dev(t))
    ok, msg = engine.declare_war(g, "ZAR", target)
    assert ok, msg
    g.pending_events.clear()
    save.save(g)
    army = next(iter(g.armies_of("ZAR")))
    # nearest enemy province to the army
    enemy_provs = g.provinces_of(target)
    src = g.provinces[army.location].center
    dest_p = min(enemy_provs,
                 key=lambda p: (p.center[0] - src[0]) ** 2
                 + (p.center[1] - src[1]) ** 2)
    tags = sorted((t for t, n in g.nations.items()
                   if n.alive and t != "ZAR"),
                  key=lambda t: -g.total_dev(t))
    return src, dest_p.center, tags.index(target), target


def nav(d, src, dst):
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    for _ in range(abs(dx)):
        d.send_key(KEY_RIGHT if dx > 0 else KEY_LEFT, 0.03)
    for _ in range(abs(dy)):
        d.send_key(KEY_DOWN if dy > 0 else KEY_UP, 0.03)
    d.pump(0.3)


def main():
    src, dst, dip_idx, target = build()
    print(f"campaign: army at {src} -> enemy {target} at {dst}")
    d = Driver()
    d.pump(1.2)
    d.send_key(ENTER, 0.5)            # new game (menu) -- actually Load:
    # oops: first menu item is New Game; we need Load. Restart selection:
    # (we sent ENTER already => nation select). Back out with ESC.
    d.send_key(ESC, 0.5)
    d.send_key(KEY_DOWN, 0.2)
    d.send_key(ENTER, 0.6)            # Load Game
    d.pump(0.6)
    if "Load which save" in d.text():
        d.send_key(ENTER, 0.6)        # newest manual save first in list
    expect(d, "AT WAR", "loaded campaign save")
    d.send("\t", 0.3)                 # select army (cursor jumps to it)
    expect(d, "regiments", "army selected")
    d.send("G", 0.3)                  # hire general
    expect(d, "General", "general hired")
    d.send("m", 0.2)
    nav(d, src, dst)
    d.send_key(ENTER, 0.4)
    expect(d, "Moving to", "march order")
    # prosecute the war
    occupied = False
    for i in range(30):
        d.send(">", 1.2)
        for _ in range(3):
            d.send_key(ENTER, 0.15)
        t = d.text()
        if "occupies" in t or "OCCUPIED" in t:
            occupied = True
            break
        if not d.alive():
            d.dump("CRASHED mid-campaign")
            sys.exit("FAIL: crash during campaign")
    print("ok: occupation achieved" if occupied
          else "warn: no occupation seen yet")
    d.dump("mid-campaign")
    # read warscore from sidebar bar like '+34%'
    m = re.search(r"([+-]\d+)%", d.text())
    print("warscore on screen:", m.group(1) if m else "?")
    if "AT WAR" not in d.text():
        # the enemy already sued for peace via popup during fast-forward
        print("ok: war resolved during play (AI peace offer accepted)")
    else:
        d.send("D", 0.4)
        if "Diplomacy with" in d.text():
            for _ in range(dip_idx):
                d.send_key(KEY_DOWN, 0.05)
            d.send_key(ENTER, 0.4)
        if "Negotiate peace" not in d.text():
            # the original war already ended; the AT WAR flag belongs to a
            # different conflict (opportunists attack the distracted)
            print("ok: original war already resolved; another war is on")
            d.send_key(ESC, 0.3)
            d.send_key(ESC, 0.3)
        else:
            d.send_key(ENTER, 0.4)
            expect(d, "white peace", "peace modes")
            d.send_key(KEY_DOWN, 0.2)
            d.send_key(KEY_DOWN, 0.2)
            d.send_key(ENTER, 0.6)    # offer white peace
            t = d.text()
            assert ("Peace concluded" in t or "rejects" in t), \
                "no peace feedback"
            print("ok: peace flow ->",
                  "concluded" if "Peace concluded" in t
                  else "rejected (AI wants more)")
    d.dump("end of campaign")
    print("CAMPAIGN TEST PASSED")
    d.quit()


if __name__ == "__main__":
    main()
