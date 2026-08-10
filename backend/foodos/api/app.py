"""FastAPI application.

    uvicorn foodos.api.app:app --reload --port 8000

Eleven screen endpoints plus health and ingest. Every response comes from the
engine; nothing is computed in a route handler.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from foodos import __version__
from foodos.api.routes import decisions, screens, system, tracks

DESCRIPTION = """
**FoodOS** — predict which food will become waste, explain why, and recommend
the highest-value action while there is still time to take it.

One objective function (`engine.optimiser.score`), three action spaces
(PREVENT, PRESERVE, RECOVER), three customer tracks.

Every number in these responses comes from the optimiser. The language model
never computes one.
"""

app = FastAPI(
    title="FoodOS Engine & API",
    version=__version__,
    description=DESCRIPTION,
)

# The frontend is served from a different origin during the hackathon.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(screens.router)
app.include_router(decisions.router)
app.include_router(tracks.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": "FoodOS Engine & API",
        "version": __version__,
        "docs": "/docs",
        "seed": "python -m foodos.ingest.seed",
    }
