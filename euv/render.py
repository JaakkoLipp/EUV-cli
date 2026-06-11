"""Curses rendering: palette, map, panels, popups."""
from __future__ import annotations

import curses
import textwrap

from . import data
from .model import Game

MAP_W, MAP_H = 60, 22
SIDEBAR_MIN = 36
MIN_COLS, MIN_ROWS = 100, 30


class Palette:
    """Color pair management with 256-color and 8-color fallbacks."""

    N_BG = 30        # pair base: nation backgrounds
    N_FG = 60        # pair base: nation foregrounds
    T_BG = 90        # terrain backgrounds
    DEV = 110        # development heat
    UI = 130         # ui pairs
    MIL = 150        # military mode terrain: own/ally/enemy/truce/neutral
    CHIP = 160       # military mode army chips: own/ally/enemy/neutral

    NATION_256 = [167, 68, 71, 178, 133, 208, 37, 168, 101, 107,
                  73, 131, 144, 246]
    NATION_8 = [curses.COLOR_RED, curses.COLOR_BLUE, curses.COLOR_GREEN,
                curses.COLOR_YELLOW, curses.COLOR_MAGENTA,
                curses.COLOR_CYAN, curses.COLOR_WHITE]
    TERRAIN_256 = {"plains": 106, "forest": 28, "hills": 137,
                   "mountains": 245, "desert": 179, "marsh": 65}
    TERRAIN_8 = {"plains": curses.COLOR_GREEN, "forest": curses.COLOR_GREEN,
                 "hills": curses.COLOR_YELLOW,
                 "mountains": curses.COLOR_WHITE,
                 "desert": curses.COLOR_YELLOW, "marsh": curses.COLOR_CYAN}
    DEV_256 = [52, 88, 130, 100, 64, 28, 22]
    DEV_8 = [curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN]

    def __init__(self):
        curses.start_color()
        curses.use_default_colors()
        self.has256 = curses.COLORS >= 256
        black = curses.COLOR_BLACK
        if self.has256:
            for i, c in enumerate(self.NATION_256):
                curses.init_pair(self.N_BG + i, black, c)
                curses.init_pair(self.N_FG + i, c, -1)
            for i, (t, c) in enumerate(self.TERRAIN_256.items()):
                curses.init_pair(self.T_BG + i, black, c)
            self._terr_idx = {t: i for i, t in
                              enumerate(self.TERRAIN_256)}
            for i, c in enumerate(self.DEV_256):
                curses.init_pair(self.DEV + i, black, c)
            self.dev_levels = len(self.DEV_256)
            curses.init_pair(self.UI + 0, 250, 17)      # sea
            for i, (fg, bg) in enumerate([(252, 22), (252, 24), (252, 52),
                                          (250, 58), (245, 235)]):
                curses.init_pair(self.MIL + i, fg, bg)
            for i, (fg, bg) in enumerate([(16, 40), (16, 45), (231, 160),
                                          (16, 250)]):
                curses.init_pair(self.CHIP + i, fg, bg)
        else:
            for i, c in enumerate(self.NATION_8):
                curses.init_pair(self.N_BG + i, black, c)
                curses.init_pair(self.N_FG + i, c, -1)
            for i, (t, c) in enumerate(self.TERRAIN_8.items()):
                curses.init_pair(self.T_BG + i, black, c)
            self._terr_idx = {t: i for i, t in enumerate(self.TERRAIN_8)}
            for i, c in enumerate(self.DEV_8):
                curses.init_pair(self.DEV + i, black, c)
            self.dev_levels = len(self.DEV_8)
            curses.init_pair(self.UI + 0, curses.COLOR_CYAN,
                             curses.COLOR_BLUE)
            white, red = curses.COLOR_WHITE, curses.COLOR_RED
            green, cyan = curses.COLOR_GREEN, curses.COLOR_CYAN
            yellow = curses.COLOR_YELLOW
            for i, (fg, bg) in enumerate([(black, green), (black, cyan),
                                          (white, red), (black, yellow),
                                          (white, black)]):
                curses.init_pair(self.MIL + i, fg, bg)
            for i, (fg, bg) in enumerate([(black, green), (black, cyan),
                                          (white, red), (black, white)]):
                curses.init_pair(self.CHIP + i, fg, bg)
        # generic ui pairs
        curses.init_pair(self.UI + 1, curses.COLOR_BLACK,
                         curses.COLOR_WHITE)                   # status bar
        curses.init_pair(self.UI + 2, curses.COLOR_RED, -1)    # war
        curses.init_pair(self.UI + 3, curses.COLOR_YELLOW, -1) # battle/warn
        curses.init_pair(self.UI + 4, curses.COLOR_CYAN, -1)   # diplo
        curses.init_pair(self.UI + 5, curses.COLOR_GREEN, -1)  # econ/good
        curses.init_pair(self.UI + 6, curses.COLOR_MAGENTA, -1)  # event
        curses.init_pair(self.UI + 7, curses.COLOR_WHITE, curses.COLOR_RED)

    def nation_bg(self, color_idx: int) -> int:
        n = len(self.NATION_256 if self.has256 else self.NATION_8)
        return curses.color_pair(self.N_BG + color_idx % n)

    def nation_fg(self, color_idx: int) -> int:
        n = len(self.NATION_256 if self.has256 else self.NATION_8)
        return curses.color_pair(self.N_FG + color_idx % n) | curses.A_BOLD

    def terrain_bg(self, terr: str) -> int:
        return curses.color_pair(self.T_BG + self._terr_idx[terr])

    def dev_bg(self, dev: int) -> int:
        lvl = min(self.dev_levels - 1, dev * self.dev_levels // 25)
        return curses.color_pair(self.DEV + lvl)

    def sea(self):
        return curses.color_pair(self.UI + 0)

    def mil(self, rel: int) -> int:
        return curses.color_pair(self.MIL + rel)

    def chip(self, rel: int) -> int:
        return curses.color_pair(self.CHIP + min(rel, 3))

    def ui(self, i: int) -> int:
        return curses.color_pair(self.UI + i)

    def log_attr(self, cat: str) -> int:
        return {"war": self.ui(2), "battle": self.ui(3),
                "siege": self.ui(3), "diplo": self.ui(4),
                "econ": self.ui(5), "event": self.ui(6)}.get(cat, 0)


def read_key(win) -> int:
    """getch that also decodes raw ESC-sequences for arrows/backtab.

    Some terminals send normal-mode sequences (ESC [ B) even when
    ncurses expects application mode (ESC O B); handle both.
    """
    k = win.getch()
    if k != 27:
        return k
    win.nodelay(True)
    try:
        k2 = win.getch()
        if k2 in (ord("["), ord("O")):
            k3 = win.getch()
            return {ord("A"): curses.KEY_UP, ord("B"): curses.KEY_DOWN,
                    ord("C"): curses.KEY_RIGHT, ord("D"): curses.KEY_LEFT,
                    ord("Z"): curses.KEY_BTAB}.get(k3, 27)
        return 27   # bare escape (k2 == -1) or unknown sequence
    finally:
        win.nodelay(False)


def safe_addstr(win, y, x, s, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    if x < 0:
        s = s[-x:]
        x = 0
    try:
        win.addstr(y, x, s[:w - x], attr)
    except curses.error:
        pass


# ------------------------------------------------------------------ the map

def rel_to_player(g: Game, tag: str) -> int:
    """0 own, 1 ally, 2 at war, 3 truce, 4 neutral (vs the player)."""
    me = g.player
    if not me or me not in g.nations:
        return 4
    if tag == me:
        return 0
    n = g.nations[me]
    if tag in n.allies:
        return 1
    if g.at_war_with(me, tag):
        return 2
    if g.truce_between(me, tag):
        return 3
    return 4


def cell_attr(g: Game, pal: Palette, ui, x: int, y: int):
    """(char, attr) for one map cell."""
    pid = g.grid[y][x]
    if pid < 0:
        return "~", pal.sea() | curses.A_DIM
    p = g.provinces[pid]
    glyph = data.TERRAIN[p.terrain][1]
    mode = ui.mapmode
    if mode == 1:       # political
        attr = pal.nation_bg(g.nations[p.owner].color)
        if p.occupier and (x + y) % 2 == 0:
            attr = pal.nation_bg(g.nations[p.occupier].color)
    elif mode == 2:     # terrain
        attr = pal.terrain_bg(p.terrain)
    elif mode == 3:     # development
        attr = pal.dev_bg(p.dev)
    elif mode == 4:     # diplomatic
        me = g.player
        n = g.nations[me] if me in g.nations else None
        owner = p.owner
        if owner == me:
            attr = pal.ui(5) | curses.A_REVERSE
        elif n and owner in n.allies:
            attr = pal.ui(4) | curses.A_REVERSE
        elif n and g.at_war_with(me, owner):
            attr = pal.ui(7)
        elif n and g.truce_between(me, owner):
            attr = pal.ui(3) | curses.A_REVERSE
        else:
            attr = pal.ui(1)
    else:               # military: muted relationship tints; units pop
        attr = pal.mil(rel_to_player(g, p.owner))
        if p.occupier and (x + y) % 2 == 0:
            attr = pal.mil(rel_to_player(g, p.occupier))
    if ui.sel_pid == pid:
        attr |= curses.A_BOLD
    return glyph, attr


def draw_map(win, g: Game, pal: Palette, ui):
    from . import engine
    win.erase()
    win.box()
    title = {1: "POLITICAL", 2: "TERRAIN", 3: "DEVELOPMENT",
             4: "DIPLOMATIC", 5: "MILITARY"}[ui.mapmode]
    safe_addstr(win, 0, 2, f"[ Eryndor - {title} ]", curses.A_BOLD)
    for y in range(g.height):
        for x in range(g.width):
            ch, attr = cell_attr(g, pal, ui, x, y)
            safe_addstr(win, y + 1, x + 1, ch, attr)
    sel_army = g.armies.get(ui.sel_aid) if ui.sel_aid is not None else None
    # province tags at centers
    for p in g.provinces.values():
        cx, cy = p.center
        if ui.mapmode == 1:
            label = p.owner
            base = pal.nation_bg(g.nations[p.owner].color)
        elif ui.mapmode == 3:
            label = f"{p.dev:2d}"
            base = pal.dev_bg(p.dev)
        else:
            label = p.owner
            _, base = cell_attr(g, pal, ui, cx, cy)
        attr = base | curses.A_BOLD
        if ui.mapmode == 5 and p.sieging:
            # siege progress replaces the tag where it matters most
            label = f"{min(99, int(p.siege_progress)):2d}%"
            attr = pal.ui(7) | curses.A_BOLD
        if (ui.mapmode == 5 and sel_army is not None
                and sel_army.owner == g.player
                and sel_army.move_target == p.pid):
            attr = pal.ui(3) | curses.A_REVERSE | curses.A_BOLD
        if p.pid == ui.sel_pid:
            attr = base | curses.A_REVERSE | curses.A_BOLD
        safe_addstr(win, cy + 1, cx, label, attr)
        if p.sieging and ui.mapmode != 5:
            safe_addstr(win, cy + 1, cx + len(label),
                        "!", pal.ui(7) | curses.A_BOLD)
    # armies
    by_prov: dict[int, list] = {}
    for a in g.armies.values():
        by_prov.setdefault(a.location, []).append(a)
    for pid, armies in by_prov.items():
        p = g.provinces[pid]
        cx, cy = p.center
        owners = {a.owner for a in armies}
        total = sum(a.regiments for a in armies)
        if ui.mapmode == 5:
            if len(owners) > 1:
                # a battle: show the odds of the two biggest sides
                by_owner: dict[str, int] = {}
                for a in armies:
                    by_owner[a.owner] = by_owner.get(a.owner, 0) \
                        + a.regiments
                top = sorted(by_owner.values(), reverse=True)
                marker = f"{min(top[0], 99)}v{min(top[1], 99)}"
                attr = pal.chip(2) | curses.A_BOLD
            else:
                o = next(iter(owners))
                lead = max(armies, key=lambda a: a.men)
                cap = engine.morale_max(g, o)
                frac = lead.morale / cap if cap else 1.0
                glyph = "*" if frac >= 0.66 else \
                    ("o" if frac >= 0.33 else "x")
                marker = f"{glyph}{min(total, 99)}"
                attr = pal.chip(rel_to_player(g, o)) | curses.A_BOLD
        elif len(owners) > 1:
            marker = f"*{min(total, 99)}"
            attr = pal.ui(7) | curses.A_BOLD
        else:
            o = next(iter(owners))
            marker = f"*{min(total, 99)}"
            attr = pal.nation_fg(g.nations[o].color)
            if o == g.player:
                attr |= curses.A_UNDERLINE
        # find a spot just below or above the tag, inside the province
        spot = None
        for dy in (1, -1, 2):
            cand = [(cx + dx, cy + dy) for dx in (-1, 0)]
            if all(0 <= xx < g.width and 0 <= yy < g.height
                   and g.grid[yy][xx] == pid for xx, yy in cand):
                spot = cand[0]
                break
        if spot is None:
            spot = (cx - 3, cy)
        sel = sel_army is not None and sel_army.location == pid
        if sel:
            attr |= curses.A_REVERSE
        safe_addstr(win, spot[1] + 1, spot[0] + 1, marker, attr)
    # cursor: invert whatever is rendered beneath it
    cx, cy = ui.cursor
    try:
        under = win.inch(cy + 1, cx + 1)
        ch = chr(under & 0xFF)
        attr = under & ~0xFF
        win.addstr(cy + 1, cx + 1, ch, attr ^ curses.A_REVERSE)
    except (curses.error, ValueError):
        pass
    if ui.mode == "move":
        safe_addstr(win, g.height + 1, 2,
                    "[ MOVE: select destination, Enter confirm, Esc cancel ]",
                    pal.ui(3) | curses.A_BOLD)


# ----------------------------------------------------------------- top bar

def draw_topbar(scr, g: Game, pal: Palette):
    _, w = scr.getmaxyx()
    n = g.nations[g.player]
    income, expense, net = _balance(g)
    safe_addstr(scr, 0, 0, " " * w, pal.ui(1))
    fl = sum(a.regiments for a in g.armies_of(g.player))
    flmax = g.force_limit(g.player)
    parts = [
        f" {n.name}",
        f"{g.date_str}",
        f"Gold {n.gold:,.0f} ({net:+.1f})",
        f"MP {n.manpower:,.0f}",
        f"Stab {n.stability:+d}",
        f"Pres {n.prestige:.0f}",
        f"Army {fl}/{flmax}",
    ]
    text = " | ".join(parts)
    wars = g.wars_of(g.player)
    if wars:
        war_txt = f"  AT WAR ({len(wars)}) "
        text = text[:w - 1 - len(war_txt) - 6]
        safe_addstr(scr, 0, 0, text, pal.ui(1) | curses.A_BOLD)
        safe_addstr(scr, 0, len(text), war_txt, pal.ui(7) | curses.A_BOLD)
    else:
        safe_addstr(scr, 0, 0, text[:w - 1], pal.ui(1) | curses.A_BOLD)
    max_ae = max((o.ae.get(g.player, 0) for o in g.nations.values()
                  if o.alive and o.tag != g.player), default=0)
    if max_ae > data.COALITION_AE_THRESHOLD * 0.7:
        warn = " AE! "
        safe_addstr(scr, 0, w - len(warn) - 1, warn,
                    pal.ui(7) | curses.A_BOLD)


def _balance(g: Game):
    from . import engine
    return engine.monthly_balance(g, g.player)


# ----------------------------------------------------------------- sidebar

def draw_sidebar(win, g: Game, pal: Palette, ui):
    from . import engine
    win.erase()
    win.box()
    h, w = win.getmaxyx()
    iw = w - 2
    row = [1]

    def put(text="", attr=0, indent=1):
        if row[0] >= h - 1:
            return
        safe_addstr(win, row[0], indent, text[:iw], attr)
        row[0] += 1

    me = g.nations[g.player]
    # --- wars
    wars = g.wars_of(g.player)
    if wars:
        for war in wars[:3]:
            sc = war.score_for(g.player)
            col = pal.ui(5) if sc >= 0 else pal.ui(2)
            put(f"{war.name}"[:iw], pal.ui(2) | curses.A_BOLD)
            barw = max(10, iw - 14)
            filled = int((sc + 100) / 200 * barw)
            bar = "#" * filled + "-" * (barw - filled)
            put(f" {bar} {sc:+.0f}%", col)
            vs = ", ".join(g.nations[t].name
                           for t in war.enemies_of(g.player))
            put(f" vs {vs}", curses.A_DIM)
            if sc <= data.LOSING_BADLY:
                put(" The realm tires of this war!", pal.ui(7))
            if abs(war.score) >= data.CAPITULATION_SCORE:
                left = max(1, data.CAPITULATION_MONTHS - war.dom_months)
                label = ("Enemy capitulates" if sc > 0
                         else "CAPITULATION")
                put(f" {label} in {left} month(s)!",
                    pal.ui(7) | curses.A_BOLD)
        put()
    if me.allies:
        put("Allies: " + ", ".join(sorted(
            g.nations[t].name for t in me.allies)), pal.ui(4))
    if me.fabricating:
        pid, left = me.fabricating
        put(f"Fabricating claim: {g.provinces[pid].name} ({left}m)",
            pal.ui(6))
    if me.war_exhaustion >= 3:
        put(f"War exhaustion: {me.war_exhaustion:.1f}", pal.ui(3))
    coalition = [o.name for o in g.nations.values()
                 if o.alive and o.in_coalition_against == g.player]
    if coalition:
        put("COALITION: " + ", ".join(coalition), pal.ui(7))
    if g.missions:
        put("Missions:", curses.A_BOLD)
        for m in g.missions:
            put(f" - {m['desc']}", pal.ui(6))
    put("-" * iw, curses.A_DIM)

    # --- selected army
    if ui.sel_aid is not None and ui.sel_aid in g.armies:
        a = g.armies[ui.sel_aid]
        put(f"{a.name}", pal.nation_fg(g.nations[a.owner].color))
        put(f" {a.regiments} regiments, {a.men:,} men")
        put(f" Morale {a.morale:.1f}/{engine.morale_max(g, a.owner):.1f}"
            f"  at {g.provinces[a.location].name}")
        if a.general:
            put(f" {a.general_name} (skill {a.general})", pal.ui(5))
        if a.move_target is not None:
            put(f" Moving to {g.provinces[a.move_target].name}", pal.ui(3))
        put(f" Reinforce: {'on' if a.reinforce else 'OFF'}   Supply here: "
            f"{engine.supply_limit(g, a.owner, a.location)}")
        att = engine.attrition_fraction(g, a)
        if att > 0:
            put(f" Taking attrition! (-{att * 100:.1f}%/month)",
                pal.ui(2) | curses.A_BOLD)
        put(" [m]ove [x]split [X]disband", curses.A_DIM)
        put(" [G]eneral [i]reinforce on/off", curses.A_DIM)
        put("-" * iw, curses.A_DIM)

    # --- selected province
    if ui.sel_pid is not None and ui.sel_pid in g.provinces:
        p = g.provinces[ui.sel_pid]
        own = g.nations[p.owner]
        put(f"{p.name}  ({data.TERRAIN[p.terrain][0]})", curses.A_BOLD)
        put(f" {own.name}", pal.nation_fg(own.color))
        if p.pid == own.capital:
            put("  * Capital *", pal.ui(3))
        put(f" Dev {p.dev}   Fort {p.fort_level}   "
            f"Tax {p.tax_income():.2f}/m")
        put(f" Supply limit: {engine.supply_limit(g, g.player, p.pid)}")
        if p.buildings:
            put(" Buildings: " + ", ".join(
                data.BUILDINGS[b][0] for b in p.buildings))
        else:
            put(" Buildings: none", curses.A_DIM)
        if p.occupier:
            put(f" OCCUPIED by {g.nations[p.occupier].name}", pal.ui(7))
        if p.sieging:
            put(f" Siege by {g.nations[p.sieging].name}: "
                f"{p.siege_progress:.0f}%", pal.ui(2))
        if p.pid in me.claims:
            put(" You have a claim here", pal.ui(5))
        here = [a for a in g.armies.values() if a.location == p.pid]
        for a in here[:4]:
            put(f"  *{a.regiments} {g.nations[a.owner].name} "
                f"({a.men:,})", pal.nation_fg(g.nations[a.owner].color))
        if p.owner == g.player:
            put(f" [d]ev +1 ({p.dev_cost()}g) [b]uild [r]ecruit",
                curses.A_DIM)
        else:
            put(" [c]laim [D]iplomacy", curses.A_DIM)
        put("-" * iw, curses.A_DIM)

    # --- owner relations snapshot
    if ui.sel_pid is not None and ui.sel_pid in g.provinces:
        p = g.provinces[ui.sel_pid]
        if p.owner != g.player:
            o = g.nations[p.owner]
            put(f"{o.name}: {o.ruler}", curses.A_BOLD)
            put(f" Opinion of you: {o.opinion_of(g.player):+.0f}   "
                f"AE: {o.ae.get(g.player, 0):.0f}")
            put(f" Dev {g.total_dev(o.tag)}  "
                f"Troops ~{sum(a.regiments for a in g.armies_of(o.tag))}r")
            rel = []
            if o.tag in me.allies:
                rel.append("ALLY")
            if g.at_war_with(g.player, o.tag):
                rel.append("AT WAR")
            if g.truce_between(g.player, o.tag):
                until = me.truces.get(o.tag, 0)
                rel.append(f"truce {(until - g.abs_month) // 12 + 1}y")
            if o.in_coalition_against == g.player:
                rel.append("IN COALITION VS YOU")
            if rel:
                put(" " + "  ".join(rel), pal.ui(3))
        put("-" * iw, curses.A_DIM)

    # --- great powers, pinned to the bottom of the panel
    from . import engine as _e
    rows_gp = sorted((t for t, n in g.nations.items() if n.alive),
                     key=lambda t: -_e.score(g, t))
    block = min(6, len(rows_gp)) + 1
    start = h - 1 - block
    if start > row[0]:
        row[0] = start
        put("Great Powers:", curses.A_BOLD)
        for i, t in enumerate(rows_gp[:6]):
            n = g.nations[t]
            attr = pal.nation_fg(n.color)
            if t == g.player:
                attr |= curses.A_REVERSE
            put(f" {i + 1}. {n.name:12} {_e.score(g, t):5.0f}", attr)


# ---------------------------------------------------------------- log bars

def draw_log(scr, g: Game, pal: Palette, top: int, lines: int):
    h, w = scr.getmaxyx()
    recent = g.log[-lines:]
    for i in range(lines):
        y = top + i
        safe_addstr(scr, y, 0, " " * (w - 1))
        if i < len(recent):
            cat, msg = recent[i]
            safe_addstr(scr, y, 0, f" {msg}", pal.log_attr(cat))


def draw_keybar(scr, pal: Palette, ui, status: str = ""):
    h, w = scr.getmaxyx()
    keys = ("[Spc]turn [>]year [Tab]army [m]ove [r]ecruit [b]uild [d]ev "
            "[c]laim [D]iplo [+]stab [o]ledger [g]log [1-5]map [?]help "
            "[S]ave [q]uit")
    safe_addstr(scr, h - 1, 0, " " * (w - 1), pal.ui(1))
    text = status if status else keys
    safe_addstr(scr, h - 1, 0, " " + text[:w - 2], pal.ui(1))


# ------------------------------------------------------------------ popups

def popup_menu(scr, pal: Palette, title: str, options: list[str],
               info: list[str] | None = None, start: int = 0) -> int | None:
    """Modal selection. Returns index or None on Esc."""
    h, w = scr.getmaxyx()
    info = info or []
    width = min(w - 4, max(len(title) + 4,
                           max((len(o) for o in options + info), default=10)
                           + 6))
    visible = min(len(options), h - 8 - len(info))
    height = visible + 4 + len(info)
    win = curses.newwin(height, width, max(1, (h - height) // 2),
                        (w - width) // 2)
    win.keypad(True)
    sel = start
    off = 0
    while True:
        win.erase()
        win.box()
        safe_addstr(win, 0, 2, f"[ {title} ]", curses.A_BOLD)
        for i, line in enumerate(info):
            safe_addstr(win, 1 + i, 2, line, curses.A_DIM)
        if sel < off:
            off = sel
        if sel >= off + visible:
            off = sel - visible + 1
        for i in range(visible):
            idx = off + i
            if idx >= len(options):
                break
            attr = curses.A_REVERSE if idx == sel else 0
            safe_addstr(win, 2 + len(info) + i, 2,
                        options[idx][:width - 4].ljust(width - 4), attr)
        safe_addstr(win, height - 1, 2, "[Enter] select  [Esc] cancel",
                    curses.A_DIM)
        win.refresh()
        k = read_key(win)
        if k in (27, ord("q")):
            return None
        if k in (curses.KEY_UP, ord("k")):
            sel = (sel - 1) % len(options)
        elif k in (curses.KEY_DOWN, ord("j")):
            sel = (sel + 1) % len(options)
        elif k in (10, 13, curses.KEY_ENTER):
            return sel


def popup_text(scr, pal: Palette, title: str, body: str,
               options: list[str] | None = None) -> int:
    """Text popup with wrapped body and option list (defaults to [OK])."""
    options = options or ["OK"]
    h, w = scr.getmaxyx()
    width = min(w - 6, 64)
    lines = []
    for para in body.split("\n"):
        lines.extend(textwrap.wrap(para, width - 4) or [""])
    height = min(h - 2, len(lines) + len(options) + 4)
    win = curses.newwin(height, width, max(1, (h - height) // 2),
                        (w - width) // 2)
    win.keypad(True)
    sel = 0
    while True:
        win.erase()
        win.box()
        safe_addstr(win, 0, 2, f"[ {title} ]", curses.A_BOLD)
        for i, line in enumerate(lines[:height - len(options) - 4]):
            safe_addstr(win, 1 + i, 2, line)
        base = height - len(options) - 2
        for i, opt in enumerate(options):
            attr = curses.A_REVERSE if i == sel else 0
            safe_addstr(win, base + i, 3, f"> {opt}"[:width - 4], attr)
        win.refresh()
        k = read_key(win)
        if k in (curses.KEY_UP, ord("k")):
            sel = (sel - 1) % len(options)
        elif k in (curses.KEY_DOWN, ord("j")):
            sel = (sel + 1) % len(options)
        elif k in (10, 13, curses.KEY_ENTER):
            return sel
        elif k == 27 and len(options) == 1:
            return 0


def popup_toggle_list(scr, pal: Palette, title: str,
                      items: list[tuple[str, float]], budget: float,
                      budget_name: str = "warscore",
                      extra_label: str | None = None,
                      extra_step: float = 0.0,
                      extra_cost_per: float = 0.0):
    """Toggle items on/off within a budget. Returns (set indices, extra) or None.

    items: (label, cost). extra_*: optional adjustable demand (e.g. gold).
    """
    h, w = scr.getmaxyx()
    width = min(w - 4, 66)
    visible = min(len(items) + (1 if extra_label else 0), h - 10)
    height = visible + 7
    win = curses.newwin(height, width, max(1, (h - height) // 2),
                        (w - width) // 2)
    win.keypad(True)
    chosen: set[int] = set()
    extra = 0.0
    sel = 0
    nrows = len(items) + (1 if extra_label else 0)
    off = 0
    while True:
        cost = sum(items[i][1] for i in chosen) + extra * extra_cost_per
        win.erase()
        win.box()
        safe_addstr(win, 0, 2, f"[ {title} ]", curses.A_BOLD)
        col = pal.ui(5) if cost <= budget else pal.ui(2)
        safe_addstr(win, 1, 2,
                    f"Demanded: {cost:.0f}%  /  your {budget_name}: "
                    f"{budget:.0f}%", col | curses.A_BOLD)
        if sel < off:
            off = sel
        if sel >= off + visible:
            off = sel - visible + 1
        for i in range(visible):
            idx = off + i
            if idx >= nrows:
                break
            if extra_label and idx == len(items):
                label = f"   {extra_label}: {extra:.0f}  (left/right)"
                mark = " "
            else:
                label = items[idx][0]
                mark = "x" if idx in chosen else " "
                label = f"[{mark}] {label}  ({items[idx][1]:.0f}%)"
            attr = curses.A_REVERSE if idx == sel else 0
            safe_addstr(win, 3 + i, 2, label[:width - 4].ljust(width - 4),
                        attr)
        safe_addstr(win, height - 2, 2,
                    "[Space] toggle  [Enter] offer  [Esc] cancel",
                    curses.A_DIM)
        win.refresh()
        k = read_key(win)
        if k == 27:
            return None
        if k in (curses.KEY_UP, ord("k")):
            sel = (sel - 1) % nrows
        elif k in (curses.KEY_DOWN, ord("j")):
            sel = (sel + 1) % nrows
        elif k == ord(" ") and sel < len(items):
            chosen.symmetric_difference_update({sel})
        elif extra_label and sel == len(items) and \
                k in (curses.KEY_LEFT, ord("h")):
            extra = max(0.0, extra - extra_step)
        elif extra_label and sel == len(items) and \
                k in (curses.KEY_RIGHT, ord("l")):
            extra += extra_step
        elif k in (10, 13, curses.KEY_ENTER):
            return chosen, extra


def show_ledger(scr, g: Game, pal: Palette):
    from . import engine
    h, w = scr.getmaxyx()
    rows = sorted((t for t, n in g.nations.items() if n.alive),
                  key=lambda t: -engine.score(g, t))
    win = curses.newwin(h - 2, min(w - 2, 78), 1,
                        max(0, (w - 78) // 2))
    win.keypad(True)
    win.erase()
    win.box()
    safe_addstr(win, 0, 2, "[ Ledger of Nations ]", curses.A_BOLD)
    hdr = (f"{'':1}{'Tag':4}{'Nation':12}{'Provs':>6}{'Dev':>5}{'Gold':>7}"
           f"{'Troops':>7}{'MP':>7}{'Stab':>5}{'Score':>7}  Rel")
    safe_addstr(win, 1, 2, hdr, curses.A_UNDERLINE)
    for i, t in enumerate(rows):
        n = g.nations[t]
        rel = ""
        if t == g.player:
            rel = "YOU"
        elif t in g.nations[g.player].allies:
            rel = "ally"
        elif g.at_war_with(g.player, t):
            rel = "WAR"
        elif g.truce_between(g.player, t):
            rel = "truce"
        line = (f"{n.tag:4}{n.name:12}"
                f"{len(g.provinces_of(t)):>6}{g.total_dev(t):>5}"
                f"{n.gold:>7.0f}"
                f"{sum(a.regiments for a in g.armies_of(t)):>7}"
                f"{n.manpower:>7.0f}{n.stability:>+5d}"
                f"{engine.score(g, t):>7.0f}  {rel}")
        attr = pal.nation_fg(n.color)
        if t == g.player:
            attr |= curses.A_REVERSE
        safe_addstr(win, 2 + i, 2, " ", attr | curses.A_REVERSE)
        safe_addstr(win, 2 + i, 3, line, attr)
    safe_addstr(win, win.getmaxyx()[0] - 1, 2, "[any key to close]",
                curses.A_DIM)
    win.refresh()
    read_key(win)


def show_log(scr, g: Game, pal: Palette):
    h, w = scr.getmaxyx()
    win = curses.newwin(h - 2, w - 4, 1, 2)
    win.keypad(True)
    lines = g.log[:]
    off = max(0, len(lines) - (h - 6))
    while True:
        win.erase()
        win.box()
        safe_addstr(win, 0, 2, "[ Chronicle ]", curses.A_BOLD)
        view = lines[off:off + h - 6]
        for i, (cat, msg) in enumerate(view):
            safe_addstr(win, 1 + i, 2, msg[:w - 8], pal.log_attr(cat))
        safe_addstr(win, h - 3, 2, "[up/down scroll, any other key closes]",
                    curses.A_DIM)
        win.refresh()
        k = read_key(win)
        if k in (curses.KEY_UP, ord("k")):
            off = max(0, off - 1)
        elif k in (curses.KEY_DOWN, ord("j")):
            off = min(max(0, len(lines) - (h - 6)), off + 1)
        elif k == curses.KEY_PPAGE:
            off = max(0, off - (h - 6))
        elif k == curses.KEY_NPAGE:
            off = min(max(0, len(lines) - (h - 6)), off + (h - 6))
        else:
            return


HELP_TEXT = """\
GOAL  Lead your nation to glory before AE 900. Grow development,
forge alliances, win wars, take provinces. Score = dev*2 + prestige
+ gold/20. Don't get annexed.

MAP   Arrows/hjkl move cursor - Enter selects province
      1 political  2 terrain  3 development  4 diplomatic
      5 military: terrain tinted by relation (green you, cyan
      ally, red at-war, yellow truce, gray neutral); army chips
      colored the same way; marker glyph shows morale (* ready,
      o shaken, x broken); battles show odds like 9v7; sieges
      show progress % in place of the tag; your selected army's
      destination is highlighted.
      Tags show owners; *N markers are armies; ! means siege.

TURNS Space ends the turn (1 month). > plays up to 12 months,
      stopping at anything important.

ECONOMY  [d] develop province (+1 dev)   [b] build building
      [+] raise stability   Buildings: farm/market boost income,
      barracks manpower, fort defense, temple unrest & prestige.

MILITARY  [Tab] cycle armies  [m] move (pick target, Enter)
      [r] recruit one regiment  [R] recruit up to force limit
      [x] split army  [X] disband army  [G] hire a general
      [i] toggle reinforcement for the selected army
      Generals add their skill to every battle die roll.
      Armies siege enemy provinces automatically when parked there.
      Battles favor numbers, morale and defensive terrain.
      SUPPLY: a province feeds 3 + dev*0.6 regiments (less in
      mountains/desert/marsh, +2 on own or allied soil). All your
      regiments in one province count together; stacks above the
      limit lose men every month - spread out or starve.

DIPLOMACY  [c] fabricate claim on a border province (6 months)
      [D] diplomacy menu: improve relations, alliances, declare
      war, negotiate peace. Claims make wars cheaper and peace
      deals stronger. Watch Aggressive Expansion - high AE
      triggers hostile coalitions.

WAR   Warscore comes from occupations and battles won. Negotiate
      peace from the diplomacy menu: demand provinces/gold or
      offer concessions when losing. War exhaustion erodes morale.
      Losing badly doubles exhaustion and risks stability; refusing
      a fair peace offer costs stability outright. If one side
      holds total warscore for a year, the loser must capitulate.

OTHER [o] ledger  [g] chronicle  [S] save  [L] load  [q] quit
"""


def show_help(scr, pal: Palette):
    popup_text(scr, pal, "How to Play", HELP_TEXT)
