"""Main curses application: input, game flow, menus."""
from __future__ import annotations

import curses
import os

from . import ai, data, engine, render, save, worldgen
from .model import Game
from .render import (popup_menu, popup_text, popup_toggle_list, read_key,
                     safe_addstr, show_help, show_ledger, show_log)


class UIState:
    def __init__(self):
        self.cursor = (30, 11)
        self.sel_pid: int | None = None
        self.sel_aid: int | None = None
        self.mapmode = 1
        self.mode = "normal"          # or "move"
        self.status = ""              # transient message on the key bar


def main(stdscr, seed: int | None = None):
    curses.curs_set(0)
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)   # snappy ESC; sequences arrive in one burst
    stdscr.keypad(True)
    pal = render.Palette()
    while True:
        choice = title_screen(stdscr, pal)
        if choice == "quit":
            return
        if choice == "load":
            try:
                g = save.load()
            except FileNotFoundError:
                popup_text(stdscr, pal, "Load", "No save file found.")
                continue
            except Exception as e:
                popup_text(stdscr, pal, "Load", f"Could not load save: {e}")
                continue
        else:
            g = worldgen.generate(seed if seed is not None
                                  else int.from_bytes(os.urandom(2), "big"))
            tag = nation_select(stdscr, g, pal)
            if tag is None:
                continue
            g.player = tag
            g.nations[tag].is_player = True
            engine._missions_phase(g)   # initial objectives
            g.pending_events.clear()    # no fanfare before the first turn
            g.say("event", f"You now guide the destiny of "
                           f"{g.nations[tag].name}. ({g.date_str})")
        game_loop(stdscr, g, pal)


# ------------------------------------------------------------------ screens

TITLE_ART = r"""
    ______ ____  __ __ _   __ ____   ___   ____
   / ____// __ \/ // /// | / // __ \ / _ \ / __ \
  / __/  / /_/ / \/ //  |/ // / / // // // /_/ /
 / /___ / _, _/ /\ \/ /|  // /_/ // // // _, _/
/_____//_/ |_|/_/ \_\_/ |_//_____//____//_/ |_|

        a grand strategy of the broken age
"""


