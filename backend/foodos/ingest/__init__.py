"""Ingestion: CSV in, canonical schema out."""

from foodos.ingest import (
    channels,
    loader,
    mapping,
    profiles,
    sample_data,
    shelf_life,
    validation,
)

__all__ = [
    "channels",
    "loader",
    "mapping",
    "profiles",
    "sample_data",
    "shelf_life",
    "validation",
]
