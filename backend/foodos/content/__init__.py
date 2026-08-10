"""The content pack — constants with a citation beside every one of them.

This package is data, not logic. It holds the numbers that decide what the
demo says, and the rule that governs it is short: **every constant has a
source in a comment.** "8.37%" with `# NABCONS 2022, MoFPI` beside it survives
a judge's question; the same number with no comment does not.

Files, and who reads them:

    commodities.yaml            A (RUL / loss physics), B (feasibility gates)
    packaging.yaml              A (thermal retention), B (cost terms)
    transport_modes.yaml        A (cooling / vibration), B (action costs)
    mandis.yaml                 B (destination candidates), D (route + price)
    questionnaire/tomato.yaml   C (renders it), A (feature_key -> fuse())
    channels.yaml               B (rescue channels; agri block is additive)
    shelf_life.yaml             the kitchen node's equivalent of commodities
    costs.yaml / recipes.yaml / yield_table.yaml   the kitchen node

`load()` below is the only reader anyone needs. It caches, so the hundred
reads a request path makes cost one file open, and it never mutates what it
hands back — a caller that edits the returned dict would silently rewrite the
constants for every later caller in the process.
"""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path

CONTENT_DIR = Path(__file__).resolve().parent


class ContentError(RuntimeError):
    """A content file is missing or unreadable.

    Raised rather than returning `{}` because a silently empty content pack
    means every commodity constant falls back to a default and every figure on
    stage is quietly wrong. Fail where it is cheap to notice.
    """


@lru_cache(maxsize=None)
def _read(name: str) -> dict:
    path = CONTENT_DIR / name
    if not path.exists():
        raise ContentError(f"content file not found: {path}")
    try:
        import yaml  # noqa: PLC0415 — pyyaml is D's dependency, imported lazily
    except ModuleNotFoundError as exc:  # pragma: no cover - environment problem
        raise ContentError("pyyaml is not installed; see backend/pyproject.toml") from exc
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ContentError(f"content file is not a mapping: {path}")
    return doc


def load(name: str) -> dict:
    """Read a content file by name, e.g. `load("commodities.yaml")`.

    Returns a deep copy so callers may edit their view freely.
    """
    return copy.deepcopy(_read(name))


def commodity(name: str) -> dict:
    """Constants for one commodity, merged over the pack-wide defaults.

    Raises `ContentError` for an unknown commodity rather than returning
    tomato's numbers under another name. Only tomato is in scope for this
    build — §10 of the team split rules out every other commodity — and a
    silent fallback would let a second one look like it works.
    """
    doc = load("commodities.yaml")
    defaults = doc.get("defaults") or {}
    row = (doc.get("commodities") or {}).get(str(name).strip().lower())
    if row is None:
        known = ", ".join(sorted(doc.get("commodities") or {}))
        raise ContentError(f"unknown commodity {name!r}; content pack has: {known}")
    return {**defaults, **row}


def mandis() -> dict[str, dict]:
    """Destination candidates, keyed by mandi id."""
    return load("mandis.yaml").get("mandis") or {}


def transport_modes() -> dict[str, dict]:
    return load("transport_modes.yaml").get("modes") or {}


def packaging_types() -> dict[str, dict]:
    return load("packaging.yaml").get("packaging") or {}


def questionnaire(commodity_name: str) -> dict:
    """The adaptive question tree C renders for a commodity.

    C never hardcodes this in TSX: the tree is data, so adding a second
    commodity is a content commit, not a frontend release.
    """
    return load(f"questionnaire/{str(commodity_name).strip().lower()}.yaml")


def agri_channels() -> list[dict]:
    """Agri diversion counterparties, from the additive block in channels.yaml.

    Deliberately a *separate* key from `channels:`. `ingest/channels.py` reads
    `channels:` and maps each row onto a `ChannelType` by id; an unmapped agri
    id would reach the ORM as an invalid enum value and break
    `python -m foodos.ingest.seed`, which is the one command that must never
    break. Additive block, zero risk to the kitchen node.
    """
    return load("channels.yaml").get("agri_channels") or []


__all__ = [
    "CONTENT_DIR",
    "ContentError",
    "agri_channels",
    "commodity",
    "load",
    "mandis",
    "packaging_types",
    "questionnaire",
    "transport_modes",
]