def title_screen(stdscr, pal) -> str:
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    if h < render.MIN_ROWS or w < render.MIN_COLS:
        safe_addstr(stdscr, 0, 0,
                    f"Terminal too small ({w}x{h}). Need at least "
                    f"{render.MIN_COLS}x{render.MIN_ROWS}. Resize and press "
                    f"a key.")
        stdscr.refresh()
        read_key(stdscr)
        return title_screen(stdscr, pal)
    for i, line in enumerate(TITLE_ART.splitlines()):
        safe_addstr(stdscr, 2 + i, max(0, (w - len(line)) // 2), line,
                    pal.ui(3) | curses.A_BOLD)
    safe_addstr(stdscr, 12, (w - 30) // 2,
                "ERYNDOR  -  the century of blood and gold",
                curses.A_DIM)
    stdscr.refresh()
    sel = popup_menu(stdscr, pal, "Eryndor",
                     ["New Game", "Load Game", "Quit"])
    return {0: "new", 1: "load", 2: "quit", None: "quit"}[sel]


def nation_select(stdscr, g: Game, pal) -> str | None:
    tags = sorted(g.nations, key=lambda t: -g.total_dev(t))
    opts = []
    for t in tags:
        n = g.nations[t]
        dev = g.total_dev(t)
        provs = len(g.provinces_of(t))
        stars = "*" * min(5, max(1, 6 - dev // 7))
        opts.append(f"{n.name:11} {n.culture:8} {provs}p {dev:>3}dev  "
                    f"difficulty {stars}")
    info = ["Pick your nation. Fewer provinces = harder.",
            "Cultures: valdric N, lyrian W, aurean C, tervani E, qessari S"]
    sel = popup_menu(stdscr, pal, "Choose Your Nation", opts, info)
    return tags[sel] if sel is not None else None


# ---------------------------------------------------------------- game loop

def game_loop(stdscr, g: Game, pal):
    ui = UIState()
    if g.player in g.nations:
        ui.cursor = g.provinces[g.nations[g.player].capital].center
        ui.sel_pid = g.nations[g.player].capital
    while True:
        draw(stdscr, g, pal, ui)
        process_popups(stdscr, g, pal)
        if g.game_over:
            popup_text(stdscr, pal, "The End",
                       g.game_over + f"\n\nFinal score: "
                       f"{engine.score(g, g.player):.0f}")
            return
        k = read_key(stdscr)
        ui.status = ""
        if not handle_key(stdscr, g, pal, ui, k):
            return


def draw(stdscr, g, pal, ui):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    if h < render.MIN_ROWS or w < render.MIN_COLS:
        safe_addstr(stdscr, 0, 0, f"Terminal too small ({w}x{h}); need "
                                  f"{render.MIN_COLS}x{render.MIN_ROWS}.")
        stdscr.refresh()
        return
    render.draw_topbar(stdscr, g, pal)
    map_h = g.height + 2
    map_w = g.width + 2
    mapwin = stdscr.derwin(map_h, map_w, 1, 0)
    render.draw_map(mapwin, g, pal, ui)
    side = stdscr.derwin(map_h, w - map_w, 1, map_w)
    render.draw_sidebar(side, g, pal, ui)
    log_top = 1 + map_h
    render.draw_log(stdscr, g, pal, log_top, h - log_top - 1)
    render.draw_keybar(stdscr, pal, ui, ui.status)
    stdscr.refresh()


def end_turn(stdscr, g, pal, ui, months=1):
    me = g.nations[g.player]
    wars_before = len(g.wars_of(g.player))
    for _ in range(months):
        engine.advance_month(g, ai_module=ai)
        if g.pending_events or g.game_over:
            break
        if len(g.wars_of(g.player)) != wars_before:
            break
        if g.year >= data.END_YEAR and g.month == 0:
            break
    if g.year == data.END_YEAR and g.month == 0 and not g.game_over:
        final_scores(stdscr, g, pal)


def final_scores(stdscr, g, pal):
    rows = sorted((t for t, n in g.nations.items() if n.alive),
                  key=lambda t: -engine.score(g, t))
    lines = ["A century has passed. The chronicles record the great",
             "powers of the age:", ""]
    for i, t in enumerate(rows[:10]):
        n = g.nations[t]
        marker = "  <-- YOU" if t == g.player else ""
        lines.append(f"{i + 1}. {n.name:12} {engine.score(g, t):6.0f}"
                     f"{marker}")
    place = rows.index(g.player) + 1 if g.player in rows else None
    if place == 1:
        lines += ["", "You are the greatest power of the age. Victory!"]
    elif place:
        lines += ["", f"You placed {place}. The game continues if you wish."]
    popup_text(stdscr, pal, f"The Age Ends - AE {data.END_YEAR}",
               "\n".join(lines))


# ------------------------------------------------------------ input handler

def handle_key(stdscr, g, pal, ui, k) -> bool:
    me = g.nations[g.player]
    cx, cy = ui.cursor
    if k in (curses.KEY_LEFT, ord("h")):
        ui.cursor = (max(0, cx - 1), cy)
    elif k in (curses.KEY_RIGHT, ord("l")):
        ui.cursor = (min(g.width - 1, cx + 1), cy)
    elif k in (curses.KEY_UP, ord("k")):
        ui.cursor = (cx, max(0, cy - 1))
    elif k in (curses.KEY_DOWN, ord("j")):
        ui.cursor = (cx, min(g.height - 1, cy + 1))
    elif k in (10, 13, curses.KEY_ENTER):
        select_at_cursor(g, ui)
    elif k == 27 and ui.mode == "move":
        ui.mode = "normal"
        ui.status = "Move cancelled."
    elif k == ord("\t"):
        cycle_army(g, ui, 1)
    elif k == curses.KEY_BTAB:
        cycle_army(g, ui, -1)
    elif k == ord("m"):
        if ui.sel_aid in g.armies and g.armies[ui.sel_aid].owner == g.player:
            ui.mode = "move"
            ui.status = "Select destination, then Enter."
        else:
            ui.status = "Select one of your armies first (Tab)."
    elif k == ord("x"):
        if ui.sel_aid in g.armies and g.armies[ui.sel_aid].owner == g.player:
            ok, msg = engine.split_army(g, ui.sel_aid)
            ui.status = msg
    elif k == ord("X"):
        if ui.sel_aid in g.armies and g.armies[ui.sel_aid].owner == g.player:
            if popup_menu(stdscr, pal, "Disband army?",
                          ["Yes, disband", "No"]) == 0:
                ok, msg = engine.disband_army(g, ui.sel_aid)
                ui.sel_aid = None
                ui.status = msg
    elif k == ord("r"):
        if ui.sel_pid is not None:
            ok, msg = engine.recruit(g, g.player, ui.sel_pid)
            ui.status = msg
    elif k == ord("d"):
        if ui.sel_pid is not None:
            ok, msg = engine.develop(g, g.player, ui.sel_pid)
            ui.status = msg
    elif k == ord("b"):
        if ui.sel_pid is not None:
            build_menu(stdscr, g, pal, ui)
    elif k == ord("c"):
        if ui.sel_pid is not None:
            ok, msg = engine.fabricate_claim(g, g.player, ui.sel_pid)
            ui.status = msg
    elif k == ord("D"):
        diplomacy_menu(stdscr, g, pal, ui)
    elif k == ord("+"):
        ok, msg = engine.raise_stability(g, g.player)
        ui.status = msg
    elif k == ord("o"):
        show_ledger(stdscr, g, pal)
    elif k == ord("g"):
        show_log(stdscr, g, pal)
    elif k in (ord("?"), curses.KEY_F1):
        show_help(stdscr, pal)
    elif k in (ord("1"), ord("2"), ord("3"), ord("4")):
        ui.mapmode = k - ord("0")
    elif k == ord(" "):
        end_turn(stdscr, g, pal, ui)
    elif k == ord(">"):
        end_turn(stdscr, g, pal, ui, months=12)
    elif k == ord("S"):
        save.save(g)
        ui.status = f"Saved to {save.SAVE_PATH}"
    elif k == ord("L"):
        try:
            g2 = save.load()
            g.__dict__.update(g2.__dict__)
            ui.status = "Game loaded."
        except Exception as e:
            ui.status = f"Load failed: {e}"
    elif k == ord("q"):
        sel = popup_menu(stdscr, pal, "Quit?",
                         ["Save and quit", "Quit without saving", "Cancel"])
        if sel == 0:
            save.save(g)
            return False
        if sel == 1:
            return False
    return True


def select_at_cursor(g, ui):
    cx, cy = ui.cursor
    pid = g.grid[cy][cx]
    if ui.mode == "move" and ui.sel_aid in g.armies:
        if pid < 0:
            ui.status = "Cannot march into the sea."
            return
        ok, msg = engine.move_army(g, ui.sel_aid, pid)
        ui.status = msg
        if ok:
            ui.mode = "normal"
        return
    if pid < 0:
        ui.sel_pid = None
        ui.sel_aid = None
        return
    here = [a for a in g.armies.values()
            if a.location == pid and a.owner == g.player]
    if ui.sel_pid == pid and here:
        # already selected: cycle own armies on this province
        if ui.sel_aid in [a.aid for a in here]:
            idx = [a.aid for a in here].index(ui.sel_aid)
            ui.sel_aid = here[(idx + 1) % len(here)].aid
        else:
            ui.sel_aid = here[0].aid
    else:
        ui.sel_pid = pid
        ui.sel_aid = here[0].aid if here else None


def cycle_army(g, ui, step):
    mine = sorted(g.armies_of(g.player), key=lambda a: a.aid)
    if not mine:
        ui.status = "You have no armies. Recruit with [r]."
        return
    ids = [a.aid for a in mine]
    if ui.sel_aid in ids:
        i = (ids.index(ui.sel_aid) + step) % len(ids)
    else:
        i = 0
    a = mine[i]
    ui.sel_aid = a.aid
    ui.sel_pid = a.location
    ui.cursor = g.provinces[a.location].center


# -------------------------------------------------------------------- menus

def build_menu(stdscr, g, pal, ui):
    p = g.provinces[ui.sel_pid]
    if p.owner != g.player:
        ui.status = "Not your province."
        return
    opts, keys = [], []
    for key, (name, cost, desc, *_rest) in data.BUILDINGS.items():
        state = ""
        if key in p.buildings:
            state = " (built)"
        opts.append(f"{name:10} {cost:>4}g  {desc}{state}")
        keys.append(key)
    info = [f"{p.name}: {len(p.buildings)}/{data.MAX_BUILDINGS} slots, "
            f"treasury {g.nations[g.player].gold:.0f}g"]
    sel = popup_menu(stdscr, pal, "Construct Building", opts, info)
    if sel is not None:
        ok, msg = engine.build(g, g.player, ui.sel_pid, keys[sel])
        ui.status = msg


def diplomacy_menu(stdscr, g, pal, ui):
    # pick target nation: owner of selected province, or from a list
    target = None
    if ui.sel_pid is not None and g.provinces[ui.sel_pid].owner != g.player:
        target = g.provinces[ui.sel_pid].owner
    if target is None:
        tags = sorted((t for t, n in g.nations.items()
                       if n.alive and t != g.player),
                      key=lambda t: -g.total_dev(t))
        opts = [f"{g.nations[t].name:12} "
                f"opinion {g.nations[t].opinion_of(g.player):+4.0f}"
                for t in tags]
        sel = popup_menu(stdscr, pal, "Diplomacy with...", opts)
        if sel is None:
            return
        target = tags[sel]
    nation_diplomacy(stdscr, g, pal, ui, target)


def nation_diplomacy(stdscr, g, pal, ui, target):
    me = g.nations[g.player]
    o = g.nations[target]
    at_war = g.at_war_with(g.player, target)
    info = [f"{o.name} - {o.ruler}",
            f"Opinion of you {o.opinion_of(g.player):+.0f}, "
            f"AE {o.ae.get(g.player, 0):.0f}, "
            f"dev {g.total_dev(target)}"]
    opts = []
    actions = []
    if at_war:
        opts.append("Negotiate peace")
        actions.append("peace")
    else:
        opts.append(f"Improve relations ({data.IMPROVE_COST}g)")
        actions.append("improve")
        if target in me.allies:
            opts.append("Break alliance")
            actions.append("break")
        else:
            opts.append("Offer alliance")
            actions.append("ally")
        claim = next((pid for pid in me.claims
                      if g.provinces[pid].owner == target), None)
        cb = "claim" if claim is not None else \
            f"NO CB: -{data.WAR_STAB_HIT_NO_CB} stability"
        if g.truce_between(g.player, target):
            yrs = (me.truces[target] - g.abs_month) // 12 + 1
            opts.append(f"Declare war (TRUCE, ~{yrs}y left!)")
        else:
            opts.append(f"Declare war ({cb})")
        actions.append("war")
    sel = popup_menu(stdscr, pal, f"Diplomacy: {o.name}", opts, info)
    if sel is None:
        return
    act = actions[sel]
    if act == "improve":
        ok, msg = engine.improve_relations(g, g.player, target)
    elif act == "ally":
        ok, msg = engine.offer_alliance(g, g.player, target)
    elif act == "break":
        ok, msg = engine.break_alliance(g, g.player, target)
    elif act == "war":
        extra = ""
        if g.truce_between(g.player, target):
            extra = ("\n\nBreaking a truce is dishonorable: "
                     "-1 stability extra, -10 prestige.")
        conf = popup_menu(stdscr, pal, f"Declare war on {o.name}?" + extra,
                          ["To war!", "Not yet"])
        if conf != 0:
            return
        if g.truce_between(g.player, target):
            me.truces.pop(target, None)
            o.truces.pop(g.player, None)
            me.stability = max(data.MIN_STAB, me.stability - 1)
            me.prestige -= 10
        ok, msg = engine.declare_war(g, g.player, target)
    elif act == "peace":
        peace_menu(stdscr, g, pal, ui, target)
        return
    ui.status = msg


def peace_menu(stdscr, g, pal, ui, target):
    w = next((w for w in g.wars_of(g.player)
              if w.side_of(target) and
              w.side_of(target) != w.side_of(g.player)), None)
    if w is None:
        ui.status = "No active war with them."
        return
    leader = (w.attackers if w.side_of(g.player) == "att" else w.defenders)[0]
    if leader != g.player:
        ui.status = f"{g.nations[leader].name} leads this war; " \
                    f"only the war leader may negotiate."
        return
    my = w.score_for(g.player)
    enemy_leader = w.enemies_of(g.player)[0]
    mode = popup_menu(
        stdscr, pal, f"Peace: {w.name}",
        ["Demand terms (you take)", "Offer concessions (you give)",
         "Offer white peace"],
        [f"Your warscore: {my:+.0f}%"])
    if mode is None:
        return
    if mode == 2:
        ok, msg = engine.offer_peace(g, w, g.player, [], 0)
        ui.status = msg
        return
    if mode == 0:
        victim, taker = enemy_leader, g.player
    else:
        victim, taker = g.player, enemy_leader
    items = []
    pids = []
    for p in sorted(g.provinces_of(victim), key=lambda p: -p.dev):
        cost = engine.province_peace_cost(g, w, taker, p.pid)
        occ = " [occupied]" if p.occupier else ""
        claim = " [claim]" if p.pid in g.nations[taker].claims \
            or p.pid == w.cb_target else ""
        items.append((f"{p.name} (dev {p.dev}){occ}{claim}", cost))
        pids.append(p.pid)
    budget = my if mode == 0 else -my + 15
    res = popup_toggle_list(
        stdscr, pal,
        "Demand provinces" if mode == 0 else "Offer provinces",
        items, budget, "warscore",
        extra_label="Gold demanded" if mode == 0 else "Gold offered",
        extra_step=25, extra_cost_per=1 / data.PEACE_GOLD_PER_WARSCORE)
    if res is None:
        return
    chosen, gold = res
    take = [pids[i] for i in chosen]
    ok, msg = engine.offer_peace(g, w, g.player, take, gold,
                                 beneficiary=taker)
    ui.status = msg


# ------------------------------------------------------------------- popups

def process_popups(stdscr, g, pal):
    while g.pending_events:
        ev = g.pending_events.pop(0)
        if "event" in ev:
            handle_event_popup(stdscr, g, pal, ev)
        elif "peace" in ev:
            handle_peace_popup(stdscr, g, pal, ev["peace"])
        elif "alliance" in ev:
            handle_alliance_popup(stdscr, g, pal, ev["alliance"])
        elif "cta" in ev:
            handle_cta_popup(stdscr, g, pal, ev["cta"])
        elif "mission" in ev:
            m = ev["mission"]
            popup_text(stdscr, pal, "Mission Complete!",
                       f"{m['desc']}\n\nReward: {m.get('gold', 0)} gold, "
                       f"{m.get('prestige', 0)} prestige.")


def handle_event_popup(stdscr, g, pal, ev):
    event = next((e for e in data.EVENTS if e[0] == ev["event"]), None)
    if event is None:
        return
    _, title, text, _, choices = event
    body = text.format(nation=g.nations[g.player].name)
    sel = popup_text(stdscr, pal, title, body, [c[0] for c in choices])
    engine.apply_event_choice(g, g.player, event, sel)


def handle_peace_popup(stdscr, g, pal, offer):
    w = g.wars.get(offer["wid"])
    if w is None or not w.side_of(g.player):
        return
    prop = g.nations[offer["proposer"]]
    ben = offer["beneficiary"]
    pids = offer["pids"]
    gold = offer["gold"]
    my = w.score_for(g.player)
    if ben == g.player or (w.side_of(ben) == w.side_of(g.player)):
        kind = f"{prop.name} offers to surrender:"
    else:
        kind = f"{prop.name} demands:"
    terms = [g.provinces[pid].name + f" (dev {g.provinces[pid].dev})"
             for pid in pids if pid in g.provinces]
    if gold > 0:
        terms.append(f"{gold:.0f} gold")
    if not terms:
        terms = ["White peace (status quo)"]
    body = (f"{kind}\n\n  " + "\n  ".join(terms)
            + f"\n\nYour warscore: {my:+.0f}%")
    sel = popup_text(stdscr, pal, f"Peace offer - {w.name}", body,
                     ["Accept", "Refuse"])
    if sel == 0:
        engine.execute_peace(g, w, ben, pids, gold)
    else:
        g.say("diplo", f"You refused the peace offer from {prop.name}.")


def handle_alliance_popup(stdscr, g, pal, tag):
    o = g.nations[tag]
    if not o.alive or tag in g.nations[g.player].allies:
        return
    body = (f"{o.name} ({o.ruler}) proposes a formal alliance.\n\n"
            f"Their strength: dev {g.total_dev(tag)}, "
            f"~{sum(a.regiments for a in g.armies_of(tag))} regiments.\n"
            f"Their opinion of you: {o.opinion_of(g.player):+.0f}")
    sel = popup_text(stdscr, pal, "An Offer of Alliance", body,
                     ["Accept alliance", "Decline"])
    if sel == 0:
        me = g.nations[g.player]
        me.allies.add(tag)
        o.allies.add(g.player)
        g.say("diplo", f"You are now allied with {o.name}.")
    else:
        o.opinions[g.player] = o.opinion_of(g.player) - 10


def handle_cta_popup(stdscr, g, pal, cta):
    w = g.wars.get(cta["wid"])
    if w is None:
        return
    caller = g.nations[cta["caller"]]
    side = cta["side"]
    enemy = (w.defenders if side == "att" else w.attackers)[0]
    if g.at_war_with(g.player, enemy) or w.side_of(g.player):
        return
    body = (f"{caller.name} calls you to arms in the {w.name}, "
            f"against {g.nations[enemy].name}.\n\n"
            f"Refusing will end the alliance and stain your honor "
            f"(-10 prestige).")
    sel = popup_text(stdscr, pal, "Call to Arms!", body,
                     ["Honor the alliance (join the war)",
                      "Refuse (break alliance, -10 prestige)"])
    me = g.nations[g.player]
    if sel == 0:
        (w.attackers if side == "att" else w.defenders).append(g.player)
        g.say("war", f"You join the {w.name} on the side of "
                     f"{caller.name}.")
    else:
        engine.break_alliance(g, g.player, caller.tag)
        me.prestige -= 10


def run(seed: int | None = None):
    curses.wrapper(main, seed)
