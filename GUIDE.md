# EUV — New Player Guide

So you've taken a throne in Eryndor. This guide walks you from your first
keypress to your first won war, and explains the systems that will
otherwise kill you. No grand strategy experience required.

Run the game with `python3 -m euv` in a terminal of at least 100x30
(256-color recommended). Your goal: be standing — ideally dominant — when
the age ends in AE 900, a century after the start. Score is
`development x2 + prestige + treasury/20`, but the real win condition is
the story you carve out.

## Choosing a nation

The selection list shows provinces, total development and a difficulty
rating. For a first game pick a 5-6 province nation (1-2 stars): big
enough to survive mistakes, small enough that your decisions matter.
Cultures hint at neighborhood: valdric north, lyrian west, aurean center,
qessari south, tervani east. Center nations have more neighbors — more
opportunity, more threat.

## Reading the screen

- **Top bar** — your vitals: treasury (and monthly net), manpower,
  stability, prestige, army size vs force limit, and a red AT WAR flag.
  An `AE!` warning means neighbors are getting scared of you (see
  Coalitions below).
- **Map** — provinces with 3-letter owner tags. `*N` chips are armies
  (N regiments), `!` is an active siege, striped provinces are occupied.
  Switch modes with `1`-`5`: political, terrain, development, diplomatic,
  and **military** — learn to love `5` in wartime: terrain is tinted by
  threat (green yours, cyan allied, red hostile), army chips show morale
  (`*` ready, `o` shaken, `x` broken), battles show odds like `9v7`, and
  sieges show their progress percent.
- **Sidebar** — your wars with score bars, missions, selected
  province/army details, and the great powers ranking.
- **Log** — the world's events scroll at the bottom; press `g` for the
  full chronicle, `o` for the ledger of nations.

Move the cursor with arrows or `hjkl`, select with `Enter`, end the turn
(one month) with `Space`, or play up to a year with `>` — it stops
automatically when something needs you.

## Your first ten years: build the engine

Wars are won in peacetime. Priorities, in order:

1. **Stability up to +2 or +3** (`+`). It boosts taxes, calms unrest, and
   you want a buffer because declaring war without a claim costs 2.
2. **Buildings before development.** Select a province, press `b`.
   Farmsteads (+30% tax) in your highest-dev provinces pay for themselves
   fastest; then markets, then a barracks somewhere safe. Temples are for
   conquered or restless land. Forts go on your border with whoever
   frightens you.
3. **Develop** (`d`) once good building slots are filled. Cost rises with
   each level, so spreading dev wide beats stacking it tall.
4. **One ally, chosen well.** Open diplomacy (`D`), improve relations
   until their opinion is +25 or so, then offer an alliance. You want a
   strong neighbor who shares an enemy with you — not the nation you
   plan to eat.
5. **Missions** (sidebar) nudge you toward all of the above and pay gold
   and prestige. Conquest missions grant a free claim — gold in the bank.

Keep your army at roughly 60-70% of force limit in peacetime; full
mobilization is for wars. Never exceed the force limit for long — upkeep
becomes 2.5x per extra regiment.

## Your first war

Pick a target you can actually beat: check the ledger (`o`) for their
troops and development, and look at who their allies are (select their
provinces and read the sidebar). You with your ally should clearly
outweigh them with theirs.

1. **Fabricate a claim** (`c` on a border province, 20 gold, 6 months).
   A claim is a casus belli: no stability hit for declaring, cheaper
   peace demands, and a **war goal** — holding the claimed province
   slowly ticks warscore in your favor, so claim wars end decisively.
2. **Mobilize first.** Recruit to force limit (`R`), and hire a general
   (`G`, 50 gold) — their skill adds to every battle die.
3. **Declare** through the diplomacy menu (`D`). Your allies may receive
   a call to arms.
4. **Fight smart.** Battles are won by numbers, morale, generals and
   terrain — defenders in mountains (`^`) and hills (`n`) hit harder.
   Bring superior numbers and engage their field army before it can join
   a siege. After a battle, let morale recover before chasing.
5. **Mind supply.** Every province feeds a limited number of regiments
   (sidebar shows the limit; worse in mountains, desert, marsh; better
   on friendly soil). Stacks beyond the limit take monthly attrition —
   split sieging forces (`x`) instead of marching one giant doomstack.
6. **Siege everything.** Armies parked on enemy land besiege
   automatically. Occupations are what fill the warscore bar; battles
   alone cap out at 40%.
7. **Make peace** (`D` → Negotiate peace) before war exhaustion hollows
   you out. Demand provinces up to your warscore (claims are discounted),
   take gold with leftover score, or — against a mid-sized enemy —
   **demand vassalization** and take the whole nation as a subject
   instead of a bite of it. Don't be greedy: a refused offer means more
   months of bleeding.

If you're *losing*: negotiate early. Refusing a fair offer while beaten
costs stability and exhaustion, and if the enemy holds total warscore
for a year you'll be forced to capitulate on their terms.

## The four ways players die

1. **Coalitions.** Every conquest generates aggressive expansion (AE) in
   everyone nearby. Past a threshold, frightened neighbors form a
   coalition that can dwarf you. Watch the `AE!` warning, conquer in
   small bites, let AE decay (~10 years), and keep some neighbors
   friendly. Reconquering land you hold a **core** on causes half AE.
2. **Rebels.** Freshly conquered provinces seethe with separatists —
   the sidebar shows unrest and REVOLT RISK. Keep an army near new
   conquests, raise stability, build temples. Rebel-held provinces stop
   paying and eventually lose development. Conquered land **cores**
   (becomes truly yours, ending the 25% tax penalty) after ten years.
3. **Bankruptcy.** Debt compounds; deep debt shatters stability and
   deserts your armies. Disband (`X`) or shrink armies after wars, and
   toggle reinforcement off (`i`) on a battered stack if your manpower
   pool is draining.
4. **War exhaustion.** It rises every month at war, faster when losing,
   eroding morale and manpower recovery. Long wars are lost wars; take
   what your warscore buys and go home.

## Diplomacy beyond the basics

- **Rivals**: you may declare up to two similar-sized rivals. Opinions
  between rivals sink toward -40 and beating one at the peace table pays
  prestige. Expect the AI to pick rivals too — check the sidebar for
  "RIVAL" before trusting a neighbor.
- **Vassals**: subjects pay a quarter of their income, fight your wars,
  and after ten loyal years can be **integrated** peacefully over two
  more. Don't let one grow past ~70% of your strength, or expect a war
  of independence — and fellow vassals will join it.
- **Cores and reconquest**: your cores on foreign-owned land are
  permanent CBs with cheap peace costs. Losing provinces isn't the end;
  taking them back is half-price diplomacy-wise.
- **Truces** last five years. Breaking one costs stability and prestige.

## Quick reference

| Key | Action |
|---|---|
| `Space` / `>` | End turn / play up to a year |
| Arrows, `hjkl`, `Enter` | Move cursor, select |
| `Tab` `m` `x` `X` | Cycle armies, move, split, disband |
| `r` `R` `G` `i` | Recruit one / to limit, hire general, toggle reinforce |
| `d` `b` `+` | Develop, build, raise stability |
| `c` `D` | Fabricate claim, diplomacy menu |
| `1`-`5` | Map modes (use `5` at war) |
| `o` `g` `?` | Ledger, chronicle, help |
| `S` `L` `q` | Save, load, quit (autosaves every January) |

One last tip: press `?` in game whenever you forget something — and when
in doubt, pick the option that keeps stability up. Good luck, and may
your name be written kindly in the chronicle of AE 900.
