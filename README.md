# EUV — grand strategy in your terminal

A turn-based grand strategy game inspired by Europa Universalis and
Victoria, played entirely in the terminal. Guide one of 14 nations on the
fictional continent of **Eryndor** through a century of blood and gold:
develop your provinces, forge alliances, fabricate claims, win wars, and
out-score your rivals before the age ends — without provoking a coalition
that tears you apart.

Zero dependencies. Pure Python standard library (curses).

```
 Zarahn | Frostwane, AE 800 | Gold 134 (+3.8) | MP 3,024 | Stab +1 | Pres 0 | Army 9/15 | AT WAR (1)
┌[ Eryndor — POLITICAL ]─────────────────────────────────────┐┌──────────────────────────────────────┐
│~~~~~~ffff~~~~~~nn^^^^^^^^^NOR^^^^^^~~~~~~~~*6f~~~~~~~~~~~~~││Zarahn–Talvona War                    │
│~~~~...fDRAf~~nnnn^^^NOR^^^*5^^^^^CAS^~~~~nfVALf~~~~~~~~~~~~││ ####################------- +80%    │
│~~~BREff*6fnnnDRAnn^^^^^^^.....^^^^^^^nnnnnn~~~~~~ff~~~~~~~~││ vs Talvona                           │
│~~~..fffffnnnnnnnnnfff^^^......^CAS^^nnVALnnnn~~nfff~~~~~~~~││──────────────────────────────────────│
│~~~~fBREfnDRAnnnnnffffff...NOR..^^^^^^nnnnnnVALnnBELf~~~~~~~││Sahoum  (Plains)                      │
│~~~~~ffffnnnnAURnnffAURffn....ff^^^^^^^nnnnnnnn...ff~~~~~~~~││ Zarahn        * Capital *            │
│~~~~..fnnnnn~~~~~~~^^ffnnnnnfCASf.^^^^^..*5n..BEL....~~~~~~~││ Dev 10   Fort 1   Tax 2.50/m         │
│~~~*7..nDRAn~~~~~~AUR^nnAURnf*5f...^^^....nn.........~~~~~~~││  *9 Zarahn (9,000)                   │
│~~.BRE.nnnn.~~~~^^*7^^nnnnnffff.....^..VOL..fff...BEL.~~~~~~││ [d]ev +1 (137g) [b]uild [r]ecruit    │
│~~~nnnn..ASH......CAE...nnfffff...........fffZARff......~~~~││──────────────────────────────────────│
│~~~~~nnnnn...ASH.nn..CAE.nnnnnn.TAL..TAL..nnfffm.BEL.*8~~~~~││Great Powers:                         │
│~~~~nnASHnn.....nnnn....nnnSERn......*4..nnnnmmmm.....~~~~~~││ 1. Zarahn          79                │
│~~~::nnnnn~~...nCAEnn..nnnn*6nn.........nZARnmZARm..~~~~~~~~││ 2. Belgrava        72                │
│~~::::nn~~~~~~.n*7nnn::nSERnnn...TAL....nnnnnnmmmm~~~~~~~~~~││ 3. Brennach        68                │
└────────────────────────────────────────────────────────────┘└──────────────────────────────────────┘
 Zarahn declares war on Talvona! (ZAR vs TAL)
```

## Running

Requires Python 3.10+ and a terminal of at least **100x30** (256-color
recommended). No installation needed:

```sh
python3 -m euv             # random world
python3 -m euv --seed 7    # a specific world
```

Or install the `euv` command with `pip install .`

## The game

Each turn is one month, from AE 800 to AE 900. When the century ends the
nations are ranked by score (development ×2 + prestige + treasury/20) —
but the real goal is survival and dominance on your own terms.

- **Economy** — provinces pay tax by development. Develop them, build
  farms, markets, barracks, forts and temples, and keep stability up
  (raising it costs more the larger your realm grows). Going bankrupt
  shatters your realm.
