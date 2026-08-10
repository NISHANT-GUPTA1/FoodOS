"""`python -m foodos.ingest.seed`

The sacred command. Rebuilds the entire demo database from scratch in one step,
and runs fifty times before the demo. If the demo ever depends on a database
somebody hand-edited, it will not survive a laptop restart.

Data is taken from the first source that exists:

    1. backend/data/            A's freshly generated CSVs
    2. backend/data/sample/     the committed sample, so a clone works
    3. built-in fixture         B's own, so B is never blocked on A

    python -m foodos.ingest.seed
    python -m foodos.ingest.seed --source sample
    python -m foodos.ingest.seed --source fixture
    python -m foodos.ingest.seed --quiet
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

from sqlalchemy import select

from foodos.config import settings
from foodos.db import create_all, drop_all, session_scope
from foodos.engine.context import default_context
from foodos.engine.recommendation import generate
from foodos.external import agmarknet
from foodos.ingest import channels, consignments, loader, sample_data
from foodos.schema.tables import Organization, Site


def _resolve_source(requested: str) -> tuple[str, object]:
    if requested == "fixture":
        return "fixture", None
    if requested == "sample":
        return "csv", settings.sample_dir
    if requested == "generated":
        return "csv", settings.data_dir
    # auto
    if loader.has_data(settings.data_dir):
        return "csv", settings.data_dir
    if loader.has_data(settings.sample_dir):
        return "csv", settings.sample_dir
    return "fixture", None


def run(source: str = "auto", quiet: bool = False) -> dict:
    today = settings.demo_today
    kind, path = _resolve_source(source)

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    drop_all()
    create_all()

    with session_scope() as session:
        if kind == "csv":
            summary = loader.load_all(session, path, today)
            summary["source"] = f"csv:{path}"
        else:
            summary = sample_data.build(session, today)
            summary["source"] = "built-in fixture (B)"

        org = session.scalars(select(Organization).limit(1)).first()
        count, channel_source = channels.load(session, org.id)
        summary["channels"] = {"count": count, "source": channel_source}

        # Agri consignments (v2 §4, H3-8). One command builds both the
        # kitchen demo and the batch demo; this line is why.
        summary["consignments"] = consignments.load(session, org.id)

        # Mandi prices describe the market, not this customer, so they load
        # from whichever directory has the file regardless of --source.
        for candidate in (settings.data_dir, settings.sample_dir):
            market = agmarknet.load(session, candidate)
            if market["loaded"]:
                break
        summary["market_prices"] = market

        generated = {}
        for site_id in session.scalars(select(Site.id).order_by(Site.id)):
            ctx = default_context(site_id, today)
            rows = generate(session, ctx, target=today + timedelta(days=1))
            if rows:
                generated[site_id] = len(rows)

        summary["today"] = today.isoformat()
        summary["recommendations_generated"] = generated

    if not quiet:
        print(json.dumps(summary, indent=2, default=str))
        print(
            "\nDatabase rebuilt at "
            f"{settings.database_url}\nStart the API with:\n"
            "  uvicorn foodos.api.app:app --reload --port 8000",
            file=sys.stderr,
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the FoodOS demo database.")
    parser.add_argument(
        "--source",
        choices=("auto", "generated", "sample", "fixture"),
        default="auto",
        help="auto: A's generated CSVs, else the committed sample, else B's fixture",
    )
    parser.add_argument(
        "--force-sample",
        action="store_true",
        help="deprecated alias for --source fixture",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(source="fixture" if args.force_sample else args.source, quiet=args.quiet)


if __name__ == "__main__":
    main()
