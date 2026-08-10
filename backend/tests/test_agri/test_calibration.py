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

from foodos.agri.calibrate import fit, holdout_report
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


def test_the_model_generalises_to_commodities_it_was_not_fitted_on():
    """The strongest check available, and for a while it failed outright.

    Calibrate the two global scalars on tomato, then predict guava and potato
    using only measured constants — activation energy, reference life, chilling
    behaviour, mechanical susceptibility, cosmetic grade-out. No information
    from the held-out commodities reaches the fit.

    The bar is the naive predictor: assign every crop the average published
    loss. A model that cannot beat that has earned nothing. The original
    two-channel engine scored 6.43 pp against naive 4.52 pp — worse than a
    constant — because a commodity-blind damage channel pinned farm loss near
    8.2% whatever the crop was.
    """
    report = holdout_report(n=8_000)

    assert report["beats_naive"], (
        f"held-out error {report['mean_abs_error']} pp is worse than the naive "
        f"{report['naive_mean_abs_error']} pp -- the model does not generalise"
    )
    assert report["mean_abs_error"] < 3.5
    assert {row["commodity"] for row in report["rows"]} == {"guava", "potato"}


def test_cosmetic_gradeout_is_measured_and_not_absorbed_by_the_fit():
    """Grade-out must come straight from the survey. If a future change lets
    the calibrator move it, the farm/market split stops being attributable and
    held-out prediction quietly breaks again."""
    from foodos.agri.commodity import COMMODITIES
    from foodos.agri.simulate import precompute, stage_losses
    from foodos.agri.scenario import sample_baseline

    for commodity in COMMODITIES.values():
        physics = precompute(sample_baseline(commodity, 400, seed=7))
        for scalars in (CalibrationParams(0.4, 0.4), CalibrationParams(2.0, 2.0)):
            computed = stage_losses(physics, scalars)
            assert float(np.mean(computed["cosmetic_gradeout"])) == pytest.approx(
                commodity.cosmetic_gradeout_pct / 100.0, abs=1e-9
            )
