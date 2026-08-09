"""Load the YAML content pack into the database.

Person D owns the YAML. This module owns getting it into SQLite, and it is the only place
in the engine that reads those files — everything downstream reads the database, so there
is exactly one parsing step and one place a content change can go wrong.

Derived dish economics are RECOMPUTED here from the bill of materials rather than copied
out of the derived block in costs.yaml. The derived block exists so a human can read the
file; this function exists so the engine never depends on that block being up to date.

Owner: Person B.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from ..config import CONTENT_DIR
from ..schema import Channel, Product, Recipe, RecipeLine, ShelfLifeProfile, StorageZone

FILES = ("recipes.yaml", "yield_table.yaml", "costs.yaml", "shelf_life.yaml", "channels.yaml")


class ContentError(Exception):
    """The content pack is inconsistent. Always fatal — a demo on bad costs is worse than none."""


def read_pack(content_dir: Path | None = None) -> dict[str, Any]:
    base = content_dir or CONTENT_DIR
    pack: dict[str, Any] = {}
    for filename in FILES:
        path = base / filename
        if not path.exists():
            raise ContentError(f"missing content file: {path}")
        pack[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return pack


def _prep_yield(pack: dict, ingredient: str) -> float:
    entry = pack["yield_table"]["prep_yield"].get(ingredient)
    if isinstance(entry, dict):
        return float(entry["yield"])
    return float(pack["yield_table"]["default_prep_yield"])


def load_content(session: Session, content_dir: Path | None = None) -> dict[str, int]:
    """Populate the reference tables. Returns row counts for the seed's summary."""
    pack = read_pack(content_dir)
    counts: dict[str, int] = {}

    # --- shelf life profiles ------------------------------------------------
    for name, profile in pack["shelf_life"]["categories"].items():
        session.add(
            ShelfLifeProfile(
                id=name,
                base_shelf_life_days=float(profile["base_shelf_life_days"]),
                ref_temp_c=float(profile["ref_temp_c"]),
                q10=float(profile["q10"]),
                cut_life_factor=float(profile["cut_life_factor"]),
                ethylene_producer=bool(profile.get("ethylene_producer", False)),
                ethylene_sensitive=bool(profile.get("ethylene_sensitive", False)),
                freeze_tolerant=bool(profile.get("freeze_tolerant", False)),
                notes=profile.get("notes"),
            )
        )
    counts["shelf_life_profile"] = len(pack["shelf_life"]["categories"])

    # --- storage zones ------------------------------------------------------
    for zone_id, zone in pack["shelf_life"]["storage_zones"].items():
        session.add(
            StorageZone(
                id=zone_id,
                name=zone["name"],
                set_temp_c=float(zone["set_temp_c"]),
                typical_temp_c=float(zone["typical_temp_c"]),
                notes=zone.get("notes"),
            )
        )
    counts["storage_zone"] = len(pack["shelf_life"]["storage_zones"])

    # --- ingredients --------------------------------------------------------
    categories = pack["shelf_life"]["ingredients"]
    for ingredient_id, spec in pack["costs"]["ingredients"].items():
        category = categories.get(ingredient_id)
        if category is None:
            raise ContentError(f"ingredient {ingredient_id!r} has no shelf-life category")
        session.add(
            Product(
                id=ingredient_id,
                name=ingredient_id.replace("_", " ").title(),
                kind="ingredient",
                category=category,
                unit_cost_per_kg=float(spec["unit_cost_per_kg"]),
                co2e_kg_per_kg=float(spec["co2e_kg_per_kg"]),
                disposal_cost_per_kg=float(
                    spec.get("disposal_cost_per_kg", pack["costs"]["disposal_default_per_kg"])
                ),
                prep_yield=_prep_yield(pack, ingredient_id),
                shelf_life_profile_id=category,
            )
        )
    counts["ingredient"] = len(pack["costs"]["ingredients"])

    session.flush()

    # --- dishes, recipes, and the derived economics -------------------------
    economics = {d["id"]: d for d in pack["costs"]["dishes"]}
    labour = float(pack["costs"]["labour_cost_per_portion"])

    for dish in pack["recipes"]["dishes"]:
        dish_id = dish["id"]
        if dish_id not in economics:
            raise ContentError(f"dish {dish_id!r} has a recipe but no price in costs.yaml")

        food_cost = co2e = input_kg = disposal = 0.0
        for line in dish["lines"]:
            ingredient = session.get(Product, line["ingredient"])
            if ingredient is None:
                raise ContentError(f"dish {dish_id!r} uses unknown ingredient {line['ingredient']!r}")
            purchased = line["qty_kg"] / float(ingredient.prep_yield or 1.0)
            input_kg += purchased
            food_cost += purchased * float(ingredient.unit_cost_per_kg)
            co2e += purchased * float(ingredient.co2e_kg_per_kg)
            disposal += purchased * float(ingredient.disposal_cost_per_kg)

        price = float(economics[dish_id]["price"])
        session.add(
            Product(
                id=dish_id,
                name=dish["name"],
                kind="dish",
                category=dish.get("category"),
                price=price,
                portion_g=float(dish["portion_g"]),
                station=dish.get("station"),
                prep_ahead_hours=float(dish.get("prep_ahead_hours", 0)),
                is_veg=bool(dish.get("veg", False)),
                food_cost_per_portion=round(food_cost, 4),
                contribution_margin=round(price - food_cost - labour, 4),
                co2e_kg_per_portion=round(co2e, 5),
                input_kg_per_portion=round(input_kg, 5),
                disposal_cost_per_portion=round(disposal, 4),
            )
        )
        session.flush()

        recipe = Recipe(
            id=f"r_{dish_id}",
            dish_id=dish_id,
            portion_g=float(dish["portion_g"]),
            station=dish.get("station"),
        )
        session.add(recipe)
        session.flush()

        for line in dish["lines"]:
            session.add(
                RecipeLine(
                    recipe_id=recipe.id,
                    ingredient_id=line["ingredient"],
                    qty_kg=float(line["qty_kg"]),
                )
            )

    counts["dish"] = len(pack["recipes"]["dishes"])
    counts["recipe_line"] = sum(len(d["lines"]) for d in pack["recipes"]["dishes"])

    # --- channels -----------------------------------------------------------
    for channel in pack["channels"]["channels"]:
        session.add(
            Channel(
                id=channel["id"],
                name=channel["name"],
                type=channel["type"],
                basis=channel["basis"],
                recovery_factor=float(channel["recovery_factor"]),
                lead_time_hours=float(channel["lead_time_hours"]),
                min_residual_life_hours=float(channel["min_residual_life_hours"]),
                min_qty_kg=float(channel.get("min_qty_kg", 0.0)),
                max_qty_kg=channel.get("max_qty_kg"),
                states=list(channel["states"]),
                allowed_categories=channel["allowed_categories"],
                available_days=list(channel["available_days"]),
                cutoff_hour=int(channel["cutoff_hour"]),
                requires=list(channel.get("requires", [])),
                co2e_avoided_factor=float(channel.get("co2e_avoided_factor", 1.0)),
                is_baseline=bool(channel.get("is_baseline", False)),
                counterparty="Indiranagar" if channel["id"] == "b2b_transfer" else None,
                notes=channel.get("notes"),
            )
        )
    counts["channel"] = len(pack["channels"]["channels"])

    session.flush()
    return counts


def prices_from_pack(content_dir: Path | None = None):
    """The λ shadow prices, read once at startup."""
    from ..engine.optimiser import Prices

    pack = read_pack(content_dir)
    spec = pack["costs"]["lambda_price"]
    return Prices(
        co2e_price_per_kg=float(spec["co2e_price_per_kg"]),
        waste_externality_per_kg_food=float(spec["waste_externality_per_kg_food"]),
    )


def labour_cost(content_dir: Path | None = None) -> float:
    return float(read_pack(content_dir)["costs"]["labour_cost_per_portion"])


def exclusion_reasons(content_dir: Path | None = None) -> dict[str, str]:
    return dict(read_pack(content_dir)["channels"]["exclusion_reasons"])
