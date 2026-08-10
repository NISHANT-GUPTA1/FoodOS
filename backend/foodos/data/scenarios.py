"""Contract 1 · `generate_scenarios()`. FoodOS-Team-Split-v2.md §2.

Physics-based synthetic shipments: every input feature plus the realised loss
and RUL. Adapter over `foodos.agri.scenario` and `foodos.agri.simulate` — the
sampling and the physics are A's, this writes the file.
"""

from __future__ import annotations

from pathlib import Path


def generate_scenarios(out_path: str, n: int = 100_000, seed: int = 42) -> None:
    """Write one CSV of simulated shipments.

    `sample_diverse` rather than `sample_baseline`: a training set drawn only
    from typical conditions teaches a model nothing about the tail, and the
    tail is where this product earns its keep.
    """
    from foodos.agri.commodity import TOMATO
    from foodos.agri.scenario import sample_diverse
    from foodos.agri.simulate import simulate

    batch = sample_diverse(TOMATO, n=n, seed=seed)
    frame = simulate(batch)

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
