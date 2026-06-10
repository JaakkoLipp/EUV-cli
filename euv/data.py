"""Static game data: constants, terrain, buildings, names, events."""

# ---------------------------------------------------------------- constants

START_YEAR = 800          # "AE 800" — fictional calendar (After Empire)
END_YEAR = 900            # scoring ends after a century, play may continue
MONTHS = ["Frostwane", "Thawmoon", "Seedtide", "Rainfall", "Highsun",
          "Goldgrass", "Harvest", "Emberfall", "Mistveil", "Longdark",
          "Icewind", "Yearsend"]

BASE_TAX_PER_DEV = 0.25    # gold per dev per month
DEV_COST_BASE = 50         # gold to add +1 dev (scales with current dev)
RECRUIT_COST = 10          # gold per regiment
RECRUIT_MANPOWER = 1000    # men per regiment
REGIMENT_UPKEEP = 0.55     # gold per regiment per month
MANPOWER_PER_DEV = 120     # max manpower pool contribution per dev
MANPOWER_REGEN_YEARS = 8   # years to refill pool from zero
FORT_UPKEEP = 0.6          # per fort level per month
FORCE_LIMIT_PER_DEV = 0.34 # regiments of force limit per total dev
FORCE_LIMIT_BASE = 3
OVER_LIMIT_MULT = 2.5      # upkeep multiplier for regiments above force limit

STAB_COST = 60             # base gold cost to raise stability
MAX_STAB, MIN_STAB = 3, -3

AE_PER_DEV_TAKEN = 2.0     # aggressive expansion per dev annexed
AE_DECAY_PER_YEAR = 2.5
COALITION_AE_THRESHOLD = 35.0
TRUCE_YEARS = 5

CLAIM_COST = 20            # gold to fabricate a claim (takes months)
CLAIM_MONTHS = 6
IMPROVE_COST = 15          # improve relations action
WAR_STAB_HIT_NO_CB = 2     # stability cost declaring without claim
WAR_STAB_HIT_CB = 0

BATTLE_DICE = 9
GENERAL_COST = 50          # hire a general for an army
MORALE_BASE = 3.0
WAR_EXHAUSTION_MONTHLY = 0.08
PEACE_GOLD_PER_WARSCORE = 2.2

# ------------------------------------------------------------------ terrain

# key: (display name, map glyph, color tag, defender bonus, dev cost mult)
TERRAIN = {
    "plains":    ("Plains",    ".", "plains",    0, 1.0),
    "forest":    ("Forest",    "f", "forest",    1, 1.1),
    "hills":     ("Hills",     "n", "hills",     1, 1.2),
    "mountains": ("Mountains", "^", "mountains", 2, 1.4),
    "desert":    ("Desert",    ":", "desert",    0, 1.25),
    "marsh":     ("Marsh",     "m", "marsh",     1, 1.3),
}

# ---------------------------------------------------------------- buildings

# key: (name, cost, description, effect key, effect value)
BUILDINGS = {
    "farm":     ("Farmstead",  40, "+30% local tax",          "tax_mult", 0.30),
    "market":   ("Market",     50, "+0.5 gold/month",         "flat_gold", 0.5),
    "barracks": ("Barracks",   45, "+50% local manpower",     "mp_mult", 0.50),
    "fort":     ("Fort",       70, "+2 fort level",           "fort", 2),
    "temple":   ("Temple",     55, "-2 unrest, +0.1 prestige/yr", "unrest", -2),
}
MAX_BUILDINGS = 3  # slots per province (fort uses a slot)

# ------------------------------------------------------------------- naming

# Culture groups: (province name parts, ruler names) — fictional flavour
CULTURES = {
    "valdric": {   # north — harsh nordic tones
        "prov": ["Skjold", "Varn", "Fjell", "Drak", "Hrim", "Ulfh", "Stor",
                 "Grim", "Thrand", "Kald", "Bjorn", "Eis", "Norr", "Vinter"],
        "suff": ["heim", "vik", "fjord", "gard", "mark", "stad", "berg"],
        "nation": ["Valdria", "Skjoldur", "Hrimland", "Norrvik", "Drakmark"],
    },
    "aurean": {    # center — latinate, old-empire
        "prov": ["Aur", "Cas", "Vel", "Mont", "Ser", "Tal", "Lup", "Flor",
                 "Mar", "Cor", "Vesp", "Luc", "Ost", "Pal"],
        "suff": ["ium", "ona", "entia", "anum", "aris", "etia", "urnum"],
        "nation": ["Aurelia", "Castevel", "Serenia", "Vespara", "Talvona"],
    },
    "qessari": {   # south — desert tones
        "prov": ["Qas", "Zar", "Ash", "Mir", "Sah", "Kel", "Dun", "Raz",
                 "Tam", "Bahr", "Yez", "Khal", "Sem", "Ozr"],
        "suff": ["ad", "ahn", "ira", "oum", "esh", "ara", "iyya"],
        "nation": ["Qessar", "Zarahn", "Ashira", "Khalesh", "Mirad"],
    },
    "tervani": {   # east — slavic/steppe tones
        "prov": ["Terv", "Volk", "Zhur", "Bel", "Kras", "Mor", "Stav", "Gor",
                 "Vran", "Dol", "Pol", "Rud", "Svet", "Char"],
        "suff": ["ova", "grad", "nik", "ovo", "ets", "yn", "iste"],
        "nation": ["Tervan", "Volkov", "Belgrava", "Krasny", "Zhurova"],
    },
    "lyrian": {    # west — celtic/maritime tones
        "prov": ["Lyr", "Bren", "Cael", "Dun", "Aber", "Glen", "Tre", "Pen",
                 "Kil", "Inver", "Caer", "Bal", "Ros", "Mor"],
        "suff": ["mouth", "wick", "loch", "moor", "ford", "haven", "cliff"],
        "nation": ["Lyria", "Brennach", "Caelwyn", "Dunmore", "Rosveil"],
    },
}

