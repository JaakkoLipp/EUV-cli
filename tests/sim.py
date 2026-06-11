"""Headless balance/stability simulation: run the world all-AI for N years."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from euv import ai, engine, worldgen


def run(seed=7, years=100, verbose=True):
    g = worldgen.generate(seed)
    g.player = ""   # all AI
    start_nations = sum(1 for n in g.nations.values()
                    if n.alive and n.tag != 'REB')
    wars_seen = 0
    for _ in range(years * 12):
        before = len(g.wars)
        engine.advance_month(g, ai_module=ai)
        if len(g.wars) > before:
            wars_seen += len(g.wars) - before
    alive = [t for t, n in g.nations.items()
         if n.alive and t != 'REB']
    if verbose:
        print(f"seed={seed} after {years}y: {len(alive)}/{start_nations} "
              f"nations alive, {wars_seen} wars started, "
              f"{len(g.wars)} ongoing")
        rank = sorted(alive, key=lambda t: -engine.score(g, t))
        for t in rank:
            n = g.nations[t]
            print(f"  {t} {n.name:10} provs={len(g.provinces_of(t)):2} "
                  f"dev={g.total_dev(t):3} gold={n.gold:7.0f} "
                  f"mp={n.manpower:6.0f} stab={n.stability:+d} "
                  f"armies={sum(a.regiments for a in g.armies_of(t))} "
                  f"score={engine.score(g, t):.0f}")
        cats = {}
        for c, _ in g.log:
            cats[c] = cats.get(c, 0) + 1
        print("  log:", cats)
    # sanity assertions
    assert alive, "everyone died"
    assert wars_seen > 0, "no wars ever happened"
    for t in alive:
        assert g.nations[t].gold > -100000, f"{t} runaway debt"
    total_provs = sum(len(g.provinces_of(t)) for t in alive)
    assert total_provs == len(g.provinces), "provinces lost owner"
    return g


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    run(seed, years)
