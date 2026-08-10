"""Content integrity.

"Wrong costs make every rupee figure in the demo wrong." This file is the reason that
cannot happen quietly. Every derived number in costs.yaml is recomputed here from the
recipe bill of materials, the yield table and the ingredient prices. A hand-edited margin
fails the build.

Owner: Person D.
"""

from __future__ import annotations

import pytest

from foodos.agents.content import ContentPack

EXPECTED_DISH_COUNT = 14


# --- referential integrity ---------------------------------------------------

def test_expected_number_of_dishes(content: ContentPack):
    assert len(content.dishes) == EXPECTED_DISH_COUNT


def test_every_recipe_ingredient_has_a_cost(content: ContentPack):
    missing = {
        line["ingredient"]
        for dish in content.dishes.values()
        for line in dish["lines"]
        if line["ingredient"] not in content.ingredients
    }
    assert not missing, f"ingredients used in a recipe but absent from costs.yaml: {sorted(missing)}"


def test_every_ingredient_has_a_shelf_life_category(content: ContentPack):
    categories = content.shelf_life["categories"]
    for ingredient in content.ingredients:
        category = content.shelf_life["ingredients"].get(ingredient)
        assert category, f"{ingredient} has no shelf-life category"
        assert category in categories, f"{ingredient} maps to unknown category {category!r}"


def test_recipes_and_economics_cover_the_same_dishes(content: ContentPack):
    assert set(content.dishes) == set(content.dish_economics)


def test_dish_ids_and_names_are_unique(content: ContentPack):
    names = [d["name"] for d in content.dishes.values()]
    assert len(names) == len(set(names))


# --- yields ------------------------------------------------------------------

def test_prep_yields_are_fractions(content: ContentPack):
    for ingredient, entry in content.yields["prep_yield"].items():
        value = entry["yield"]
        assert 0.0 < value <= 1.0, f"{ingredient} prep yield {value} is not a fraction"


def test_cooking_yields_are_positive(content: ContentPack):
    for ingredient, value in content.yields["cooking_yield"].items():
        assert value > 0, f"{ingredient} cooking yield {value} is not positive"


def test_cauliflower_yield_matches_the_standard(content: ContentPack):
    """A spot check against the culinary reference, so a typo cannot slide in unnoticed."""
    assert content.prep_yield("cauliflower") == pytest.approx(0.58)
    assert content.prep_yield("tomato") == pytest.approx(0.91)
    assert content.prep_yield("onion") == pytest.approx(0.87)


# --- prices and costs --------------------------------------------------------

def test_all_ingredients_priced_and_carbon_rated(content: ContentPack):
    for name, entry in content.ingredients.items():
        assert entry["unit_cost_per_kg"] > 0, f"{name} has no price"
        assert entry["co2e_kg_per_kg"] > 0, f"{name} has no carbon figure"
        assert entry["disposal_cost_per_kg"] >= 0, f"{name} has a negative disposal cost"


@pytest.mark.parametrize(
    "field,method,tolerance",
    [
        ("food_cost_per_portion", "food_cost_per_portion", 0.01),
        ("contribution_margin_per_portion", "contribution_margin", 0.01),
        ("co2e_kg_per_portion", "co2e_per_portion", 0.005),
        ("input_kg_per_portion", "input_kg_per_portion", 0.005),
        ("disposal_cost_per_portion", "disposal_cost_per_portion", 0.01),
    ],
)
def test_derived_values_match_the_bill_of_materials(content: ContentPack, field, method, tolerance):
    """Recompute every derived field. This is the test that keeps the demo honest."""
    for dish_id, economics in content.dish_economics.items():
        computed = getattr(content, method)(dish_id)
        stated = economics[field]
        assert stated == pytest.approx(computed, abs=tolerance), (
            f"{dish_id}.{field}: costs.yaml says {stated}, the recipe says {computed:.4f}. "
            f"Re-derive it, do not adjust the file to match."
        )


def test_food_cost_pct_matches(content: ContentPack):
    for dish_id, economics in content.dish_economics.items():
        expected = 100 * content.food_cost_per_portion(dish_id) / economics["price"]
        assert economics["food_cost_pct"] == pytest.approx(expected, abs=0.1)


def test_every_dish_makes_money(content: ContentPack):
    for dish_id in content.dishes:
        margin = content.contribution_margin(dish_id)
        assert margin > 0, f"{dish_id} loses money at menu price"


def test_food_cost_is_in_a_defensible_band(content: ContentPack):
    """A dish under 10% or over 45% food cost is a data-entry error, not a business model."""
    for dish_id, economics in content.dish_economics.items():
        pct = economics["food_cost_pct"]
        assert 10.0 <= pct <= 45.0, f"{dish_id} food cost is {pct}%, which is not credible"


def test_portfolio_food_cost_is_realistic(content: ContentPack):
    prices = sum(e["price"] for e in content.dish_economics.values())
    costs = sum(content.food_cost_per_portion(d) for d in content.dishes)
    portfolio = 100 * costs / prices
    assert 20.0 <= portfolio <= 35.0, f"portfolio food cost is {portfolio:.1f}%"


# --- the lambda story --------------------------------------------------------

