"""The identity layer: codes, lifecycle, custody, splitting, FEFO."""

from __future__ import annotations

from datetime import timedelta

import pytest

from foodos.engine import batch_identity as identity
from foodos.schema.enums import BatchEventType, BatchLifecycle, PartyRole

from .conftest import HARVEST

L = BatchLifecycle


# ---------------------------------------------------------------- codes


def test_commodity_slug_is_the_readable_prefix():
    assert identity.commodity_slug("tomato") == "TOM"
    assert identity.commodity_slug("Onion") == "ONI"


def test_origin_slug_separates_districts_that_collide_at_three_letters():
    """The whole reason for squeezing vowels rather than truncating."""
    assert identity.origin_slug("Kolar Collection Hub") == "KLR"
    assert identity.origin_slug("Kolhapur") == "KLH"
    assert identity.origin_slug("Kollam") == "KLL"
    # Truncation would map all three to KOL. Squeezing keeps them apart, which
    # is the property that matters — the exact letters are incidental.
    assert len({identity.origin_slug(p) for p in ("Kolar", "Kolhapur", "Kollam")}) == 3


def test_origin_slug_ignores_everything_after_the_first_word():
    """"Kolar Collection Hub" and "Kolar Farm Gate" are one place for the
    purpose of a code; the precise location lives on the batch, unabbreviated."""
    assert identity.origin_slug("Kolar Farm Gate") == identity.origin_slug("Kolar")


def test_code_matches_the_published_pattern(session, make_batch):
    batch = make_batch()
    assert identity.CODE_RE.match(batch.code), batch.code


def test_counter_is_scoped_to_commodity_and_origin(session, make_batch):
    a = make_batch()
    b = make_batch()
    c = make_batch(origin="Hassan Farmer Producer Co")
    assert a.code.endswith("00001") and b.code.endswith("00002")
    # A different origin starts its own counter rather than continuing.
    assert c.code.endswith("00001")
    assert c.code != a.code


def test_child_codes_do_not_advance_the_parent_counter(session, make_batch):
    parent = make_batch()
    identity.split(
        session, parent,
        [identity.Allocation(5000, "A"), identity.Allocation(5000, "B")],
        occurred_at=HARVEST + timedelta(hours=1),
    )
    nxt = identity.next_code(session, "tomato", "Kolar Collection Hub")
    assert nxt.endswith("00002"), nxt


def test_child_code_uses_letters(session):
    assert identity.child_code("TOM-KLR-00124", 0) == "TOM-KLR-00124-A"
    assert identity.child_code("TOM-KLR-00124", 2) == "TOM-KLR-00124-C"


# ---------------------------------------------------------------- lifecycle


def test_the_happy_path_is_legal():
    ladder = [
        L.CREATED, L.ASSESSED, L.READY_FOR_DISPATCH, L.IN_TRANSIT,
        L.ARRIVED, L.RECEIVED, L.IN_INVENTORY, L.SOLD,
    ]
    for current, target in zip(ladder, ladder[1:]):
        assert identity.can_transition(current, target), f"{current} -> {target}"


def test_a_batch_cannot_skip_the_road():
    assert not identity.can_transition(L.ASSESSED, L.IN_TRANSIT)
    assert not identity.can_transition(L.CREATED, L.RECEIVED)


def test_diversion_is_reachable_from_the_road_and_is_not_an_ending():
    """A diverted batch still has a fate to record — booking the diversion as
    the outcome would count every rescue as a success we never confirmed."""
    assert identity.can_transition(L.IN_TRANSIT, L.DIVERTED)
    assert not L.DIVERTED.is_terminal
    assert identity.can_transition(L.DIVERTED, L.PROCESSED)


def test_terminal_states_go_nowhere():
    for state in (L.SOLD, L.PROCESSED, L.DONATED, L.WASTED):
        assert state.is_terminal
        assert identity.TRANSITIONS[state] == frozenset()


def test_every_live_state_can_reach_wasted():
    for state, allowed in identity.TRANSITIONS.items():
        if state.is_terminal:
            continue
        assert L.WASTED in allowed, state


