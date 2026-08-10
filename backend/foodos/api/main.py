"""FastAPI application.

    uvicorn foodos.api.main:app --reload --port 8000

Interactive docs at /docs. During the demo those docs are the first contingency rung: if
the frontend will not load, every number on every screen is still readable from there.

Owner: Person B.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import get_config
from ..schema import Product, get_engine, session_scope
from .routers import router

DESCRIPTION = """
Decision infrastructure for perishable inventory.

One objective function, three action spaces:

    V(a) = recovery(a) − cost(a) − disposal(a) − λ · sustainability(a)

`lambda` is a query parameter on every endpoint whose answer depends on it, and every such
response echoes back the value actually used.
"""

app = FastAPI(
    title="FoodOS",
    version="0.1.0",
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url=None,
)

# The frontend is served from a different port in development. Locked to localhost —
# there is no reason for this to be reachable from anywhere else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Is the database seeded? The first thing to check when a screen comes back empty."""
    config = get_config()
    try:
        with session_scope() as session:
            dishes = session.query(Product).filter(Product.kind == "dish").count()
    except Exception as exc:
        return {
            "status": "unseeded",
            "detail": str(exc),
            "fix": "python -m foodos.ingest.seed",
        }

    return {
        "status": "ok" if dishes else "unseeded",
        "dishes": dishes,
        "demo_date": config.demo_date.isoformat(),
        "default_lambda": config.default_lambda,
        "fix": None if dishes else "python -m foodos.ingest.seed",
    }


@app.exception_handler(Exception)
async def unhandled(request, exc: Exception) -> JSONResponse:
    """Never return a stack trace to a screen mid-demo. Say what to do instead."""
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
            "hint": "If this is a fresh checkout, run: python -m foodos.ingest.seed",
        },
    )


@app.on_event("startup")
def warm_up() -> None:
    get_engine()
