"""Fuzz the TUI with random keys; the game must never crash."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tui_driver import Driver, ENTER, ESC, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_UP

KEYS = (list("hjkl mrRbdcDxi+og12345?>") + ["\t"]
        + [None] * 0)
SPECIALS = [ENTER, ESC, KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT]


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    rng = random.Random(seed)
    d = Driver()
    d.pump(1.2)
    d.send_key(ENTER, 0.5)        # new game
    d.send_key(ENTER, 0.8)        # first nation
    n = 350
    for i in range(n):
        if rng.random() < 0.25:
            d.send_key(rng.choice(SPECIALS), 0.04)
        else:
            d.send(rng.choice(KEYS), 0.04)
        if i % 50 == 49:
            d.pump(0.6)
            if not d.alive():
                d.dump(f"CRASHED at key {i}")
                sys.exit(f"FAIL: crashed after ~{i} random keys")
            print(f"...{i + 1} keys, alive")
    # never let fuzz quit the app via 'q' menu: 'q' opens quit menu, but
    # ESC/other keys usually cancel it; if it quit, that's fine too as
    # long as it didn't crash with a traceback.
    d.pump(1.0)
    print("FUZZ COMPLETE — no crash")
    d.quit()


if __name__ == "__main__":
    main()
