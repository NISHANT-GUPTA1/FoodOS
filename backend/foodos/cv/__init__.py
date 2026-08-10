"""Photo feature extraction — Person A.

Created empty by B at H2 so the package exists before anyone branches (§1,
FoodOS-Team-Split-v2.md). B does not put code in here.

Contract 1 (§2) puts one function in this package:

    foodos/cv/inference.py
    def extract_photo_features(image_paths: list[str], commodity: str) -> dict

It returns probabilistic features — maturity index, damage share, uniformity —
that feed `models/features.py::fuse()`. They are never rendered as verdicts, and
a batch with zero photos must still score through the rule-based fallback.
"""
