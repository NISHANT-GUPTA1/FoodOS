"""Controlled vocabularies. String enums so the SQLite rows stay readable."""

from __future__ import annotations

from enum import StrEnum


class Track(StrEnum):
    KITCHEN = "kitchen"
    RETAIL = "retail"
    PRODUCTION = "production"


class SiteType(StrEnum):
    KITCHEN = "kitchen"
    STORE = "store"
    WAREHOUSE = "warehouse"
    PLANT = "plant"


class BatchState(StrEnum):
    WHOLE = "whole"
    CUT = "cut"
    PREPARED = "prepared"


class InventoryEventType(StrEnum):
    RECEIVE = "receive"
    MOVE = "move"
    CONSUME = "consume"
    ADJUST = "adjust"
    WASTE = "waste"
    TRANSFER = "transfer"
    MARKDOWN = "markdown"


class WasteReason(StrEnum):
    OVERPRODUCTION = "overproduction"
    PREP_TRIM = "prep_trim"
    SPOILAGE = "spoilage"
    PLATE_WASTE = "plate_waste"
    QUALITY_REJECTION = "quality_rejection"


class WasteStage(StrEnum):
    STORAGE = "storage"
    PREP = "prep"
    PRODUCTION = "production"
    SERVICE = "service"
    POST_SERVICE = "post_service"


class CaptureMethod(StrEnum):
    MANUAL = "manual"
    PHOTO = "photo"
    POS_DERIVED = "pos_derived"
    INFERRED = "inferred"


class Horizon(StrEnum):
    """The three intervention types. Not products — action spaces."""

    PREVENT = "PREVENT"
    PRESERVE = "PRESERVE"
    RECOVER = "RECOVER"


class ActionType(StrEnum):
    # PREVENT
    SET_PREP_QTY = "set_prep_qty"
    SET_ORDER_QTY = "set_order_qty"
    SET_PRODUCTION_QTY = "set_production_qty"
    # PRESERVE
    USE_FIRST = "use_first"
    RELOCATE = "relocate"
    TRANSFER = "transfer"
    MARKDOWN = "markdown"
    REPLAN_MENU = "replan_menu"
    # RECOVER
    STAFF_MEAL = "staff_meal"
    DEEP_MARKDOWN = "deep_markdown"
    B2B_TRANSFER = "b2b_transfer"
    DONATE = "donate"
    PROCESS = "process"
    ANIMAL_FEED = "animal_feed"
    COMPOST = "compost"
    DO_NOTHING = "do_nothing"

    # --- agri transit action space (v2 §4, H8-13) --------------------------
    # PREVENT: change the journey before it starts.
    DEPART_EARLIER = "depart_earlier"
    UPGRADE_TRANSPORT = "upgrade_transport"
    # PRESERVE: change where it goes or how it is broken up.
    REROUTE = "reroute"
    SPLIT_BATCH = "split_batch"
    # RECOVER: it will not survive the journey as planned.
    DIVERT_TO_CHANNEL = "divert_to_channel"



class ChannelType(StrEnum):
    INTERNAL_USE = "internal_use"
    STAFF_MEAL = "staff_meal"
    MARKDOWN = "markdown"
    B2B_TRANSFER = "b2b_transfer"
    DONATION = "donation"
    PROCESSING = "processing"
    ANIMAL_FEED = "animal_feed"
    COMPOST = "compost"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    OVERRIDDEN = "overridden"
    EXPIRED = "expired"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RescueOfferStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


# --------------------------------------------------------------------------
# AGRI BATCH — added at H2-3 per FoodOS-Team-Split-v2.md §4.
# Additive: nothing above this line changes. Values are the wire format from
# the Batch Profile in Contract 2 §2, so the API serialises them unchanged.
# --------------------------------------------------------------------------


class TransportMode(StrEnum):
    """Keys of D's content/transport_modes.yaml.

    Each carries a cooling_factor, vibration_penalty, cost_per_km and
    availability_hours in that file. The engine reads them from there — the
    numbers are never duplicated in Python.
    """

    OPEN_TRUCK = "open_truck"
    TARPAULIN = "tarpaulin"
    REEFER = "reefer"


class PackagingType(StrEnum):
    """Keys of D's content/packaging.yaml — thermal_retention_factor,
    crush_protection, cost_per_kg."""

    LOOSE = "loose"
    JUTE_SACK = "jute_sack"
    VENTILATED_PLASTIC_CRATE = "ventilated_plastic_crate"
    CFB_CARTON = "cfb_carton"


class MaturityStage(StrEnum):
    """How far through ripening the batch was at harvest.

    Low/medium/high rather than the horticultural ladder (mature-green,
    breaker, turning, ripe) because Contract 2 freezes `"maturity": "high"` on
    the wire, and a second vocabulary between the DB and the API is how a field
    ends up translated in two places and disagreeing in one of them.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(StrEnum):
    """The band on a LossRiskScore. Drives Screen 1's grouping and C's colour
    tokens (HIGH red / MEDIUM amber / LOW green, §5).

    Distinct from `Confidence`, which says how sure the model is. A batch can
    be HIGH risk with LOW confidence — that pairing is exactly what the band on
    Screen 3 exists to show, so the two must not be collapsed into one field.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# --------------------------------------------------------------------------
# BATCH IDENTITY — the digital passport.
#
# Additive again: nothing above this line changes. A `Consignment` already had
# a free-text `status`; these give it a controlled vocabulary, an event
# alphabet and a party vocabulary, which is what turns a scored row into an
# identity that survives a change of owner.
#
# Contract 2b froze four status values on the wire (registered | assessed |
# in_transit | delivered). Those are NOT deleted — `BatchLifecycle.contract_status`
# projects the richer ladder back down onto them, so C's Command Center keeps
# filtering on exactly what it filters on today while the passport gets the
# full state. One vocabulary in the database, two views of it on the wire, and
# the mapping lives here rather than in a route handler.
# --------------------------------------------------------------------------


