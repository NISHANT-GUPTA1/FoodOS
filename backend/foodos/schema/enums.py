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
