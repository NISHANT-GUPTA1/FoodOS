"""Rebuild the entire demo database in one command.

    python -m foodos.ingest.seed

This command is sacred. It runs fifty times before the demo, from a clean checkout, with
no manual steps, and it must always work. Every other convenience in this repo can rot;
this one cannot.

What it does, in order:

    1. drop and recreate every table
    2. load the YAML content pack into the reference tables
    3. generate the synthetic CSVs if they are not already there
    4. load the CSVs, with column mapping and strict validation
    5. fit the forecaster and persist both the demo-day quantiles and the backtest
    6. score every open batch for shelf-life risk
    7. build and store the recommendations at the default λ

Steps 5 to 7 are here rather than in the API because a demo must not spend its first
fourteen seconds training LightGBM while a judge watches a spinner.

Owner: Person B.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

from ..config import CSV_FILES, get_config
from ..engine.recommendation import persist
from ..engine.service import FoodosService, ServiceContext
from ..models.backtest import run_backtest_holdout
from ..models.forecaster import Forecaster, build_features, build_next_day_row
from ..schema import (
    DemandContext,
    Forecast,
    Product,
    RiskScore,
    SalesRecord,
    create_all,
    drop_all,
    reset_engine,
    session_scope,
)
from .content import exclusion_reasons, labour_cost, load_content, prices_from_pack
from .csv_loader import load_all


def _make_console_utf8_safe() -> None:
    """Windows consoles default to cp1252, which cannot encode λ, °C or ₹.

    This command is run fifty times before the demo and must never fail. Dying on a
    progress message would be an absurd way to lose an hour, so the streams are widened
    once at import and every write is defensive besides.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):  # pragma: no cover - platform dependent
            pass


_make_console_utf8_safe()


def _say(message: str, quiet: bool = False) -> None:
    if quiet:
        return
    try:
        print(message, flush=True)
    except UnicodeEncodeError:  # pragma: no cover - only on a hostile console
        print(message.encode("ascii", "replace").decode("ascii"), flush=True)


def ensure_csvs(data_dir: Path, *, regenerate: bool, quiet: bool) -> None:
    missing = [name for name in CSV_FILES if not (data_dir / name).exists()]
    if not missing and not regenerate:
        _say(f"  csv       reusing {len(CSV_FILES)} existing files", quiet)
        return

    from ..data.generator import generate

    if missing and not regenerate:
        _say(f"  csv       {len(missing)} missing, generating", quiet)
    generate(out_dir=data_dir, quiet=True)
    _say(f"  csv       generated {len(CSV_FILES)} files", quiet)


def _frames(session):
    sales = pd.read_sql(
        select(SalesRecord.date, SalesRecord.dish_id, SalesRecord.qty_portions),
        session.connection(),
    )
    context = pd.read_sql(
        select(
            DemandContext.date, DemandContext.dow, DemandContext.is_weekend,
            DemandContext.is_holiday, DemandContext.rain_mm, DemandContext.temp_c,
            DemandContext.promo, DemandContext.local_event,
        ),
        session.connection(),
    )
    for frame in (sales, context):
        frame["date"] = pd.to_datetime(frame["date"])
    for column in ("is_weekend", "is_holiday", "promo", "local_event"):
        context[column] = context[column].astype(int)
    return sales, context


