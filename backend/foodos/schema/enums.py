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