RULER_FIRST = {
    "valdric": ["Sigurd", "Astrid", "Halvar", "Freya", "Torvald", "Ingrid"],
    "aurean": ["Marcus", "Livia", "Cassian", "Aurelia", "Octav", "Severa"],
    "qessari": ["Rashid", "Zahra", "Karim", "Samira", "Idris", "Layla"],
    "tervani": ["Bogdan", "Milena", "Radomir", "Vesna", "Stanislav", "Zora"],
    "lyrian": ["Brennan", "Eira", "Cadoc", "Morwen", "Aldric", "Rhona"],
}
RULER_TITLE = {
    "valdric": "Jarl", "aurean": "Consul", "qessari": "Sultan",
    "tervani": "Knyaz", "lyrian": "High King",
}

# ------------------------------------------------------------------- events

# Each event: id, title, text, weight, choices [(label, effects dict)]
# effects: gold, stability, prestige, manpower_frac, ae, dev_capital, unrest_all
EVENTS = [
    ("harvest", "Bountiful Harvest",
     "Granaries overflow across {nation}. The people rejoice.", 10,
     [("Sell the surplus (+40 gold)", {"gold": 40}),
      ("Distribute to the people (+1 stability)", {"stability": 1})]),
    ("comet", "Comet Sighted",
     "A burning star crosses the night sky. The court whispers of omens.", 8,
     [("It is an omen of doom (-1 stability)", {"stability": -1}),
      ("Commission astronomers (-25 gold, +5 prestige)",
       {"gold": -25, "prestige": 5})]),
    ("plague", "Outbreak of the Grey Fever",
     "Sickness spreads through the towns of {nation}.", 6,
     [("Quarantine the towns (-30 gold)", {"gold": -30}),
      ("Let it burn out (-15% manpower, -5 prestige)",
       {"manpower_frac": -0.15, "prestige": -5})]),
    ("minister", "A Gifted Minister",
     "A brilliant administrator offers their services to the crown.", 8,
     [("Appoint them (+25 gold now, +2 prestige)", {"gold": 25, "prestige": 2}),
      ("The old guard objects — refuse", {})]),
    ("border", "Border Incident",
     "Soldiers clashed at a disputed frontier crossing.", 7,
     [("Demand apologies (+3 prestige, +5 AE)", {"prestige": 3, "ae": 5}),
      ("Smooth it over quietly (-10 gold)", {"gold": -10})]),
    ("golden_age", "Golden Anniversary",
     "Crowds gather to celebrate the dynasty's anniversary.", 6,
     [("Hold games (-20 gold, +6 prestige)", {"gold": -20, "prestige": 6}),
      ("A modest ceremony (+1 stability)", {"stability": 1})]),
    ("deserters", "Deserters in the Hills",
     "Veterans unpaid for months have taken to banditry.", 6,
     [("Hunt them down (-15 gold)", {"gold": -15}),
      ("Pardon them (+10% manpower, -3 prestige)",
       {"manpower_frac": 0.10, "prestige": -3})]),
    ("scholars", "The Grand Academy Petitions",
     "Scholars ask for royal patronage of a new academy.", 6,
     [("Fund it (-35 gold, +1 dev in capital)", {"gold": -35, "dev_capital": 1}),
      ("Coin is needed elsewhere (-2 prestige)", {"prestige": -2})]),
    ("zealots", "Religious Fervour",
     "Wandering preachers stir the countryside against the crown's taxes.", 5,
     [("Suppress the movement (-1 stability, +10 gold)",
       {"stability": -1, "gold": 10}),
      ("Grant tax relief (-30 gold, +1 stability)",
       {"gold": -30, "stability": 1})]),
    ("merchants", "Merchant Delegation",
     "Foreign merchants seek a trade charter in {nation}.", 7,
     [("Grant the charter (+30 gold, +3 AE)", {"gold": 30, "ae": 3}),
      ("Protect local guilds (+2 prestige)", {"prestige": 2})]),
]