class BatchLifecycle(StrEnum):
    """Where a batch is in its life. Ordered farm-gate to terminal.

    Not every batch visits every state — a consignment diverted mid-haul goes
    IN_TRANSIT -> DIVERTED without ever being RECEIVED, which is the whole
    point of the rescue path. Legal moves are declared in
    `engine/batch_identity.py::TRANSITIONS` rather than implied by this order,
    because "the next one down the list" is wrong for exactly the cases that
    matter.
    """

    # `"registered"` rather than `"created"`: Contract 2b froze that spelling,
    # `routes/batches.py` writes it on every new consignment, and
    # `ingest/consignments.py` seeds it. Giving this member its own spelling
    # would mean `BatchLifecycle(row.status)` raised ValueError on every batch
    # the Contract 2b endpoint created — the two layers share one column, so
    # they have to share one vocabulary.
    CREATED = "registered"
    ASSESSED = "assessed"
    READY_FOR_DISPATCH = "ready_for_dispatch"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    RECEIVED = "received"
    IN_INVENTORY = "in_inventory"
    # --- terminal ---------------------------------------------------------
    SOLD = "sold"
    PROCESSED = "processed"
    DONATED = "donated"
    DIVERTED = "diverted"
    WASTED = "wasted"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    @property
    def contract_status(self) -> str:
        """The Contract 2b value for this state. Never a new spelling."""
        return _CONTRACT_STATUS[self]


#: DIVERTED is deliberately NOT here. A diverted batch is a batch that is still
#: moving, just somewhere else — it has a fate ahead of it (processed, donated,
#: sold) that the ledger has to be able to record. Treating the diversion
#: itself as the ending would book every rescue as an outcome we never
#: confirmed, which is the one number in this product that has to be honest.
_TERMINAL: frozenset[BatchLifecycle] = frozenset(
    {
        BatchLifecycle.SOLD,
        BatchLifecycle.PROCESSED,
        BatchLifecycle.DONATED,
        BatchLifecycle.WASTED,
    }
)

#: The projection down onto Contract 2b's four frozen values. `delivered` is
#: the catch-all for everything at or past arrival, including the terminal
#: states, because to the Command Center they are all "off the road".
_CONTRACT_STATUS: dict[BatchLifecycle, str] = {
    BatchLifecycle.CREATED: "registered",
    BatchLifecycle.ASSESSED: "assessed",
    BatchLifecycle.READY_FOR_DISPATCH: "assessed",
    BatchLifecycle.IN_TRANSIT: "in_transit",
    BatchLifecycle.ARRIVED: "delivered",
    BatchLifecycle.RECEIVED: "delivered",
    BatchLifecycle.IN_INVENTORY: "delivered",
    BatchLifecycle.SOLD: "delivered",
    BatchLifecycle.PROCESSED: "delivered",
    BatchLifecycle.DONATED: "delivered",
    # Still on a truck, just aimed somewhere else.
    BatchLifecycle.DIVERTED: "in_transit",
    BatchLifecycle.WASTED: "delivered",
}


class BatchEventType(StrEnum):
    """The alphabet of the batch timeline.

    Deliberately separate from `InventoryEventType`, which is the kitchen's
    stock ledger (receive/consume/waste against a storage zone). These are
    journey events against a consignment in motion. Sharing one enum would mean
    `CONSUME` was legal on a truck and `HEAT_EXPOSURE` legal on a prep
    container, and neither is true.

    Events are append-only. Nothing in the system updates a batch without
    writing one, which is what makes the timeline a record rather than a
    rendering of the current row.
    """

    # --- origin -----------------------------------------------------------
    HARVEST = "harvest"
    FIELD_HOLD = "field_hold"
    PACKED = "packed"
    ASSESSED = "assessed"
    PHOTOS_ADDED = "photos_added"
    # --- journey ----------------------------------------------------------
    DISPATCHED = "dispatched"
    DELAY = "delay"
    TEMPERATURE_EXPOSURE = "temperature_exposure"
    ARRIVED = "arrived"
    # --- custody ----------------------------------------------------------
    HANDOFF = "handoff"
    RECEIVED = "received"
    SPLIT = "split"
    # --- outcome ----------------------------------------------------------
    DIVERTED = "diverted"
    SOLD = "sold"
    PROCESSED = "processed"
    DONATED = "donated"
    WASTED = "wasted"

    @property
    def rescores(self) -> bool:
        """Does this event change the physics, and so demand a re-score?

        A handoff does not: the same tomatoes at the same temperature in the
        same crates are the same tomatoes, and re-running the model on a change
        of owner would make the number move for a reason nobody can explain.
        A six-hour delay does. This property is why the two are told apart.
        """
        return self in _RESCORING


_RESCORING: frozenset[BatchEventType] = frozenset(
    {
        BatchEventType.FIELD_HOLD,
        BatchEventType.ASSESSED,
        BatchEventType.PHOTOS_ADDED,
        BatchEventType.DISPATCHED,
        BatchEventType.DELAY,
        BatchEventType.TEMPERATURE_EXPOSURE,
        BatchEventType.ARRIVED,
        BatchEventType.SPLIT,
        BatchEventType.DIVERTED,
    }
)


class PartyRole(StrEnum):
    """Who is holding the batch. The custody chain is a sequence of these."""

    FARMER = "farmer"
    FPO = "fpo"
    TRANSPORTER = "transporter"
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    PROCESSOR = "processor"
    DONATION_PARTNER = "donation_partner"
