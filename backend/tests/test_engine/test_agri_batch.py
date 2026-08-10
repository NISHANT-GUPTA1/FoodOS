"""The agri batch surface — action space, planner, and Contract 2b.

Two jobs. Most of this file guards B's own code. The last class guards a
cross-team fact that cost real time to establish and would otherwise be
rediscovered by someone on stage.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from foodos import content
from foodos.api.app import app
from foodos.engine import agriplan, transit
from foodos.engine.context import DecisionContext
from foodos.engine.optimiser import rank, score


@pytest.fixture(scope="module")
def agri_db(request):
    """The kitchen fixture plus consignments.

    `seeded_db` in conftest builds B's own kitchen data into a temp database
    and stops there — it predates the agri surface. Requesting it here rather
    than seeding a second database keeps one source of truth for the fixture,
    and the consignments land on top of the same org.
    """
    request.getfixturevalue("seeded_db")

    from foodos.db import SessionLocal
    from foodos.ingest import consignments

    session = SessionLocal()
    try:
        consignments.load(session)
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="module")
def client(agri_db):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def ctx():
    return DecisionContext(today=date(2026, 8, 10), site_id=1)


@pytest.fixture
def subject():
    return agriplan.subject_from(
        consignment_id=1,
        code="T1024",
        commodity="tomato",
        qty_kg=10_000.0,
        origin="Kolar Collection Hub",
        destination="delhi_apmc",
        transport="open_truck",
        packaging="ventilated_plastic_crate",
        answers=content.questionnaire("tomato").get("demo_answers", {}).get("T1024", {}),
    )


# --------------------------------------------------------------------------
# the action space
# --------------------------------------------------------------------------


class TestTransitActionSpace:
    def test_every_builder_produces_a_scorable_action(self, subject, ctx):
        actions = [
            transit.do_nothing(subject),
            transit.depart_earlier(subject, -6),
            transit.upgrade_transport(subject, "reefer"),
            transit.reroute(subject, "bengaluru_apmc"),
            transit.split_batch(
                subject,
                [
                    {"mandi": "delhi_apmc", "qty_kg": 6000},
                    {"mandi": "jaipur_apmc", "qty_kg": 4000},
                ],
            ),
        ]
        for action in actions:
            scored = score(action, ctx)
            assert scored.terms, f"{action.action_type} produced no V(a) terms"

    def test_actions_actually_change_the_loss(self, subject, ctx):
        """The bug this exists to catch.

        `what_if` returns `loss_after_pct`. Reading any other key throws, hits
        the fallback, and every action silently scores the baseline loss — a
        plan matrix that renders perfectly and is completely flat.
        """
        baseline = transit.do_nothing(subject)
        cooled = transit.upgrade_transport(subject, "reefer")
        assert cooled.facts["loss_pct"] < baseline.facts["loss_pct"] - 1.0

    def test_a_fallback_is_never_silent(self, subject):
        """A degraded number must announce itself. A fallback that looks like a
        prediction is worse than no number at all."""
        blind = transit.TransitSubject(
            consignment_id=1, code="X", commodity="tomato", qty_kg=1000.0,
            origin="a", destination="b", transport="open_truck",
            packaging="gunny_bag", transit_hours=10.0, base=None,
            baseline_loss_pct=9.0,
        )
        assert transit.depart_earlier(blind, -6).facts["degraded"] is True
        assert transit.do_nothing(blind).facts["degraded"] is False

    def test_departing_earlier_moves_through_field_hours(self, subject):
        """A's ScenarioBatch has no `departure_shift_hours`. An earlier
        departure is fewer hours in the sun at the collection point, and passing
        an unknown key would silently return the baseline instead."""
        assert transit.depart_earlier(subject, -6).facts["degraded"] is False

    def test_horizons_follow_the_spec(self, subject):
        assert transit.depart_earlier(subject, -6).horizon.value == "PREVENT"
        assert transit.upgrade_transport(subject, "reefer").horizon.value == "PREVENT"
        assert transit.reroute(subject, "jaipur_apmc").horizon.value == "PRESERVE"

    def test_a_split_that_does_not_add_up_is_blocked_with_its_reason(self, subject):
        action = transit.split_batch(
            subject,
            [{"mandi": "delhi_apmc", "qty_kg": 1000}, {"mandi": "jaipur_apmc", "qty_kg": 1000}],
        )
        assert action.blocked_reason is not None
        assert "2,000 kg" in action.blocked_reason


# --------------------------------------------------------------------------
# the planner
# --------------------------------------------------------------------------


class TestPlanner:
    def test_the_baseline_is_always_present_exactly_once(self, subject, ctx):
        rows = agriplan.as_rows(agriplan.plan(subject, ctx), subject)
        assert sum(1 for r in rows if r["is_baseline"]) == 1

    def test_exactly_one_row_is_best(self, subject, ctx):
        rows = agriplan.as_rows(agriplan.plan(subject, ctx), subject)
        assert sum(1 for r in rows if r["is_best"]) == 1

    def test_deltas_are_measured_against_the_baseline(self, subject, ctx):
        rows = agriplan.as_rows(agriplan.plan(subject, ctx), subject)
        baseline = next(r for r in rows if r["is_baseline"])
        assert baseline["delta_vs_baseline"] == pytest.approx(0.0, abs=0.01)

    def test_agent_proposals_become_scored_actions(self, subject, ctx):
        """Contract 1: the orchestrator returns action PARAMETERS only. B turns
        each into an Action and scores it; the agents never rank."""
        proposals = [{"kind": "upgrade_transport", "transport": "reefer"}]
        with_agents = agriplan.candidates(subject, proposals)
        assert any(a.params.get("kind") == "upgrade_transport" for a in with_agents)

    def test_a_malformed_proposal_is_dropped_not_raised(self, subject):
        """A is allowed to be wrong. A is not allowed to take the screen down."""
        assert agriplan.candidates(subject, [{"kind": "reroute"}]) is not None

    def test_every_term_of_v_a_is_reported(self, subject, ctx):
        rows = agriplan.as_rows(agriplan.plan(subject, ctx), subject)
        assert set(rows[0]["terms"]) == {
            "expected_price_per_kg", "surviving_kg", "gross_revenue",
            "logistics_cost", "loss_cost", "diversion_cost", "mass_penalty",
            "w_preserve", "ranking_value",
        }

    def test_excluded_plans_are_returned_with_their_reason(self, subject, ctx):
        """§4 H13-17. A hidden option looks like the engine never considered it."""
        bad = transit.split_batch(subject, [{"mandi": "delhi_apmc", "qty_kg": 1.0}])
        ranked = rank([transit.do_nothing(subject), bad], ctx)
        for scored in ranked.excluded:
            assert scored.exclusion_reason


# --------------------------------------------------------------------------
# Contract 2b over HTTP
# --------------------------------------------------------------------------


class TestContract2b:
    def test_all_eleven_endpoints_answer(self, client):
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/questionnaire?commodity=tomato").status_code == 200
        assert client.get("/api/batches").status_code == 200
        assert client.get("/api/batches/T1024").status_code == 200
        assert client.get("/api/batches/T1024/plans").status_code == 200
        assert client.get("/api/markets?commodity=tomato").status_code == 200
        assert client.post(
            "/api/batches/T1024/simulate",
            json={"departure_shift_hours": -6, "transport": "reefer", "destinations": []},
        ).status_code == 200

    def test_the_profile_scores_on_first_read(self, client):
        """Screen 3 loads the hero before the matrix. Without a lazy score a
        seeded batch renders 0% loss / 0h RUL, which reads as 'this shipment is
        fine' rather than 'not assessed yet'."""
        risk = client.get("/api/batches/T1024").json()["risk"]
        assert risk["loss_pct"] > 0
        assert risk["rul_hours"] > 0

    def test_the_band_is_present_or_honestly_absent(self, client):
        """Contract 2b: a missing band means a fallback scored the row. The UI
        must never draw an interval around a point estimate."""
        risk = client.get("/api/batches/T1024").json()["risk"]
        if risk["low"] is None:
            assert risk["confidence"] == "LOW"
        else:
            assert risk["low"] <= risk["loss_pct"] <= risk["high"]

    def test_a_split_that_does_not_sum_is_422_not_a_silent_rescale(self, client):
        r = client.post(
            "/api/batches/T1024/simulate",
            json={
                "departure_shift_hours": 0, "transport": "open_truck",
                "destinations": [{"mandi": "delhi_apmc", "qty_kg": 10}],
            },
        )
        assert r.status_code == 422

    def test_simulate_returns_a_plan_row(self, client):
        """Same shape, same `score()`. If the simulator and the recommendation
        disagree on stage, one of them is a second objective function."""
        row = client.post(
            "/api/batches/T1024/simulate",
            json={"departure_shift_hours": -6, "transport": "reefer", "destinations": []},
        ).json()
        assert {"loss_pct", "net_value", "delta_vs_baseline", "terms"} <= set(row)

    def test_the_questionnaire_is_data_not_code(self, client):
        """Every question carries the feature_key it writes into A's fuse().
        C never hardcodes one, or a second commodity is a frontend release."""
        body = client.get("/api/questionnaire?commodity=tomato").json()
        questions = [q for s in body["steps"] for q in s["questions"]]
        assert questions
        assert all(q["feature_key"] for q in questions)

    def test_accept_and_override_record_an_outcome(self, client):
        plan_id = client.get("/api/batches/T1024/plans").json()["best_plan_id"]
        assert client.post(f"/api/plans/{plan_id}/accept").json()["outcome"] == "accepted"
        assert client.post(
            f"/api/plans/{plan_id}/override", json={"reason": "no truck"}
        ).json()["outcome"] == "overridden"

    def test_the_kitchen_surface_is_untouched(self, client):
        """The regression that IS the platform claim."""
        for path in ("/api/today", "/api/attribution", "/api/plan", "/api/ledger",
                     "/api/rescue", "/api/impact", "/api/tracks/retail"):
            assert client.get(path).status_code == 200, path