def test_reassessment_is_a_legal_self_loop():
    assert identity.can_transition(L.ASSESSED, L.ASSESSED)
    # But a second arrival report is not.
    assert not identity.can_transition(L.ARRIVED, L.ARRIVED)


def test_contract_2b_statuses_are_the_only_ones_projected():
    """C filters on four values. The richer ladder must never leak new ones."""
    assert {s.contract_status for s in L} == {
        "registered", "assessed", "in_transit", "delivered",
    }


def test_illegal_event_raises_and_writes_nothing(session, make_batch):
    batch = make_batch()
    with pytest.raises(identity.LifecycleError):
        identity.apply_event(
            session, batch, BatchEventType.RECEIVED, occurred_at=HARVEST
        )
    assert batch.events == []
    assert BatchLifecycle(batch.status) is L.CREATED


def test_events_record_the_transition_they_caused(session, in_transit):
    dispatched = [
        e for e in in_transit.events
        if BatchEventType(e.type) is BatchEventType.DISPATCHED
    ][0]
    assert BatchLifecycle(dispatched.from_status) is L.READY_FOR_DISPATCH
    assert BatchLifecycle(dispatched.to_status) is L.IN_TRANSIT


def test_informational_events_do_not_move_the_lifecycle(session, in_transit):
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=10), payload={"duration_hours": 6},
    )
    assert BatchLifecycle(in_transit.status) is L.IN_TRANSIT


def test_only_physical_events_ask_for_a_rescore():
    assert BatchEventType.DELAY.rescores
    assert BatchEventType.TEMPERATURE_EXPOSURE.rescores
    # A change of owner does not change a tomato's temperature.
    assert not BatchEventType.HANDOFF.rescores
    assert not BatchEventType.SOLD.rescores


# ---------------------------------------------------------------- custody


def test_handoff_keeps_the_same_batch_id(session, in_transit):
    before = in_transit.code
    identity.apply_event(
        session, in_transit, BatchEventType.ARRIVED,
        occurred_at=HARVEST + timedelta(hours=45),
    )
    identity.hand_over(
        session, in_transit, to_party="Azadpur Wholesaler",
        to_role=PartyRole.WHOLESALER, occurred_at=HARVEST + timedelta(hours=46),
    )
    assert in_transit.code == before
    assert in_transit.current_owner == "Azadpur Wholesaler"


def test_partial_acceptance_books_the_shortfall_as_waste(session, in_transit):
    """A load rejected at the gate is a real loss; it must not evaporate
    between the transporter's ledger and the wholesaler's."""
    identity.hand_over(
        session, in_transit, to_party="Azadpur Wholesaler",
        to_role=PartyRole.WHOLESALER, occurred_at=HARVEST + timedelta(hours=46),
        qty_kg=9_850,
    )
    assert in_transit.qty_kg_remaining == 9_850
    assert in_transit.qty_kg == 10_000  # as registered, never overwritten
    wasted = [e for e in in_transit.events if BatchEventType(e.type) is BatchEventType.WASTED]
    assert len(wasted) == 1 and wasted[0].qty_kg == 150.0
    # and the batch is still alive, not written off entirely
    assert not BatchLifecycle(in_transit.status).is_terminal


def test_cannot_hand_over_more_than_remains(session, in_transit):
    with pytest.raises(ValueError, match="only"):
        identity.hand_over(
            session, in_transit, to_party="X", to_role=PartyRole.WHOLESALER,
            occurred_at=HARVEST + timedelta(hours=46), qty_kg=11_000,
        )


def test_custody_chain_starts_at_the_origin(session, in_transit):
    identity.hand_over(
        session, in_transit, to_party="Azadpur Wholesaler",
        to_role=PartyRole.WHOLESALER, occurred_at=HARVEST + timedelta(hours=46),
    )
    chain = identity.custody_chain(in_transit)
    assert [c["role"] for c in chain] == ["fpo", "wholesaler"]


# ---------------------------------------------------------------- splitting