def test_lambda_can_actually_move_the_plan(content: ContentPack):
    """Content must support a slider that does something.

    The engine owns the newsvendor, but the newsvendor can only respond to lambda if the
    sustainability cost is non-zero for every dish. If this fails, the Plan screen's slider
    is decoration and the pitch is fiction.
    """
    price = content.costs["lambda_price"]
    labour = content.costs["labour_cost_per_portion"]

    for dish_id, economics in content.dish_economics.items():
        sustainability = (
            price["co2e_price_per_kg"] * economics["co2e_kg_per_portion"]
            + price["waste_externality_per_kg_food"] * economics["input_kg_per_portion"]
        )
        assert sustainability > 0

        cu = economics["contribution_margin_per_portion"]
        co = economics["food_cost_per_portion"] + labour + economics["disposal_cost_per_portion"]
        q_profit = cu / (cu + co)
        q_green = cu / (cu + co + sustainability)

        assert q_green < q_profit, f"{dish_id}: lambda does not reduce the service level"
        assert q_profit - q_green > 0.02, (
            f"{dish_id}: lambda moves the service level by only "
            f"{100 * (q_profit - q_green):.1f}pp, which will not be visible on stage"
        )


def test_mutton_is_the_carbon_outlier(content: ContentPack):
    """The demo leans on this contrast, so assert it rather than hoping."""
    mutton = content.dish_economics["mutton_rogan_josh"]["co2e_kg_per_portion"]
    others = [
        e["co2e_kg_per_portion"]
        for d, e in content.dish_economics.items()
        if d != "mutton_rogan_josh"
    ]
    assert mutton > 3 * max(others)


# --- channels ----------------------------------------------------------------

def test_recovery_factors_are_fractions(content: ContentPack):
    for channel_id, channel in content.channels_by_id.items():
        factor = channel["recovery_factor"]
        assert 0.0 <= factor <= 1.0, f"{channel_id} recovery factor {factor} is not a fraction"


def test_channels_are_internally_complete(content: ContentPack):
    required = {
        "id", "name", "type", "basis", "recovery_factor", "lead_time_hours",
        "min_residual_life_hours", "min_qty_kg", "states", "allowed_categories",
        "available_days", "cutoff_hour", "requires",
    }
    for channel_id, channel in content.channels_by_id.items():
        missing = required - set(channel)
        assert not missing, f"{channel_id} is missing {sorted(missing)}"
        assert channel["basis"] in {"menu_price", "food_cost"}
        assert channel["lead_time_hours"] >= 0


def test_disposal_is_the_baseline_and_ranks_last(content: ContentPack):
    disposal = content.channels_by_id["disposal"]
    assert disposal["recovery_factor"] == 0.0
    assert disposal.get("is_baseline") is True
    others = [c for cid, c in content.channels_by_id.items() if cid != "disposal"]
    assert all(c["recovery_factor"] >= disposal["recovery_factor"] for c in others)


def test_cooked_food_cannot_be_donated(content: ContentPack):
    """A food-safety rule, not a preference. If this ever passes cooked stock, stop the demo."""
    assert "cooked" not in content.channels_by_id["ngo_donation"]["states"]


def test_every_exclusion_reason_has_copy(content: ContentPack):
    reasons = content.exclusion_reasons
    assert reasons, "no exclusion reasons defined — excluded channels would render blank"
    for code, text in reasons.items():
        assert text and text[0].isupper(), f"exclusion reason {code} is not presentable copy"


def test_preserve_actions_actually_preserve(content: ContentPack):
    for action_id, action in content.preserve_actions.items():
        assert action["life_multiplier"] > 1.0, f"{action_id} does not extend shelf life"
        assert action["lead_time_hours"] >= 0


def test_free_preserve_actions_exist(content: ContentPack):
    """Moving stock to a colder zone costs nothing and should always be on the table."""
    free = [a for a in content.preserve_actions.values() if a.get("cost", a.get("cost_per_kg", 1)) == 0]
    assert free, "no zero-cost preserve action — the cheapest intervention is missing"


# --- shelf life --------------------------------------------------------------

def test_shelf_life_profiles_are_physical(content: ContentPack):
    for name, profile in content.shelf_life["categories"].items():
        assert profile["base_shelf_life_days"] > 0, f"{name} has no shelf life"
        assert 1.0 <= profile["q10"] <= 4.0, f"{name} has an implausible Q10"
        assert 0.0 < profile["cut_life_factor"] <= 1.0, f"{name} cut factor is not a penalty"
        assert -30 <= profile["ref_temp_c"] <= 40, f"{name} reference temperature is off-scale"


def test_the_planted_warm_chiller_is_actually_warm(content: ContentPack):
    """Pathology two depends on COLD_2 running above set point. Assert the plant is in place."""
    zone = content.shelf_life["storage_zones"]["COLD_2"]
    assert zone["typical_temp_c"] - zone["set_temp_c"] >= 4.0


def test_paneer_is_the_short_life_expensive_item(content: ContentPack):
    profile = content.shelf_life_profile("paneer")
    assert profile["base_shelf_life_days"] <= 6
    assert content.unit_cost("paneer") >= 300
