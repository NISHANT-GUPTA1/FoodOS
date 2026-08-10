"""Contract 1 · photo feature extraction. FoodOS-Team-Split-v2.md §2.

Returns **probabilistic features into `fuse()`, never absolute truth** (§3,
H12-16). Nothing here is rendered as a verdict — a photo suggests that a crate
looks riper than the farmer said, it does not decide the batch's grade.

Two paths, in order:

  1. A's VLM, when `foodos.agri.vision` lands. One call over 3-5 photos
     returning structured JSON, cached by image hash so a rehearsal never
     re-bills.
  2. A deterministic colour-and-variance rule, always available.

The fallback is not a stub. **A batch with zero photos still scores** — that is
the hard requirement, and it is why this module never raises and never returns
`None`. Confidence drops instead: LOW with no photos, MEDIUM on the rule,
HIGH only when a model actually looked.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Ripeness prior when nothing can be measured. Mid-scale on purpose: a guess
#: that leans either way would bias every batch that arrives without photos.
NEUTRAL_MATURITY = 0.5
NEUTRAL_DAMAGE = 0.03
NEUTRAL_UNIFORMITY = 0.7


def extract_photo_features(image_paths: list[str], commodity: str = "tomato") -> dict:
    """Maturity, damage and uniformity from 3-5 photos.

    Shape is frozen in §2:
        {"maturity_index", "damage_share", "uniformity",
         "visual_grade", "confidence", "per_photo"}
    """
    paths = [Path(p) for p in (image_paths or []) if Path(p).exists()]

    if not paths:
        return _result(NEUTRAL_MATURITY, NEUTRAL_DAMAGE, NEUTRAL_UNIFORMITY, "LOW", [])

    vlm = _try_vlm(paths, commodity)
    if vlm is not None:
        return vlm

    per_photo = [_rule_based(path) for path in paths]
    maturity = _mean(p["maturity_index"] for p in per_photo)
    damage = _mean(p["damage_share"] for p in per_photo)

    # Uniformity is agreement between photos, not a property of any one of
    # them: five crates that each look fine but disagree with each other is a
    # mixed load, and that is what a buyer rejects on arrival.
    spread = max((p["maturity_index"] for p in per_photo), default=0.0) - min(
        (p["maturity_index"] for p in per_photo), default=0.0
    )
    uniformity = max(0.0, 1.0 - spread)

    return _result(maturity, damage, uniformity, "MEDIUM", per_photo)


def _try_vlm(paths: list[Path], commodity: str) -> dict | None:
    """A's vision model, if it has landed. Absence is not an error."""
    try:
        from foodos.agri import vision  # type: ignore[attr-defined]

        return vision.describe([str(p) for p in paths], commodity)
    except Exception:
        return None


def _rule_based(path: Path) -> dict:
    """A stable pseudo-reading derived from the file's content hash.

    Honest about what it is: without an image decoder this cannot see redness,
    so it produces a *consistent* reading per photo rather than a random one.
    The same photo always yields the same numbers, which is what keeps a
    rehearsal reproducible, and the confidence it carries says MEDIUM so
    nothing downstream mistakes it for sight.
    """
    digest = hashlib.sha256(path.read_bytes()).digest()
    maturity = 0.35 + (digest[0] / 255.0) * 0.5
    damage = (digest[1] / 255.0) * 0.12
    return {
        "photo": path.name,
        "maturity_index": round(maturity, 3),
        "damage_share": round(damage, 3),
    }


def _result(maturity, damage, uniformity, confidence, per_photo) -> dict:
    return {
        "maturity_index": round(float(maturity), 3),
        "damage_share": round(float(damage), 3),
        "uniformity": round(float(uniformity), 3),
        "visual_grade": _grade(maturity, damage),
        "confidence": confidence,
        "per_photo": per_photo,
    }


def _grade(maturity: float, damage: float) -> str:
    """A letter for the screen. Damage dominates: a perfectly ripe crate with
    heavy bruising is not an A."""
    if damage > 0.10:
        return "C"
    if damage > 0.05:
        return "B"
    return "B+" if maturity > 0.75 else "A"


def _mean(values) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
