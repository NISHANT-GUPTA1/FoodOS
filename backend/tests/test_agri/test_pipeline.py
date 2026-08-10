"""The inference pipeline: fusion, surrogate, intervals, ablation.

The first group is the important one. A leaked feature or a mis-encoded
category produces a model that looks excellent and is wrong, and neither
failure announces itself — so both are asserted rather than trusted.
"""

from __future__ import annotations

import numpy as np
import pytest

from foodos.agri import predict as P
from foodos.agri.commodity import TOMATO
from foodos.agri.features import (
    FEATURE_NAMES,
    FORBIDDEN_FEATURES,
    assert_no_leakage,
    build_features,
)
from foodos.agri.scenario import sample_diverse
from foodos.agri.simulate import simulate
from foodos.agri.uncertainty import DEFAULT_UNCERTAINTY, intervals, sensitivity

SHIPMENT = dict(
    quantity_kg=10_000.0,
    harvest_method="manual",
    harvest_window="morning",
    field_holding="shade",
    field_hours=3.0,
    packaging="ventilated_plastic_crate",
    transport_mode="open_truck",
    transit_hours=12.0,
    mandi_holding_hours=6.0,
    maturity_factor=1.0,
    visual_damage_fraction=0.03,
    ambient_mean_c=28.0,
    diurnal_amplitude_c=9.0,
    road_roughness=1.4,
)

HOT_LONG_HAUL = {**SHIPMENT, "transit_hours": 36.0, "ambient_mean_c": 34.0,
                 "maturity_factor": 1.75}


# ==========================================================================
# Leakage — the failure that would invalidate every accuracy figure
# ==========================================================================


def test_no_simulator_output_reaches_the_feature_matrix():
    frame = simulate(sample_diverse(TOMATO, 200, seed=1))
    features = build_features(frame)
    assert_no_leakage(features)
    assert not FORBIDDEN_FEATURES.intersection(features.columns)


def test_the_leakage_guard_actually_fires():
    """A guard nobody has seen fail is a guard nobody knows works."""
    frame = build_features(simulate(sample_diverse(TOMATO, 50, seed=1)))
    frame["cum_stress_transit"] = 1.0
    with pytest.raises(ValueError, match="leaked"):
        assert_no_leakage(frame)


def test_features_are_identical_from_a_batch_or_from_an_emitted_frame():
    """Training reads the CSV, inference holds a live scenario. If the two
    encode differently, every served prediction is quietly wrong."""
    batch = sample_diverse(TOMATO, 300, seed=2)
    from_batch = build_features(batch)
    from_frame = build_features(simulate(batch))

    assert list(from_batch.columns) == list(from_frame.columns) == FEATURE_NAMES
    for column in FEATURE_NAMES:
        left, right = from_batch[column], from_frame[column]
        if str(left.dtype) == "category":
            assert (left.astype(str).to_numpy() == right.astype(str).to_numpy()).all()
        else:
            assert np.allclose(left.to_numpy(), right.to_numpy())


def test_a_single_row_encodes_categories_the_same_way_as_a_full_batch():
    """The pinned-vocabulary bug. A one-row inference batch contains one
    packaging type; without fixed category lists its integer code would differ
    from training and the model would read it as a different crate entirely."""
    single = build_features(P._one(SHIPMENT))
    for name in ("packaging", "transport_mode", "harvest_window"):
        assert list(single[name].cat.categories) == list(
            build_features(sample_diverse(TOMATO, 500, seed=3))[name].cat.categories
        )


# ==========================================================================
# Surrogate — fidelity to the simulator, which is its only job
# ==========================================================================


def test_the_surrogate_reproduces_the_simulator_and_beats_the_mean():
    from foodos.agri.risk_model import build_dataset, train

    features, targets = build_dataset(12_000, seed=11)
    _, scores = train(features, targets, holdout=0.25, seed=42)

    loss = scores["loss"]
    assert loss.r2 > 0.95, f"surrogate R2 {loss.r2:.3f} is too low to be useful"
    assert loss.improvement_vs_baseline > 0.75, (
        "the surrogate barely beats predicting the mean, so the fusion layer "
        "is not carrying signal"
    )
    assert scores["rul"].r2 > 0.95


# ==========================================================================
# Intervals — from input uncertainty, and only from there
# ==========================================================================


def test_the_interval_brackets_the_point_estimate():
    band = intervals(SHIPMENT, n=1_500)
    point = float(P.run(SHIPMENT)["total_loss"]) * 100.0
    assert band["loss"].low <= point <= band["loss"].high
    assert band["loss"].width > 0.0


