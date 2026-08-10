"""Default shelf-life profiles by product category.

A's `products.csv` does not carry ethylene flags or Q10 constants, and it does
not need to — A supplies `rsl_days` directly from the RSL model. But two
features still need the physics: the deterministic fallback for batches A has
not scored, and the ethylene-adjacency check.

So B keeps a small category table here. It is reference data, not a model.
D can override it from `content/` later without touching this file.

    category -> (base_days, ref_temp_c, q10, cut_factor, sensitive, emitter)
"""

from __future__ import annotations

DEFAULT_PROFILES: dict[str, tuple[float, float, float, float, bool, bool]] = {
    "leafy_green": (7.0, 4.0, 2.5, 0.35, True, False),
    "herb": (5.0, 4.0, 2.6, 0.30, True, False),
    "vegetable": (10.0, 6.0, 2.2, 0.40, False, False),
    "fruiting_vegetable": (8.0, 8.0, 2.3, 0.40, False, True),
    "fruit": (7.0, 8.0, 2.4, 0.45, False, True),
    "root": (30.0, 25.0, 1.5, 0.40, False, False),
    "tuber": (30.0, 25.0, 1.5, 0.40, False, False),
    "dairy": (12.0, 4.0, 2.8, 0.50, False, False),
    "meat": (4.0, 2.0, 2.6, 0.50, False, False),
    "seafood": (3.0, 1.0, 2.8, 0.50, False, False),
    "staple": (180.0, 20.0, 1.2, 0.80, False, False),
    "grain": (180.0, 20.0, 1.2, 0.80, False, False),
    "spice": (365.0, 25.0, 1.1, 0.90, False, False),
    "bakery": (3.0, 20.0, 1.8, 0.60, False, False),
    "prepared_dish": (2.0, 4.0, 2.5, 0.60, False, False),
}

# Products whose name matches one of these is treated as an ethylene emitter or
# a sensitive item regardless of its category, because the category alone is
# too coarse — "vegetable" covers both tomatoes and cabbage.
EMITTER_NAMES = ("tomato", "banana", "apple", "mango", "papaya", "avocado", "melon")
SENSITIVE_NAMES = (
    "spinach", "lettuce", "coriander", "cilantro", "kale", "broccoli",
    "cabbage", "cucumber", "carrot", "methi", "fenugreek",
)

# A's category vocabulary -> ours. A classifies by handling behaviour
# (soft_veg, root_allium, dry), which is a better taxonomy than ours for a
# kitchen; this table is the translation, not a correction.
CATEGORY_ALIASES = {
    "soft_veg": "fruiting_vegetable",
    "hard_veg": "vegetable",
    "root_allium": "root",
    "root_veg": "root",
    "leafy": "leafy_green",
    "greens": "leafy_green",
    "herb": "herb",
    "herbs": "herb",
    "fruit": "fruit",
    "dairy": "dairy",
    "meat": "meat",
    "poultry": "meat",
    "seafood": "seafood",
    "dry": "staple",
    "dry_goods": "staple",
    "grain": "grain",
    "spice": "spice",
    "bakery": "bakery",
    "prepared": "prepared_dish",
    "dish": "prepared_dish",
}

FALLBACK = ("vegetable", *DEFAULT_PROFILES["vegetable"])


def profile_for(category: str, name: str = "") -> tuple[str, float, float, float, float, bool, bool]:
    """Return (category_key, base_days, ref_temp, q10, cut, sensitive, emitter)."""
    key = (category or "").strip().lower().replace(" ", "_")
    key = CATEGORY_ALIASES.get(key, key)
    base = DEFAULT_PROFILES.get(key)
    if base is None:
        # Try a loose match before giving up: "fresh_vegetable" -> "vegetable".
        for candidate, values in DEFAULT_PROFILES.items():
            if candidate in key:
                key, base = candidate, values
                break
    if base is None:
        return FALLBACK

    base_days, ref_temp, q10, cut, sensitive, emitter = base
    lowered = (name or "").strip().lower()
    if any(token in lowered for token in EMITTER_NAMES):
        emitter = True
    if any(token in lowered for token in SENSITIVE_NAMES):
        sensitive = True
    return key, base_days, ref_temp, q10, cut, sensitive, emitter
