"""Ground truth of the synthetic world.

OWNER: Person A (Data & Models).

This module defines the *reality* the generator simulates: which products exist,
what a dish is actually made of, what yields the kitchen actually achieves and
how fast each category actually spoils.

It is deliberately NOT the same thing as `foodos/content/*.yaml` (Person D),
which holds what the *engine believes* — standard culinary yield tables,
published shelf-life profiles and costs. The gap between the two is where the
planted faults live: the engine believes cauliflower yields 0.58; this kitchen
actually achieves 0.51, and the attribution engine has to find that.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Site
# --------------------------------------------------------------------------

SITE = {
    "site_id": "SITE_KIT_01",
    "name": "Spice Garden, Koramangala",
    "type": "kitchen",
    "timezone": "Asia/Kolkata",
    "currency": "INR",
}

# Last business date with actuals. "Today" in the demo IS this day: the ledger
# is the stock standing at close of business, and the plan being recommended is
# for tomorrow. Tomorrow is deliberately a Friday, which is the day the planted
# biryani over-prep bites hardest and the newsvendor cut is largest.
DEFAULT_END_DATE = "2026-02-12"    # Thursday
DEMO_TODAY = "2026-02-12"          # ledger as-of
PLAN_DATE = "2026-02-13"           # Friday — the day the plan is for

# --------------------------------------------------------------------------
# Storage zones — temperatures are declared once, never sensed (no hardware)
# --------------------------------------------------------------------------

STORAGE_ZONES = [
    # zone_id,      name,             mean_temp_c, temp_source
    ("ZN_COLD",     "Cold room",              4.0, "declared"),
    ("ZN_DRY",      "Dry store",             26.0, "declared"),
    ("ZN_FREEZE",   "Freezer",              -18.0, "declared"),
    ("ZN_PREP",     "Prep area",             28.0, "declared"),
    ("ZN_DOCK",     "Receiving dock",        31.0, "simulated"),
]

# --------------------------------------------------------------------------
# Shelf-life profiles — Q10 spoilage kinetics, per category
#   base_shelf_life_days is the life at ref_temp_c for a grade-1.0 intake.
# --------------------------------------------------------------------------

SHELF_LIFE_PROFILES = {
    # category      base_days  ref_temp_c  Q10   cut_life_factor  ethyl_sens  ethyl_emit
    "leafy":        (4.0,      4.0,        2.8,  0.30,            True,       False),
    "soft_veg":     (7.0,      4.0,        2.5,  0.35,            False,      True),
    "hard_veg":     (10.0,     4.0,        2.2,  0.40,            True,       False),
    "root_allium":  (30.0,     15.0,       1.8,  0.45,            False,      False),
    "herb":         (3.0,      4.0,        3.0,  0.25,            True,       False),
    "fruit":        (6.0,      4.0,        2.5,  0.35,            False,      True),
    "dairy":        (6.0,      4.0,        3.0,  0.40,            False,      False),
    "meat":         (3.0,      2.0,        3.2,  0.50,            False,      False),
    "prepared":     (2.0,      4.0,        3.0,  0.50,            False,      False),
    "dry":          (180.0,    26.0,       1.2,  0.90,            False,      False),
}

ZONE_FOR_CATEGORY = {
    "leafy": "ZN_COLD",
    "soft_veg": "ZN_COLD",
    "hard_veg": "ZN_COLD",
    "root_allium": "ZN_DRY",
    "herb": "ZN_COLD",
    "fruit": "ZN_COLD",
    "dairy": "ZN_COLD",
    "meat": "ZN_FREEZE",
    "prepared": "ZN_COLD",
    "dry": "ZN_DRY",
}

# --------------------------------------------------------------------------
# Ingredients — 40 SKUs, 22 of them fruit & vegetables
#   (product_id, name, category, uom, unit_cost, is_produce, co2e_kg_per_uom)
# --------------------------------------------------------------------------

INGREDIENTS = [
    # --- produce (22) ------------------------------------------------------
    ("ING_TOMATO",    "Tomato",            "soft_veg",    "kg",  32.0, True,  1.4),
    ("ING_ONION",     "Onion",             "root_allium", "kg",  38.0, True,  0.5),
    ("ING_POTATO",    "Potato",            "root_allium", "kg",  28.0, True,  0.5),
    ("ING_CAULI",     "Cauliflower",       "hard_veg",    "kg",  40.0, True,  0.7),
    ("ING_SPINACH",   "Spinach",           "leafy",       "kg",  30.0, True,  0.6),
    ("ING_CORIANDER", "Coriander leaves",  "herb",        "kg",  60.0, True,  0.6),
    ("ING_GCHILLI",   "Green chilli",      "soft_veg",    "kg",  70.0, True,  1.0),
    ("ING_GINGER",    "Ginger",            "root_allium", "kg", 120.0, True,  0.8),
    ("ING_GARLIC",    "Garlic",            "root_allium", "kg", 180.0, True,  0.8),
    ("ING_CARROT",    "Carrot",            "hard_veg",    "kg",  45.0, True,  0.4),
    ("ING_CAPSICUM",  "Capsicum",          "soft_veg",    "kg",  80.0, True,  1.8),
    ("ING_CABBAGE",   "Cabbage",           "hard_veg",    "kg",  25.0, True,  0.4),
    ("ING_BRINJAL",   "Brinjal",           "soft_veg",    "kg",  40.0, True,  0.9),
    ("ING_OKRA",      "Okra",              "soft_veg",    "kg",  55.0, True,  0.9),
    ("ING_PEAS",      "Green peas",        "soft_veg",    "kg",  90.0, True,  1.0),
    ("ING_MINT",      "Mint leaves",       "herb",        "kg",  60.0, True,  0.6),
    ("ING_CURRYLEAF", "Curry leaves",      "herb",        "kg",  80.0, True,  0.6),
    ("ING_LEMON",     "Lemon",             "fruit",       "kg",  90.0, True,  0.9),
    ("ING_BEANS",     "French beans",      "soft_veg",    "kg",  60.0, True,  0.8),
    ("ING_MUSHROOM",  "Mushroom",          "soft_veg",    "kg", 220.0, True,  2.9),
    ("ING_CUCUMBER",  "Cucumber",          "soft_veg",    "kg",  35.0, True,  0.6),
    ("ING_BANANA",    "Banana",            "fruit",       "kg",  55.0, True,  0.8),
    # --- non-produce (18) --------------------------------------------------
    ("ING_CHICKEN",   "Chicken",           "meat",        "kg", 210.0, False, 6.9),
    ("ING_MUTTON",    "Mutton",            "meat",        "kg", 720.0, False, 39.2),
    ("ING_FISH",      "Seer fish",         "meat",        "kg", 480.0, False, 5.4),
    ("ING_EGG",       "Egg",               "dairy",       "kg", 140.0, False, 4.7),
    ("ING_PANEER",    "Paneer",            "dairy",       "kg", 380.0, False, 8.6),
    ("ING_CURD",      "Curd",              "dairy",       "kg",  70.0, False, 2.2),
    ("ING_MILK",      "Milk",              "dairy",       "kg",  58.0, False, 1.4),
    ("ING_CREAM",     "Cream",             "dairy",       "kg", 220.0, False, 5.3),
    ("ING_BUTTER",    "Butter",            "dairy",       "kg", 520.0, False, 12.1),
    ("ING_GHEE",      "Ghee",              "dry",         "kg", 640.0, False, 14.8),
    ("ING_RICE",      "Basmati rice",      "dry",         "kg", 120.0, False, 2.7),
    ("ING_ATTA",      "Wheat flour",       "dry",         "kg",  48.0, False, 1.4),
    ("ING_BESAN",     "Gram flour",        "dry",         "kg",  90.0, False, 1.6),
    ("ING_OIL",       "Refined oil",       "dry",         "kg", 145.0, False, 3.3),
    ("ING_CASHEW",    "Cashew",            "dry",         "kg", 850.0, False, 4.1),
    ("ING_COCONUT",   "Coconut",           "dry",         "kg",  45.0, False, 1.1),
    ("ING_TOORDAL",   "Toor dal",          "dry",         "kg", 165.0, False, 1.8),
    ("ING_BATTER",    "Dosa batter",       "prepared",    "kg",  70.0, False, 1.5),
]

# --------------------------------------------------------------------------
# Dishes — 14
#   (product_id, name, menu_price, portion_kg, base_daily_demand)
# --------------------------------------------------------------------------

DISHES = [
    ("DSH_CHBIRYANI", "Chicken Biryani",       275.0, 0.45,  40),
    ("DSH_VGBIRYANI", "Veg Biryani",           210.0, 0.42,  28),
    ("DSH_PBM",       "Paneer Butter Masala",  235.0, 0.30,  45),
    ("DSH_GOBIMANCH", "Gobi Manchurian",       180.0, 0.28,  34),
    ("DSH_PALAK",     "Palak Paneer",          220.0, 0.30,  26),
    ("DSH_NAAN",      "Butter Naan",            48.0, 0.09, 130),
    ("DSH_ROTI",      "Tandoori Roti",          28.0, 0.07,  95),
    ("DSH_JEERARICE", "Jeera Rice",            130.0, 0.28,  40),
    ("DSH_DALTADKA",  "Dal Tadka",             145.0, 0.30,  48),
    ("DSH_ROGANJOSH", "Mutton Rogan Josh",     385.0, 0.32,  18),
    ("DSH_VEGPULAO",  "Veg Pulao",             170.0, 0.35,  22),
    ("DSH_DOSA",      "Masala Dosa",           105.0, 0.25,  55),
    ("DSH_MIXVEG",    "Mixed Veg Curry",       185.0, 0.30,  30),
    ("DSH_FISHCURRY", "Fish Curry",            290.0, 0.30,  20),
]

# Portions here are larger than a textbook spec sheet, which is normal for
# Indian casual dining and is what puts food cost at a realistic ~27% of
# revenue. Applied at read time rather than by editing 100 BOM lines.
PORTION_SCALE = 1.30

# --------------------------------------------------------------------------
# Recipe BOM — net kg of ingredient per portion of dish.
#   `true_yield` is what THIS kitchen actually achieves at prep.
#   Person D's yield table holds the STANDARD the engine benchmarks against.
#   Where they differ, attribution must surface avoidable trim.
# --------------------------------------------------------------------------

#
# Meat and fish are bought already cut, so their butchery loss never reaches
# this kitchen's bin and is not in the waste log. Trim here is produce trim.
#
TRUE_YIELD = {
    "ING_CAULI": 0.51,        # PLANTED FAULT 2 — standard is 0.58
    "ING_ONION": 0.90,
    "ING_TOMATO": 0.97,
    "ING_POTATO": 0.85,
    "ING_CARROT": 0.88,
    "ING_BEANS": 0.90,
    "ING_CAPSICUM": 0.83,
    "ING_SPINACH": 0.78,
    "ING_GINGER": 0.90,
    "ING_GARLIC": 0.87,
    "ING_GCHILLI": 0.94,
    "ING_MINT": 0.86,
    "ING_CORIANDER": 0.86,
    "ING_CURRYLEAF": 0.90,
    "ING_LEMON": 0.55,
    "ING_CABBAGE": 0.88,
    "ING_BRINJAL": 0.88,
    "ING_OKRA": 0.90,
    "ING_MUSHROOM": 0.95,
    "ING_CUCUMBER": 0.85,
    "ING_BANANA": 0.68,
}

# The standard the engine benchmarks against. Only where a kitchen can
# plausibly do better than it does. Person D mirrors this in content/.
STANDARD_YIELD = dict(TRUE_YIELD)
STANDARD_YIELD["ING_CAULI"] = 0.58        # the benchmark the kitchen misses
STANDARD_YIELD["ING_ONION"] = 0.92
STANDARD_YIELD["ING_SPINACH"] = 0.80
STANDARD_YIELD["ING_POTATO"] = 0.87

# Not every gram of peel reaches a scale. What the kitchen actually weighs and
# logs as prep waste; the rest leaves with general kitchen waste.
TRIM_CAPTURE_RATE = 0.34

RECIPES = {
    "DSH_CHBIRYANI": [
        ("ING_CHICKEN", 0.180), ("ING_RICE", 0.120), ("ING_ONION", 0.060),
        ("ING_TOMATO", 0.040), ("ING_CURD", 0.030), ("ING_GINGER", 0.004),
        ("ING_GARLIC", 0.004), ("ING_GCHILLI", 0.005), ("ING_MINT", 0.004),
        ("ING_CORIANDER", 0.005), ("ING_GHEE", 0.012), ("ING_CASHEW", 0.006),
    ],
    "DSH_VGBIRYANI": [
        ("ING_RICE", 0.120), ("ING_CARROT", 0.030), ("ING_BEANS", 0.025),
        ("ING_PEAS", 0.020), ("ING_CAULI", 0.030), ("ING_POTATO", 0.040),
        ("ING_ONION", 0.050), ("ING_TOMATO", 0.035), ("ING_CURD", 0.025),
        ("ING_MINT", 0.004), ("ING_CORIANDER", 0.005), ("ING_GHEE", 0.010),
    ],
    "DSH_PBM": [
        ("ING_PANEER", 0.110), ("ING_TOMATO", 0.100), ("ING_ONION", 0.040),
        ("ING_BUTTER", 0.015), ("ING_CREAM", 0.020), ("ING_CASHEW", 0.008),
        ("ING_GINGER", 0.003), ("ING_GARLIC", 0.003),
    ],
    "DSH_GOBIMANCH": [
        ("ING_CAULI", 0.160), ("ING_CAPSICUM", 0.020), ("ING_ONION", 0.025),
        ("ING_GARLIC", 0.004), ("ING_GCHILLI", 0.004), ("ING_BESAN", 0.020),
        ("ING_OIL", 0.025), ("ING_CORIANDER", 0.003),
    ],
    "DSH_PALAK": [
        ("ING_SPINACH", 0.140), ("ING_PANEER", 0.070), ("ING_ONION", 0.030),
        ("ING_TOMATO", 0.030), ("ING_GARLIC", 0.003), ("ING_GINGER", 0.003),
        ("ING_CREAM", 0.010), ("ING_BUTTER", 0.008),
    ],
    "DSH_NAAN": [
        ("ING_ATTA", 0.070), ("ING_BUTTER", 0.006), ("ING_MILK", 0.010),
        ("ING_CURD", 0.008),
    ],
    "DSH_ROTI": [
        ("ING_ATTA", 0.060),
    ],
    "DSH_JEERARICE": [
        ("ING_RICE", 0.110), ("ING_GHEE", 0.008), ("ING_ONION", 0.010),
    ],
    "DSH_DALTADKA": [
        ("ING_TOORDAL", 0.060), ("ING_TOMATO", 0.020), ("ING_ONION", 0.020),
        ("ING_GARLIC", 0.003), ("ING_GHEE", 0.008), ("ING_CURRYLEAF", 0.002),
        ("ING_GCHILLI", 0.003), ("ING_CORIANDER", 0.003),
    ],
    "DSH_ROGANJOSH": [
        ("ING_MUTTON", 0.200), ("ING_ONION", 0.070), ("ING_TOMATO", 0.040),
        ("ING_CURD", 0.030), ("ING_GINGER", 0.005), ("ING_GARLIC", 0.005),
        ("ING_GHEE", 0.015),
    ],
    "DSH_VEGPULAO": [
        ("ING_RICE", 0.110), ("ING_CARROT", 0.030), ("ING_PEAS", 0.020),
        ("ING_BEANS", 0.020), ("ING_CAPSICUM", 0.020), ("ING_ONION", 0.030),
        ("ING_GHEE", 0.010),
    ],
    "DSH_DOSA": [
        ("ING_BATTER", 0.160), ("ING_POTATO", 0.090), ("ING_ONION", 0.030),
        ("ING_CURRYLEAF", 0.002), ("ING_GCHILLI", 0.003), ("ING_OIL", 0.015),
    ],
    "DSH_MIXVEG": [
        ("ING_CAULI", 0.040), ("ING_CARROT", 0.030), ("ING_BEANS", 0.025),
        ("ING_PEAS", 0.020), ("ING_POTATO", 0.030), ("ING_CAPSICUM", 0.020),
        ("ING_TOMATO", 0.040), ("ING_ONION", 0.030), ("ING_CREAM", 0.008),
    ],
    "DSH_FISHCURRY": [
        ("ING_FISH", 0.160), ("ING_COCONUT", 0.040), ("ING_TOMATO", 0.040),
        ("ING_ONION", 0.040), ("ING_CURRYLEAF", 0.002), ("ING_GCHILLI", 0.004),
        ("ING_LEMON", 0.005),
    ],
}

# Salad, raita and accompaniments: served with every cover, no menu price.
#
# This is modelled as a real dish with a real BOM rather than as untracked
# "direct usage", and that matters. Any kilo the kitchen draws from stock
# without a recipe behind it makes the yield benchmark meaningless — the engine
# sees gross consumption with no net requirement to compare it against, and
# concludes the kitchen wastes 88% of its lemons. A BOM for the sides is what
# makes the trim detector honest.
SIDES = {
    "product_id": "DSH_SIDES",
    "name": "Salad, Raita & Accompaniments",
    "price": 0.0,          # complimentary, but the food cost is real
    "portion_kg": 0.25,
}

# Net kg per cover per day — this dict IS the sides recipe.
DIRECT_USE_PER_COVER = {
    "ING_CUCUMBER": 0.012,
    "ING_CABBAGE": 0.008,
    "ING_CARROT": 0.004,
    "ING_BANANA": 0.010,
    "ING_LEMON": 0.003,
    "ING_EGG": 0.009,
    "ING_BRINJAL": 0.011,
    "ING_OKRA": 0.013,
    "ING_MUSHROOM": 0.004,
    "ING_CURD": 0.015,
    "ING_ONION": 0.006,
}

# --------------------------------------------------------------------------
# Demand shape
# --------------------------------------------------------------------------

# Monday=0 ... Sunday=6
DOW_MULTIPLIER = {
    "default":        [0.82, 0.85, 0.90, 0.98, 1.28, 1.42, 1.30],
    "DSH_CHBIRYANI":  [0.78, 0.82, 0.88, 0.96, 1.46, 1.55, 1.38],
    "DSH_ROGANJOSH":  [0.70, 0.74, 0.82, 0.92, 1.50, 1.62, 1.45],
    "DSH_DOSA":       [1.02, 1.00, 1.00, 1.02, 1.10, 1.24, 1.32],
    "DSH_FISHCURRY":  [0.80, 0.84, 0.88, 0.94, 1.34, 1.48, 1.32],
    "DSH_NAAN":       [0.84, 0.86, 0.92, 1.00, 1.30, 1.44, 1.28],
}

# Indian festival / holiday calendar covering the generated window.
FESTIVAL_CALENDAR = {
    "2025-11-15": ("weekend_special", 1.05),
    "2025-12-24": ("christmas_eve", 1.22),
    "2025-12-25": ("christmas", 1.38),
    "2025-12-31": ("new_year_eve", 1.55),
    "2026-01-01": ("new_year", 1.34),
    "2026-01-14": ("makar_sankranti", 1.26),
    "2026-01-15": ("pongal", 1.18),
    "2026-01-26": ("republic_day", 1.30),
    "2026-02-08": ("weekend_special", 1.08),
}

HOLIDAYS = {"2025-12-25", "2026-01-01", "2026-01-14", "2026-01-26"}

# Dishes that get a promo, and on which weekday (Monday=0)
PROMO_RULES = {
    "DSH_VGBIRYANI": (1, 1.35),      # Tuesday veg promo
    "DSH_DOSA": (2, 1.28),           # Wednesday dosa promo
    "DSH_PBM": (0, 1.22),            # Monday paneer promo
}

# --------------------------------------------------------------------------
# Over-prep behaviour — the kitchen's habit, i.e. the thing FoodOS corrects.
#   The chef preps to roughly the 92nd percentile because running out is loud.
# --------------------------------------------------------------------------

# These put the kitchen at roughly the 85th-90th percentile of its own demand,
# which is the behaviour the whole product is aimed at: running out is loud and
# waste is silent, so the chef buys insurance against the loud one.
BASE_OVERPREP = {
    "default": 1.16,
    "DSH_NAAN": 1.04,
    "DSH_ROTI": 1.04,
    "DSH_ROGANJOSH": 1.20,
    "DSH_PBM": 1.18,
}

# PLANTED FAULT 1 — Friday chicken biryani, produced ~23% above what sells.
FRIDAY_BIRYANI_OVERPREP = 1.34

# Breads and dosa are fired to order. Whatever the chef "plans" for these is a
# batter and dough quantity, not a plated count, so they generate no unsold
# portions. Modelling them as batch-prepped would invent waste that isn't there.
MADE_TO_ORDER = {"DSH_NAAN", "DSH_ROTI", "DSH_DOSA"}

# Not all unsold prepared food is binned. Gravies and rice are carried to the
# next service or go to staff meal; fried and assembled dishes do not keep.
# This is the share of unsold portions that genuinely becomes waste.
UNSOLD_WASTED = {
    "default": 0.24,
    "DSH_CHBIRYANI": 0.31,
    "DSH_VGBIRYANI": 0.31,
    "DSH_GOBIMANCH": 0.45,
    "DSH_DALTADKA": 0.15,
    "DSH_ROGANJOSH": 0.18,
    "DSH_PBM": 0.20,
    "DSH_JEERARICE": 0.22,
    "DSH_PALAK": 0.22,
}

# PLANTED FAULT 3 — a receiving-dock temperature excursion on spinach.
# Placed on the final day so the batch is still open in the Ledger at demo time,
# carrying a true RSL far below the date printed on it.
DOCK_EXCURSION = {
    "product_id": "ING_SPINACH",
    "days_before_end": 0,
    "dwell_hours": 4.0,
    # It sat on the dock precisely because it was an oversized delivery that
    # nobody had room to put away. The size is also what leaves enough of it
    # open in the Ledger for the demo to point at.
    "order_multiplier": 2.6,
}

NORMAL_DOCK_DWELL_HOURS = 0.5

# --------------------------------------------------------------------------
# Ordering behaviour
# --------------------------------------------------------------------------

ORDER_CYCLE_DAYS = {
    "leafy": 1, "herb": 1, "prepared": 1,
    "soft_veg": 2, "hard_veg": 2, "fruit": 2, "dairy": 2, "meat": 2,
    "root_allium": 4, "dry": 7,
}

# The fear buffer on top of expected usage. This is the upstream half of the
# waste problem: an inflated order is an inflated demand signal.
ORDER_BUFFER = {
    "leafy": 0.30, "herb": 0.32, "prepared": 0.20,
    "soft_veg": 0.26, "hard_veg": 0.24, "fruit": 0.26, "dairy": 0.15,
    "meat": 0.12, "root_allium": 0.15, "dry": 0.10,
}

# Suppliers deliver in crates, not in exact kilos. For low-turnover items the
# rounding alone is enough to guarantee spoilage — which is why a kitchen can
# order "correctly" and still bin mint every week.
CRATE_SIZE_KG = {
    "leafy": 1.0, "herb": 0.25, "prepared": 1.0,
    "soft_veg": 1.0, "hard_veg": 1.0, "fruit": 1.0, "dairy": 1.0,
    "meat": 1.0, "root_allium": 2.0, "dry": 5.0,
}

# The storekeeper does not fully trust the walk-in count, so on-hand stock is
# only partly netted off the next order.
ON_HAND_NETTING = 0.82

# Supplier pushes a deal; the kitchen buys ahead. A real and common cause.
OPPORTUNISTIC_BUY_PROB = 0.07
OPPORTUNISTIC_BUY_MULT = 1.6

# The single biggest cause of produce spoilage in a real kitchen: a crate gets
# pushed to the back of the walk-in behind newer stock and is simply not seen
# on picking day. This is precisely what the FEFO pick list exists to fix, so
# the dataset has to contain it or the feature has nothing to prove.
BURIED_BATCH_PROB = 0.44

# The standing order with the vendor. A kitchen that has agreed "two crates of
# spinach a day" keeps taking two crates on the day the walk-in is already full,
# because cancelling is a phone call nobody makes. Intake therefore runs a few
# per cent above consumption indefinitely, and the surplus dies of old age.
#
# This is the single biggest structural cause of produce spoilage in a kitchen,
# and it is precisely what the order-quantity recommendation replaces.
STANDING_ORDER_CATEGORIES = {"leafy", "herb", "fruit", "prepared"}
STANDING_ORDER_FRACTION = 1.03

PLATE_WASTE_RATE = 0.020          # share of served portions partly returned
PLATE_WASTE_FRACTION = 0.34       # how much of that portion comes back
QUALITY_REJECT_PROB = 0.14        # chance a produce receipt is partly rejected

CO2E_PRICE_PER_KG = 2.5           # rupees per kg CO2e

# --------------------------------------------------------------------------
# Newsvendor cost terms
# --------------------------------------------------------------------------
#
# C_o is NOT just the ingredient cost. A portion that goes in the bin also
# consumed labour, gas and a disposal fee, and none of that is recoverable.
LABOUR_COST_PER_PORTION = 15.0
DISPOSAL_COST_PER_KG = 6.0

# C_u is NOT the full menu margin. When a dish runs out most guests order
# something else off the same menu, so only part of the contribution is really
# lost. Ignoring this makes running out look catastrophic and is precisely the
# arithmetic error that has the kitchen prepping to the 92nd percentile.
SUBSTITUTION_RATE = 0.35          # share of would-be lost sales recovered

# lambda: rupees of value placed on one kilo of food not wasted. Zero is the
# profit-optimal plan; raising it slides the whole plan toward less waste at a
# small, visible cost in margin. This is the slider a judge gets to drag.
LAMBDA_DEFAULT = 0.0

# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------

INGREDIENT_BY_ID = {row[0]: row for row in INGREDIENTS}
DISH_BY_ID = {row[0]: row for row in DISHES}


def ingredient_cost(product_id: str) -> float:
    return INGREDIENT_BY_ID[product_id][4]


def ingredient_category(product_id: str) -> str:
    return INGREDIENT_BY_ID[product_id][2]


def ingredient_co2e(product_id: str) -> float:
    return INGREDIENT_BY_ID[product_id][6]


# The sides are a dish like any other, so every kilo drawn from stock has a
# recipe line behind it.
RECIPES[SIDES["product_id"]] = list(DIRECT_USE_PER_COVER.items())


def recipe_lines(dish_id: str) -> list[tuple[str, float]]:
    """BOM for one portion, at served scale. The single place PORTION_SCALE
    is applied, so the generator and the cost model can never disagree."""
    return [(ing_id, net_qty * PORTION_SCALE) for ing_id, net_qty in RECIPES[dish_id]]


def dish_food_cost(dish_id: str) -> float:
    """Recipe cost of one portion, at gross (post-trim) input quantities."""
    total = 0.0
    for ing_id, net_qty in recipe_lines(dish_id):
        gross = net_qty / TRUE_YIELD.get(ing_id, 1.0)
        total += gross * ingredient_cost(ing_id)
    return round(total, 2)


def dish_co2e(dish_id: str) -> float:
    total = 0.0
    for ing_id, net_qty in recipe_lines(dish_id):
        gross = net_qty / TRUE_YIELD.get(ing_id, 1.0)
        total += gross * ingredient_co2e(ing_id)
    return round(total, 3)


def dow_multiplier(dish_id: str, dow: int) -> float:
    return DOW_MULTIPLIER.get(dish_id, DOW_MULTIPLIER["default"])[dow]


def overprep_factor(dish_id: str) -> float:
    return BASE_OVERPREP.get(dish_id, BASE_OVERPREP["default"])