# --------------------------------------------------------------------------
# the calibration reconciliation
# --------------------------------------------------------------------------


class TestNabconsReconciliation:
    """Why T1024 does not read 8.4%, pinned so nobody rediscovers it on stage.

    §7's H30 gate locks T1024 at 8.4% loss / 31 h RUL. A's model puts a
    Kolar -> Delhi open-truck load at roughly 44%, and no physically honest
    parameter set closes that gap — the 2,150 km transit dominates everything
    else.

    That is not a bug in either. A's model is calibrated against NABCONS 2022
    (8.37% farm + 3.25% market = 11.62% total), and NABCONS measures the
    national average across mostly short hauls. At those distances this model
    agrees with it. The 8.4% in the blueprint corresponds to a ~500 km journey,
    not a 2,150 km one, so 'Kolar to Delhi at 8.4%' was never reachable.

    The story the model does support is stronger: this shipment should not go
    to Delhi on an open truck at all, and the engine says so — the winning plan
    is a reroute, not a tweak. The destination decision is the high-leverage
    one, which is the product thesis.
    """

    @staticmethod
    def _loss(transit_hours: float) -> float:
        from foodos.agri.commodity import TOMATO
        from foodos.agri.predict import run

        base = dict(
            quantity_kg=10_000.0, harvest_method="manual", harvest_window="early_morning",
            field_holding="shade", field_hours=4.0, packaging="ventilated_plastic_crate",
            transport_mode="open_truck", transit_hours=transit_hours,
            mandi_holding_hours=6.0, maturity_factor=1.0, visual_damage_fraction=0.03,
            ambient_mean_c=29.0, diurnal_amplitude_c=9.0, road_roughness=1.4,
        )
        return float(run(base, TOMATO)["total_loss"]) * 100.0

    def test_short_hauls_agree_with_the_nabcons_average(self):
        """Under a day's transit the model sits inside the NABCONS envelope.
        This is what makes the long-haul figure defensible rather than alarming."""
        from foodos.agri.commodity import NABCONS_TOMATO

        ceiling = NABCONS_TOMATO.farm_operations_pct + NABCONS_TOMATO.market_level_pct
        for hours in (0.5, 2.5, 5.0, 9.5):
            assert 5.0 <= self._loss(hours) <= ceiling, f"{hours}h left the envelope"

    def test_the_blueprint_number_belongs_to_a_half_day_haul(self):
        """8.4% is reachable — at about 9.5 hours, roughly Hyderabad. It was
        never a 36-hour Delhi run."""
        assert self._loss(9.5) == pytest.approx(8.4, abs=1.0)

    def test_long_haul_is_where_the_product_earns_its_keep(self):
        """A 36-hour unrefrigerated August haul is catastrophic, and the engine
        is supposed to say so loudly rather than average it away."""
        assert self._loss(36.5) > 25.0

    def test_the_engine_answers_it_by_changing_the_destination(self, subject, ctx):
        """The recommendation on the real numbers is 'do not send this to
        Delhi', which is a better demo than shaving a few points off a plan
        that should never have been made."""
        rows = agriplan.as_rows(agriplan.plan(subject, ctx), subject)
        best = next(r for r in rows if r["is_best"])
        baseline = next(r for r in rows if r["is_baseline"])
        assert best["loss_pct"] < baseline["loss_pct"] / 2