def test_split_children_carry_the_parent(session, in_transit):
    kids = identity.split(
        session, in_transit,
        [identity.Allocation(3000, "Retailer A"), identity.Allocation(7000, "Retailer B")],
        occurred_at=HARVEST + timedelta(hours=47),
    )
    assert [k.code[-2:] for k in kids] == ["-A", "-B"]
    assert all(k.parent_id == in_transit.id for k in kids)
    assert in_transit.qty_kg_remaining == 0.0
    # The parent row survives — it is what the chain rolls up to.
    assert in_transit.qty_kg == 10_000


def test_split_must_balance(session, in_transit):
    with pytest.raises(ValueError, match="allocations sum"):
        identity.split(
            session, in_transit,
            [identity.Allocation(3000, "A"), identity.Allocation(4000, "B")],
            occurred_at=HARVEST + timedelta(hours=47),
        )


def test_split_refuses_a_zero_or_negative_allocation(session, in_transit):
    with pytest.raises(ValueError):
        identity.split(
            session, in_transit,
            [identity.Allocation(10_500, "A"), identity.Allocation(-500, "B")],
            occurred_at=HARVEST + timedelta(hours=47),
        )


def test_children_inherit_the_journey_and_the_timeline(session, in_transit):
    """Three tonnes that already spent forty hours on an open truck are not
    fresh produce. A child scored without that past outscores its own parent."""
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=20), payload={"duration_hours": 6},
    )
    kids = identity.split(
        session, in_transit, [identity.Allocation(10_000, "Retailer A")],
        occurred_at=HARVEST + timedelta(hours=47),
    )
    child = kids[0]
    inherited = {str(e.type) for e in child.events}
    assert {"dispatched", "delay"} <= inherited
    assert all(e.payload.get("inherited") for e in child.events)
    assert child.journey is not None
    assert child.journey.transit_hours == in_transit.journey.transit_hours
    # The parent's own split event is not copied onto the child.
    assert "split" not in inherited


def test_a_child_cannot_be_split_again(session, in_transit):
    kids = identity.split(
        session, in_transit, [identity.Allocation(10_000, "A")],
        occurred_at=HARVEST + timedelta(hours=47),
    )
    with pytest.raises(ValueError, match="already a child"):
        identity.split(
            session, kids[0], [identity.Allocation(10_000, "B")],
            occurred_at=HARVEST + timedelta(hours=48),
        )


# ---------------------------------------------------------------- FEFO


def test_fefo_sorts_by_life_not_by_arrival(session, make_batch):
    from foodos.engine import batch_intelligence as intelligence

    now = HARVEST + timedelta(hours=8)
    # Old but travelling cold, versus fresh but on an open truck in the heat.
    old_cold = make_batch(
        harvested_at=HARVEST - timedelta(hours=24), transit_hours=4.0,
        transport=__import__(
            "foodos.schema.enums", fromlist=["TransportMode"]
        ).TransportMode.REEFER,
    )
    new_hot = make_batch(harvested_at=HARVEST, transit_hours=40.0)
    for b in (old_cold, new_hot):
        intelligence.rescore(session, b, as_of=now, reason="test")

    rows = identity.fefo_order([old_cold, new_hot], now=now)
    assert rows[0].code == new_hot.code, "FEFO must pick the shorter-lived batch"
    # FIFO would have taken the older one, so both rows disagree with it.
    assert all(r.beats_fifo for r in rows)


def test_unscored_batches_sort_last(session, make_batch):
    from foodos.engine import batch_intelligence as intelligence

    now = HARVEST + timedelta(hours=8)
    scored = make_batch()
    unscored = make_batch()
    intelligence.rescore(session, scored, as_of=now, reason="test")

    rows = identity.fefo_order([unscored, scored], now=now)
    assert rows[0].code == scored.code
    assert rows[-1].code == unscored.code and rows[-1].rul_hours is None


def test_fefo_skips_empty_batches(session, in_transit):
    identity.split(
        session, in_transit, [identity.Allocation(10_000, "A")],
        occurred_at=HARVEST + timedelta(hours=47),
    )
    rows = identity.fefo_order([in_transit], now=HARVEST + timedelta(hours=48))
    assert rows == []