- **Military** — recruit regiments against a force limit, maneuver army
  stacks, hire generals, and let armies siege enemy provinces (or retake
  your own). Battles weigh numbers, morale, generals, dice and defensive
  terrain. Manpower is a slow-recovering pool; war exhaustion erodes
  morale the longer you fight. Provinces have a **supply limit**
  (3 + dev×0.6 regiments, less in mountains/desert/marsh, +2 on own or
  allied soil): a nation's regiments stacked beyond it take monthly
  attrition, so doomstacks bleed — spread out. Toggle reinforcement per
  army with `i` to stop a wounded stack draining your manpower. The game
  autosaves every January.
- **Diplomacy** — opinions, alliances, truces, rivalries and calls to
  arms. Declare up to two nearby peers as rivals: opinions between
  rivals sour toward -40, envoys are refused, the AI itches for rival
  wars, and beating a rival at the peace table swings prestige both
  ways. Fabricate claims to get cheap casus belli. Warscore from
  occupations, battles and war-goal control buys provinces and gold at
  the peace table.
- **War goals** — in claim wars, whichever side controls the claimed
  province gains a slow monthly warscore tick (up to +/-20), so wars
  over a goal resolve decisively instead of stalling forever.
- **Aggressive expansion** — every conquest scares the neighbours.
  Push too fast and a hostile coalition will form and strike.
- **Missions** — rotating objectives (conquest, development, alliances…)
  that pay gold and prestige, and grant claims for conquest goals.
- **A living world** — AI nations develop, ally, scheme, declare wars on
  each other, and sue for peace. Nations die; great powers rise.
  Random events with meaningful choices punctuate the century.

## Controls

| Keys | Action |
|---|---|
| Arrows / `hjkl` | Move map cursor |
| `Enter` | Select province / confirm move / cycle armies here |
| `Tab` / `Shift-Tab` | Cycle your armies |
| `Space` | End turn (1 month) — `>` plays up to 12 months |
| `m` | Move selected army (pick destination, `Enter`) |
| `x` / `X` | Split / disband army |
| `G` | Hire a general for the selected army |
| `i` | Toggle reinforcement for the selected army |
| `r` / `R` | Recruit one regiment / up to force limit |
| `d` / `b` | Develop province / build building |
| `c` | Fabricate claim on a border province |
| `D` | Diplomacy (relations, alliances, war, peace) |
| `+` | Raise stability |
| `1 2 3 4 5` | Map modes: political, terrain, development, diplomatic, military |
| `o` / `g` | Ledger of nations / chronicle (full log) |
| `?` | Help |
| `S` / `L` / `q` | Save / load / quit |

Map legend: three-letter tags mark province owners, `*N` markers are army
stacks (N regiments), `!` marks an active siege, striped provinces are
occupied, `~` is the sea. Terrain glyphs: `.` plains, `f` forest,
`n` hills, `^` mountains, `:` desert, `m` marsh.

The **military map mode** (`5`) is built for wartime: terrain is tinted by
your relation to the owner (green yours, cyan allied, red at-war, yellow
truce, gray neutral), army chips use the same threat colors, the marker
glyph encodes morale (`*` ready, `o` shaken, `x` broken), battles display
their odds (`9v7`), sieges show progress percent in place of the owner
tag, and your selected army's destination is highlighted.

## Development

The world is generated deterministically from a seed: a hand-shaped
landmass is partitioned into 52 provinces by flood-fill, grouped into 14
nations across five cultures, then named and flavoured. The engine is
fully headless-testable; the curses UI sits on top.

```sh
bash tests/run_all.sh           # everything below
python3 tests/sim.py 7 100      # 100-year all-AI balance simulation
python3 tests/test_rivals.py    # rivalries, war goals, stability costs
python3 tests/tui_driver.py     # scripted TUI session in a pty (pyte)
python3 tests/tui_war.py        # war & peace-negotiation UI flow
python3 tests/tui_campaign.py   # full campaign: march, siege, peace
python3 tests/tui_fuzz.py       # 350 random keys must not crash
```

Module map: `worldgen.py` (map/nations), `model.py` (state),
`engine.py` (turn tick, combat, diplomacy, peace, missions, events),
`ai.py` (AI economy/war/peace/coalitions), `render.py` (curses drawing,
popups), `app.py` (input & game flow), `save.py` (JSON save/load),
`data.py` (constants, names, events).
