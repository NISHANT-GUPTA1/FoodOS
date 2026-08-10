"""Loader for the YAML content pack.

Read-only. This module answers "what is a cauliflower worth, how long does it live, and
where can it go" for the agent layer and for the content tests. The engine reads the same
YAML through Person B's own loader — the files are the contract, not this class.

Owner: Person D.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .settings import CONTENT_DIR

FILES = {
    "recipes": "recipes.yaml",
    "yields": "yield_table.yaml",
    "costs": "costs.yaml",
    "shelf_life": "shelf_life.yaml",
    "channels": "channels.yaml",
}


class ContentError(Exception):
    """The content pack is internally inconsistent. Always fatal — never fall back."""


@dataclass(frozen=True)
class ContentPack:
    recipes: Mapping[str, Any]
    yields: Mapping[str, Any]
    costs: Mapping[str, Any]
    shelf_life: Mapping[str, Any]
    channels: Mapping[str, Any]
    root: Path

    # --- dishes ------------------------------------------------------------
    @functools.cached_property
    def dishes(self) -> dict[str, dict[str, Any]]:
        return {d["id"]: d for d in self.recipes["dishes"]}

    @functools.cached_property
    def dish_economics(self) -> dict[str, dict[str, Any]]:
        return {d["id"]: d for d in self.costs["dishes"]}

    @functools.cached_property
    def dish_names(self) -> dict[str, str]:
        return {d["id"]: d["name"] for d in self.recipes["dishes"]}

    # --- ingredients -------------------------------------------------------
    @functools.cached_property
    def ingredients(self) -> dict[str, dict[str, Any]]:
        return dict(self.costs["ingredients"])

    @functools.cached_property
    def ingredient_names(self) -> dict[str, str]:
        return {i: i.replace("_", " ").title() for i in self.ingredients}

    # --- channels ----------------------------------------------------------
    @functools.cached_property
    def channels_by_id(self) -> dict[str, dict[str, Any]]:
        return {c["id"]: c for c in self.channels["channels"]}

    @functools.cached_property
    def preserve_actions(self) -> dict[str, dict[str, Any]]:
        return {a["id"]: a for a in self.channels.get("preserve_actions", [])}

    @functools.cached_property
    def exclusion_reasons(self) -> dict[str, str]:
        return dict(self.channels["exclusion_reasons"])

    # --- lookups the agents and tests use ----------------------------------
    def prep_yield(self, ingredient: str) -> float:
        entry = self.yields["prep_yield"].get(ingredient)
        if isinstance(entry, Mapping):
            return float(entry["yield"])
        return float(self.yields["default_prep_yield"])

    def category_of(self, ingredient: str) -> str:
        try:
            return self.shelf_life["ingredients"][ingredient]
        except KeyError:
            raise ContentError(
                f"ingredient {ingredient!r} has no shelf-life category in shelf_life.yaml"
            ) from None

    def shelf_life_profile(self, ingredient: str) -> dict[str, Any]:
        return self.shelf_life["categories"][self.category_of(ingredient)]

    def unit_cost(self, ingredient: str) -> float:
        return float(self.ingredients[ingredient]["unit_cost_per_kg"])

    def co2e_per_kg(self, ingredient: str) -> float:
        return float(self.ingredients[ingredient]["co2e_kg_per_kg"])

    def food_cost_per_portion(self, dish_id: str) -> float:
        """Recomputed from the BOM, never read from the derived block.

        The derived block in costs.yaml exists for the engine's convenience and for
        humans reading the file. It is checked against this function by the content test,
        so the two can never quietly drift apart.
        """
        total = 0.0
        for line in self.dishes[dish_id]["lines"]:
            ing = line["ingredient"]
            total += (line["qty_kg"] / self.prep_yield(ing)) * self.unit_cost(ing)
        return total

    def co2e_per_portion(self, dish_id: str) -> float:
        total = 0.0
        for line in self.dishes[dish_id]["lines"]:
            ing = line["ingredient"]
            total += (line["qty_kg"] / self.prep_yield(ing)) * self.co2e_per_kg(ing)
        return total

    def input_kg_per_portion(self, dish_id: str) -> float:
        return sum(
            line["qty_kg"] / self.prep_yield(line["ingredient"])
            for line in self.dishes[dish_id]["lines"]
        )

    def disposal_cost_per_portion(self, dish_id: str) -> float:
        total = 0.0
        for line in self.dishes[dish_id]["lines"]:
            ing = line["ingredient"]
            per_kg = float(
                self.ingredients[ing].get(
                    "disposal_cost_per_kg", self.costs["disposal_default_per_kg"]
                )
            )
            total += (line["qty_kg"] / self.prep_yield(ing)) * per_kg
        return total

    def contribution_margin(self, dish_id: str) -> float:
        price = float(self.dish_economics[dish_id]["price"])
        return price - self.food_cost_per_portion(dish_id) - float(
            self.costs["labour_cost_per_portion"]
        )

    def known_names(self) -> set[str]:
        """Every proper name an agent is allowed to say — dishes, ingredients, channels.

        The Verifier uses this to catch a hallucinated entity: text that names a dish the
        facts never mentioned is blocked, however plausible the sentence reads.
        """
        names = set(self.dish_names.values())
        names |= set(self.ingredient_names.values())
        names |= {c["name"] for c in self.channels["channels"]}
        names |= {a["name"] for a in self.channels.get("preserve_actions", [])}
        return names


@functools.lru_cache(maxsize=4)
def load_content(root: Path | str | None = None) -> ContentPack:
    """Load and cache the content pack. Fails loudly and specifically."""
    base = Path(root) if root else CONTENT_DIR
    loaded: dict[str, Any] = {}
    for key, filename in FILES.items():
        path = base / filename
        if not path.exists():
            raise ContentError(f"missing content file: {path}")
        try:
            loaded[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ContentError(f"{filename} is not valid YAML: {exc}") from exc
    return ContentPack(root=base, **loaded)
