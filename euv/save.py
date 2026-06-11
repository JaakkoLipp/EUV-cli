"""Save / load the full game state as JSON."""
from __future__ import annotations

import json
import os

from .model import Army, Game, Nation, Province, War

SAVE_PATH = os.path.expanduser("~/.euv_save.json")
AUTOSAVE_PATH = os.path.expanduser("~/.euv_autosave.json")


def save(g: Game, path: str = SAVE_PATH):
    state = {
        "seed": g.seed,
        "rng": _rng_to_json(g.rng.getstate()),
        "year": g.year, "month": g.month, "player": g.player,
        "width": g.width, "height": g.height,
        "grid": g.grid,
        "straits": sorted(list(s) for s in g.straits),
        "next_army": g._next_army, "next_war": g._next_war,
        "game_over": g.game_over,
        "pending_events": g.pending_events,
        "missions": g.missions,
        "log": g.log[-120:],
        "provinces": [{
            "pid": p.pid, "name": p.name, "terrain": p.terrain,
            "culture": p.culture, "owner": p.owner, "dev": p.dev,
            "buildings": p.buildings, "cells": p.cells, "center": p.center,
            "neighbors": sorted(p.neighbors), "coastal": p.coastal,
            "occupier": p.occupier, "siege_progress": p.siege_progress,
            "sieging": p.sieging, "unrest": p.unrest,
        } for p in g.provinces.values()],
        "nations": [{
            "tag": n.tag, "name": n.name, "culture": n.culture,
            "color": n.color, "capital": n.capital, "ruler": n.ruler,
            "is_player": n.is_player, "alive": n.alive, "gold": n.gold,
            "manpower": n.manpower, "stability": n.stability,
            "prestige": n.prestige, "war_exhaustion": n.war_exhaustion,
            "opinions": n.opinions, "ae": n.ae, "truces": n.truces,
            "allies": sorted(n.allies), "claims": sorted(n.claims),
            "fabricating": n.fabricating,
            "in_coalition_against": n.in_coalition_against,
            "last_war_month": n.last_war_month,
            "rivals": sorted(n.rivals),
        } for n in g.nations.values()],
        "armies": [{
            "aid": a.aid, "owner": a.owner, "location": a.location,
            "regiments": a.regiments, "men": a.men, "morale": a.morale,
            "move_target": a.move_target, "name": a.name,
            "general": a.general, "general_name": a.general_name,
            "reinforce": a.reinforce,
        } for a in g.armies.values()],
        "wars": [{
            "wid": w.wid, "attackers": w.attackers, "defenders": w.defenders,
            "cb_target": w.cb_target, "start": w.start, "score": w.score,
            "battles_score": w.battles_score, "name": w.name,
            "dom_months": w.dom_months, "refusals": w.refusals,
            "no_offers_until": w.no_offers_until,
            "goal_score": w.goal_score,
        } for w in g.wars.values()],
    }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def load(path: str = SAVE_PATH) -> Game:
    with open(path) as f:
        s = json.load(f)
    g = Game(s["seed"])
    g.rng.setstate(_rng_from_json(s["rng"]))
    g.year, g.month, g.player = s["year"], s["month"], s["player"]
    g.width, g.height = s["width"], s["height"]
    g.grid = s["grid"]
    g.straits = {tuple(x) for x in s["straits"]}
    g._next_army, g._next_war = s["next_army"], s["next_war"]
    g.game_over = s["game_over"]
    g.pending_events = s.get("pending_events", [])
    g.missions = s.get("missions", [])
    g.log = [tuple(e) for e in s["log"]]
    for d in s["provinces"]:
        p = Province(d["pid"], d["name"], d["terrain"], d["culture"],
                     d["owner"], d["dev"], d["buildings"],
                     [tuple(c) for c in d["cells"]], tuple(d["center"]),
                     set(d["neighbors"]), d["coastal"], d["occupier"],
                     d["siege_progress"], d["sieging"], d["unrest"])
        g.provinces[p.pid] = p
    for d in s["nations"]:
        n = Nation(d["tag"], d["name"], d["culture"], d["color"],
                   d["capital"], d["ruler"], d["is_player"], d["alive"],
                   d["gold"], d["manpower"], d["stability"], d["prestige"],
                   d["war_exhaustion"], d["opinions"], d["ae"],
                   {k: int(v) for k, v in d["truces"].items()},
                   set(d["allies"]), set(d["claims"]),
                   tuple(d["fabricating"]) if d["fabricating"] else None,
                   d["in_coalition_against"],
                   d.get("last_war_month", (s["year"] - 5) * 12),
                   set(d.get("rivals", [])))
        g.nations[n.tag] = n
    for d in s["armies"]:
        a = Army(d["aid"], d["owner"], d["location"], d["regiments"],
                 d["men"], d["morale"], d["move_target"], d["name"],
                 d.get("general", 0), d.get("general_name", ""),
                 d.get("reinforce", True))
        g.armies[a.aid] = a
    for d in s["wars"]:
        w = War(d["wid"], d["attackers"], d["defenders"], d["cb_target"],
                tuple(d["start"]), d["score"], d["battles_score"], d["name"],
                d.get("dom_months", 0), d.get("refusals", 0),
                d.get("no_offers_until", 0), d.get("goal_score", 0.0))
        g.wars[w.wid] = w
    return g


def _rng_to_json(state):
    version, internal, gauss = state
    return [version, list(internal), gauss]


def _rng_from_json(j):
    return (j[0], tuple(j[1]), j[2])