def fit_and_store_forecasts(session, config, *, quiet: bool) -> int:
    """Backtest first, then the live forecast. Both are persisted; neither is recomputed."""
    sales, context = _frames(session)
    if sales.empty:
        raise RuntimeError("no sales history — cannot fit a forecaster")

    started = time.perf_counter()

    # --- held-out backtest ---------------------------------------------------
    result, medians = run_backtest_holdout(
        sales, context, held_out_days=config.backtest_days, quantiles=config.forecast_quantiles
    )
    stored = 0
    for row in medians.itertuples():
        session.add(
            Forecast(
                date=row.date.date(),
                dish_id=row.dish_id,
                quantile=0.5,
                value=round(float(row.forecast_median), 2),
                is_backtest=True,
            )
        )
        stored += 1
    _say(
        f"  backtest  {config.backtest_days} held-out days, MAE {result.mae} "
        f"vs baseline {result.baseline_mae} ({result.improvement_pct:+.1f}%)",
        quiet,
    )

    # --- the live forecast for the demo date ---------------------------------
    frame = build_features(sales, context)
    forecaster = Forecaster(quantiles=config.forecast_quantiles).fit(frame)

    context_row = context[context["date"] == pd.Timestamp(config.demo_date)]
    context_row = context_row.iloc[0] if not context_row.empty else pd.Series(dtype=float)

    rows = [
        build_next_day_row(
            dish_id,
            forecaster.dish_codes.get(dish_id, 0),
            config.demo_date,
            frame,
            context_row,
        )
        for dish_id in sorted(frame["dish_id"].unique())
    ]
    grid = forecaster.predict_grid(pd.DataFrame(rows))

    for row in grid.itertuples():
        session.add(
            Forecast(
                date=config.demo_date,
                dish_id=row.dish_id,
                quantile=float(row.quantile),
                value=round(float(row.value), 2),
                is_backtest=False,
            )
        )
        stored += 1

    session.flush()
    _say(
        f"  forecast  {len(config.forecast_quantiles)} quantiles x {len(rows)} dishes "
        f"in {time.perf_counter() - started:.1f}s",
        quiet,
    )
    return stored


def score_batches(session, service: FoodosService, *, quiet: bool) -> int:
    stored = 0
    for batch in service.open_batches:
        assessment = service.batch_risk(batch)
        session.add(
            RiskScore(
                date=service.date,
                batch_id=batch.id,
                rsl_days=round(assessment.rsl_days, 3),
                risk_pct=round(assessment.risk_pct, 2),
                value_at_risk_inr=round(assessment.value_at_risk_inr, 2),
                co2e_at_risk_kg=round(assessment.co2e_at_risk_kg, 3),
            )
        )
        stored += 1
    session.flush()
    _say(f"  risk      {stored} open batches scored", quiet)
    return stored


def seed(
    *,
    data_dir: Path | None = None,
    regenerate: bool = False,
    quiet: bool = False,
    skip_models: bool = False,
) -> dict[str, int]:
    config = get_config()
    data_dir = data_dir or config.data_dir
    started = time.perf_counter()
    summary: dict[str, int] = {}

    _say(f"seeding {config.db_url}", quiet)
    _say(f"  demo date {config.demo_date} ({config.demo_date.strftime('%A')})", quiet)

    reset_engine()
    drop_all()
    create_all()
    _say("  schema    dropped and recreated", quiet)

    ensure_csvs(data_dir, regenerate=regenerate, quiet=quiet)

    with session_scope() as session:
        counts = load_content(session)
        summary.update(counts)
        _say(
            f"  content   {counts['ingredient']} ingredients, {counts['dish']} dishes, "
            f"{counts['recipe_line']} recipe lines, {counts['channel']} channels",
            quiet,
        )

        report = load_all(session, data_dir)
        summary["csv_rows"] = report.total()
        _say(f"  csv       {report.total():,} rows loaded", quiet)
        if report.skipped:
            _say(f"  csv       SKIPPED {', '.join(report.skipped)}", quiet)

        if not skip_models:
            summary["forecast"] = fit_and_store_forecasts(session, config, quiet=quiet)

    if not skip_models:
        with session_scope() as session:
            context = ServiceContext(
                prices=prices_from_pack(),
                labour_cost=labour_cost(),
                exclusion_reasons=exclusion_reasons(),
            )
            service = FoodosService(session, context, config)
            summary["risk_score"] = score_batches(session, service, quiet=quiet)

            recommendations = service.build_recommendations(config.default_lambda)
            persist(session, recommendations)
            summary["recommendation"] = len(recommendations)
            _say(
                f"  actions   {len(recommendations)} recommendations at λ={config.default_lambda:g}",
                quiet,
            )

    _say(f"done in {time.perf_counter() - started:.1f}s", quiet)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="foodos.ingest.seed", description="Rebuild the demo database from scratch."
    )
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--regenerate", action="store_true", help="rewrite the CSVs first")
    parser.add_argument("--skip-models", action="store_true", help="schema and data only, no LightGBM")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    try:
        seed(
            data_dir=Path(args.data_dir) if args.data_dir else None,
            regenerate=args.regenerate,
            quiet=args.quiet,
            skip_models=args.skip_models,
        )
    except Exception as exc:
        print(f"\nSEED FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
