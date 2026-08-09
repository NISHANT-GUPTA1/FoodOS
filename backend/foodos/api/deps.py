"""FastAPI dependencies.

The service context is built once at import — reading five YAML files on every request
would be a silly way to spend a demo's latency budget.

Owner: Person B.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from ..config import Config, get_config
from ..engine.service import FoodosService, ServiceContext
from ..ingest.content import exclusion_reasons, labour_cost, prices_from_pack
from ..schema import get_session


@lru_cache(maxsize=1)
def get_context() -> ServiceContext:
    return ServiceContext(
        prices=prices_from_pack(),
        labour_cost=labour_cost(),
        exclusion_reasons=exclusion_reasons(),
    )


def db() -> Iterator[Session]:
    yield from get_session()


def service(session: Session = Depends(db)) -> FoodosService:
    return FoodosService(session, get_context(), get_config())


def lambda_param(
    lambda_: float | None = Query(
        None,
        alias="lambda",
        ge=0.0,
        le=1.0,
        description="Sustainability weight, 0 to 1. Omitted means the configured default.",
    ),
) -> float:
    """Clamped in exactly one place, and echoed back by every response that uses it."""
    return get_config().clamp_lambda(lambda_)


def config() -> Config:
    return get_config()