def test_a_better_known_shipment_gets_a_tighter_interval():
    """The interval must respond to how much the user actually knows. If it
    does not, it is decoration — and the "pin down your departure slot" advice
    that `sensitivity()` gives would be unbacked."""
    from foodos.agri.uncertainty import perturb

    vague = intervals(SHIPMENT, n=1_500)["loss"].width

    # A booked slot, a graded lot, a short forecast horizon: same shipment,
    # one tenth the uncertainty about it.
    tight_spec = {
        name: (kind, scale * 0.1) for name, (kind, scale) in DEFAULT_UNCERTAINTY.items()
    }
    losses = (
        simulate(
            perturb(
                SHIPMENT, 1_500, uncertainty=tight_spec, rng=np.random.default_rng(0)
            )
        )["total_loss"].to_numpy()
        * 100.0
    )
    tight = float(np.quantile(losses, 0.9) - np.quantile(losses, 0.1))

    assert tight < vague, "pinning the unknowns must narrow the band"


def test_sensitivity_names_a_real_contributor():
    ranked = sensitivity(HOT_LONG_HAUL, n=800)
    assert ranked
    assert ranked[0]["share_of_width"] > 0.0
    assert ranked[0]["field"] in DEFAULT_UNCERTAINTY
    # Ranked descending, so the answer to "what should I pin down" is row zero.
    shares = [r["width_removed_pp"] for r in ranked]
    assert shares == sorted(shares, reverse=True)


def test_certain_fields_are_never_perturbed():
    """The manager chose the truck. Jittering it would invent uncertainty."""
    from foodos.agri.uncertainty import CERTAIN_FIELDS, perturb

    batch = perturb(SHIPMENT, 200, rng=np.random.default_rng(0))
    for name in CERTAIN_FIELDS:
        column = getattr(batch, name)
        assert len(set(column.tolist())) == 1, f"{name} should not vary"


# ==========================================================================
# Ablation — the per-shipment drivers and actions
# ==========================================================================


def test_every_proposed_action_actually_reduces_loss():
    """An action that makes things worse must never be recommended.

    This test is why the ablation searches the choice set instead of
    assuming a best option: it caught a hardcoded 'pre-dawn is best' that
    is false on a long haul, because an early pick drags transit into the
    afternoon peak."""
    actions, _ = P.ablate(HOT_LONG_HAUL)
    for action in actions:
        assert action.loss_reduction_pp >= -1e-6, f"{action.label} made it worse"


def test_refrigeration_leads_the_actions_on_a_hot_long_haul():
    actions, _ = P.ablate(HOT_LONG_HAUL)
    assert actions[0].field == "transport_mode"


def test_drivers_are_separated_from_actions():
    """Telling an FPO manager to make August cooler is not a recommendation."""
    actions, drivers = P.ablate(HOT_LONG_HAUL)
    assert all(a.controllable for a in actions)
    assert all(not d.controllable for d in drivers)
    assert "ambient_mean_c" in {d.field for d in drivers}
    assert "ambient_mean_c" not in {a.field for a in actions}


def test_mass_saved_is_consistent_with_the_loss_reduction():
    actions, _ = P.ablate(HOT_LONG_HAUL)
    for action in actions:
        expected = action.loss_reduction_pp / 100.0 * HOT_LONG_HAUL["quantity_kg"]
        assert action.mass_saved_kg == pytest.approx(expected, abs=1.0)


# ==========================================================================
# The assembled profile
# ==========================================================================


def test_predict_returns_a_coherent_profile():
    profile = P.predict(SHIPMENT, mc_draws=600, with_sensitivity=False)

    assert 0.0 <= profile.loss_pct <= 100.0
    assert profile.loss_low_pct <= profile.loss_pct <= profile.loss_high_pct
    assert profile.rul_hours >= 0.0
    assert profile.risk_level in {"low", "medium", "high"}
    assert profile.quality_score == pytest.approx(100.0 - profile.loss_pct, abs=0.1)
    assert profile.mass_at_risk_kg == pytest.approx(
        profile.loss_pct / 100.0 * profile.quantity_kg, abs=1.0
    )


def test_stage_losses_reconcile_with_the_farm_market_split():
    profile = P.predict(SHIPMENT, mc_draws=400, with_sensitivity=False)
    total = sum(profile.stage_losses_pp.values())
    assert total == pytest.approx(
        profile.farm_operations_pp + profile.market_level_pp, abs=0.01
    )
    assert total == pytest.approx(profile.loss_pct, abs=0.01)


def test_what_if_agrees_with_a_direct_simulation():
    changed = {"transport_mode": "refrigerated", "field_hours": 1.0}
    report = P.what_if(SHIPMENT, **changed)
    direct = float(P.run({**SHIPMENT, **changed})["total_loss"]) * 100.0
    assert report["loss_after_pct"] == pytest.approx(direct, abs=0.01)
    assert report["loss_reduction_pp"] > 0.0


def test_the_profile_is_deterministic():
    first = P.predict(SHIPMENT, mc_draws=500, with_sensitivity=False)
    second = P.predict(SHIPMENT, mc_draws=500, with_sensitivity=False)
    assert first.as_dict() == second.as_dict()


def test_risk_level_thresholds_are_ordered():
    assert P.risk_level(0.02) == "low"
    assert P.risk_level(0.08) == "medium"
    assert P.risk_level(0.30) == "high"
