"""Calibration: does it converge, and does the shipped fit still hold.

These tests are weaker evidence than `test_behaviour.py` and are labelled as
such on purpose. Two knobs hitting two published numbers proves the bisection
worked. It says nothing about predictive accuracy, and this file must never be
cited as if it did.

What it does buy: a regression guard. If someone changes a measured constant,
the shipped `FITTED` pair stops reproducing NABCONS and this goes red — which is
the moment to re-run the calibrator, not to widen the tolerance.
"""

from __future__ import annotations

import numpy as np
import pytest

from foodos.agri.calibrate import fit
from foodos.agri.commodity import NABCONS_TOMATO, TOMATO
from foodos.agri.scenario import sample_baseline, sample_diverse
from foodos.agri.simulate import FITTED, CalibrationParams, simulate, summarise

#: Sampling noise at 20k scenarios is a few hundredths of a percentage point.
TOLERANCE_PCT = 0.25


def test_the_shipped_fit_still_reproduces_nabcons():
    """The regression guard. Red here means a measured constant moved and the
    calibrator needs re-running — never that this tolerance needs widening."""
    stats = summarise(simulate(sample_baseline(TOMATO, 20_000, seed=7)))
    assert stats["farm_operations_pct"] == pytest.approx(
        NABCONS_TOMATO.farm_operations_pct, abs=TOLERANCE_PCT
    )
    assert stats["market_level_pct"] == pytest.approx(
        NABCONS_TOMATO.market_level_pct, abs=TOLERANCE_PCT
    )


def test_both_fitted_scalars_are_physically_plausible():
    """The one genuinely interesting thing calibration tells us.

    The scalars are free to take any value in a 0.05-8.0 bracket. Landing near
    1.0 means the published biophysics and the published survey agree without
    being forced together. A scalar of 6.0 would mean one of them is wrong, and
    the model would be fitting that error rather than describing anything.
    """
    for name, value in (
        ("mechanical_scale", FITTED.mechanical_scale),
        ("spoilage_scale", FITTED.spoilage_scale),
    ):
        assert 0.5 <= value <= 2.0, f"{name}={value:.3f} is not a plausible correction"


def test_neither_scalar_is_pinned_against_a_bracket_edge():
    """A pinned scalar means the target was unreachable at any scale — the
    disagreement is structural, not a matter of degree. This caught a bad
    vibration constant on the very first run, which is why the check exists
    rather than being assumed."""
    _, report = fit(TOMATO, n=8_000, seed=7)
    assert all(report["converged"].values()), report["plausibility"]


def test_calibration_converges_from_the_default_start():
    params, report = fit(TOMATO, n=8_000, seed=7)
    assert abs(report["residual_pct_points"]["farm_operations"]) < 0.05
    assert abs(report["residual_pct_points"]["market_level"]) < 0.05
    assert params.mechanical_scale > 0.0 and params.spoilage_scale > 0.0


def test_the_fit_is_stable_across_independent_scenario_draws():
    """Fitted on one sample, checked on another. A fit that moves materially
    between seeds is fitting sampling noise, not the survey."""
    first, _ = fit(TOMATO, n=8_000, seed=7)
    second, _ = fit(TOMATO, n=8_000, seed=23)
    assert first.mechanical_scale == pytest.approx(second.mechanical_scale, rel=0.15)
    assert first.spoilage_scale == pytest.approx(second.spoilage_scale, rel=0.20)


def test_the_farm_target_is_not_reachable_by_spoilage_alone():
    """Guards the split, not the total.

    Both scalars at once can hit 11.62% combined in many ways. This pins that
    the mechanical channel is genuinely doing the farm-side work: switch it off
    and farm-operations loss must collapse well below 8.37%, because field heat
    over a few shaded hours cannot account for it. If this ever passes with
    mechanical off, the two channels have become interchangeable and the
    farm/market split has stopped meaning anything.
    """
    spoilage_only = CalibrationParams(
        mechanical_scale=1e-6, spoilage_scale=FITTED.spoilage_scale
    )
    stats = summarise(simulate(sample_baseline(TOMATO, 8_000, seed=7), spoilage_only))
    assert stats["farm_operations_pct"] < 0.5 * NABCONS_TOMATO.farm_operations_pct


def test_baseline_and_diverse_samplers_describe_different_populations():
    """Fit on baseline, train on diverse. If the two coincided, the model would
    never have to extrapolate off the calibration point and the behavioural
    checks would be measuring nothing."""
    baseline = summarise(simulate(sample_baseline(TOMATO, 8_000, seed=7)))
    diverse = summarise(simulate(sample_diverse(TOMATO, 8_000, seed=11)))
    assert not np.isclose(baseline["total_pct"], diverse["total_pct"], rtol=0.15)
