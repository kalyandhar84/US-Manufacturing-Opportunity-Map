"""Refresh every MOI dataset into SQLite.

Usage:
    python refresh_data.py
    python refresh_data.py --seed-only
    python refresh_data.py --blend 0.6
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from src.db import (
    DB_PATH,
    ROOT,
    checkpoint_wal,
    connect,
    finish_refresh_run,
    insert_metrics,
    record_last_refresh_stamp,
    seed_company_layers,
    seed_from_registry,
    start_refresh_run,
    upsert_metros,
    utc_now,
)
from src.ingest_facilities import ingest_public_facilities
from src.metros import METROS

USER_AGENT = "ManufacturingOpportunityIndex/1.0 (data refresh)"
ACS_YEARS = (2024, 2023, 2022, 2021)
ACS_DATASETS = ("acs/acs1/profile", "acs/acs5/profile")
CENSUS_VARS = {
    "acs_population": "DP05_0001E",
    "unemployment_rate": "DP03_0005PE",
    "manufacturing_share": "DP03_0035PE",
    "transport_share": "DP03_0041PE",
    "bachelors_share": "DP02_0068PE",
}
_census_key_missing = False


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def log(message: str) -> None:
    print(message, flush=True)


def census_get(path: str, params: dict[str, str], timeout: int = 60) -> list[list[str]] | None:
    global _census_key_missing
    if _census_key_missing:
        return None
    query = dict(params)
    key = os.getenv("CENSUS_API_KEY")
    if key:
        query["key"] = key
    url = f"https://api.census.gov/data/{path}?{urllib.parse.urlencode(query, quote_via=urllib.parse.quote)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:180]
        log(f"  skip {path}: HTTP {exc.code} {body}")
        return None
    except (urllib.error.URLError, TimeoutError) as exc:
        log(f"  skip {path}: {exc}")
        return None
    if "<title>Missing Key</title>" in raw or "Missing Key" in raw[:400]:
        _census_key_missing = True
        log("  Census requires CENSUS_API_KEY — add it to .env (free: https://api.census.gov/data/key_signup.html)")
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        log(f"  skip {path}: non-JSON ({raw[:120]!r})")
        return None
    if not payload or len(payload) < 2:
        return None
    return payload


def parse_number(value: Any) -> float | None:
    if value in (None, "", "null", "None") or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number <= -1_000_000:
        return None
    return number


def fetch_acs_profile(year: int, dataset: str) -> pd.DataFrame | None:
    get = ",".join(["NAME", *CENSUS_VARS.values()])
    payload = census_get(
        f"{year}/{dataset}",
        {
            "get": get,
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
    )
    if not payload:
        return None
    header, *rows = payload
    frame = pd.DataFrame(rows, columns=header)
    frame = frame.rename(
        columns={
            header[-1]: "cbsa",
            **{code: name for name, code in CENSUS_VARS.items()},
        }
    )
    frame["cbsa"] = frame["cbsa"].astype(str).str.zfill(5)
    for col in CENSUS_VARS:
        frame[col] = frame[col].map(parse_number)
    frame["year"] = year
    return frame[["cbsa", "year", *CENSUS_VARS]]


def latest_acs() -> tuple[pd.DataFrame | None, int | None, str | None]:
    for year in ACS_YEARS:
        for dataset in ACS_DATASETS:
            log(f"Census {dataset} {year}…")
            frame = fetch_acs_profile(year, dataset)
            if frame is not None and not frame.empty:
                log(f"  {len(frame):,} metro/micro areas")
                return frame, year, dataset
    return None, None, None


def prior_acs_population(year: int, dataset: str) -> pd.DataFrame | None:
    prior = year - 5
    log(f"Census {dataset} {prior} population (5-year lookback)…")
    payload = census_get(
        f"{prior}/{dataset}",
        {
            "get": "NAME,DP05_0001E",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
    )
    if not payload:
        return None
    header, *rows = payload
    frame = pd.DataFrame(rows, columns=header)
    frame = frame.rename(columns={header[-1]: "cbsa", "DP05_0001E": "population_prior"})
    frame["cbsa"] = frame["cbsa"].astype(str).str.zfill(5)
    frame["population_prior"] = frame["population_prior"].map(parse_number)
    frame["prior_year"] = prior
    return frame[["cbsa", "population_prior", "prior_year"]]


def percentile_0_100(series: pd.Series, invert: bool = False) -> pd.Series:
    ranked = series.rank(pct=True, method="average") * 100
    if invert:
        ranked = 100 - ranked
    return ranked.clip(0, 100)


def blend(seed: float, live: float | None, weight: float) -> int:
    if live is None:
        value = seed
    else:
        value = weight * float(live) + (1.0 - weight) * float(seed)
    return int(max(0, min(100, round(value))))


def apply_live_scores(
    seed: pd.DataFrame,
    acs: pd.DataFrame,
    prior: pd.DataFrame | None,
    weight: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    seed = seed.copy()
    seed["cbsa"] = seed["cbsa"].astype(str).str.zfill(5)
    acs = acs.copy()
    acs["cbsa"] = acs["cbsa"].astype(str).str.zfill(5)
    panel = seed.merge(acs, on="cbsa", how="left")
    if prior is not None:
        panel = panel.merge(prior, on="cbsa", how="left")
    else:
        panel["population_prior"] = pd.NA
        panel["prior_year"] = pd.NA
    panel = panel.reset_index(drop=True)

    panel["pop_cagr"] = pd.NA
    has_both = panel["acs_population"].notna() & panel["population_prior"].gt(0)
    panel.loc[has_both, "pop_cagr"] = (
        panel.loc[has_both, "acs_population"] / panel.loc[has_both, "population_prior"]
    ) ** (1.0 / 5.0) - 1.0

    mfg_live = percentile_0_100(panel["manufacturing_share"])
    labor_live = 0.55 * percentile_0_100(panel["unemployment_rate"], invert=True) + 0.45 * percentile_0_100(
        panel["bachelors_share"]
    )
    warehouse_live = percentile_0_100(panel["transport_share"])
    growth_live = percentile_0_100(panel["pop_cagr"])

    records = []
    for i, row in panel.iterrows():
        metro = seed.loc[seed["cbsa"] == row["cbsa"]].iloc[0].to_dict()
        acs_pop = parse_number(row.get("acs_population"))
        if acs_pop is not None:
            metro["population"] = int(round(acs_pop))
        metro["manufacturing"] = blend(metro["manufacturing"], parse_number(mfg_live.iat[i]), weight)
        metro["labor"] = blend(metro["labor"], parse_number(labor_live.iat[i]), weight)
        metro["warehouse"] = blend(metro["warehouse"], parse_number(warehouse_live.iat[i]), weight)
        metro["growth"] = blend(metro["growth"], parse_number(growth_live.iat[i]), weight)
        records.append(metro)
    return pd.DataFrame(records), panel


def metrics_from_acs(panel: pd.DataFrame, year: int, fetched_at: str, source: str) -> list[dict[str, Any]]:
    records = []
    mapping = {
        "population": "acs_population",
        "unemployment_rate": "unemployment_rate",
        "manufacturing_share": "manufacturing_share",
        "transport_share": "transport_share",
        "bachelors_share": "bachelors_share",
        "pop_cagr": "pop_cagr",
    }
    for _, row in panel.iterrows():
        for metric, col in mapping.items():
            value = parse_number(row.get(col))
            if value is None:
                continue
            metric_year = int(row["prior_year"]) if metric == "pop_cagr" and pd.notna(row.get("prior_year")) else year
            records.append(
                {
                    "cbsa": row["cbsa"],
                    "metric": metric,
                    "year": metric_year,
                    "value": float(value),
                    "source": source,
                    "fetched_at": fetched_at,
                }
            )
    return records


def refresh(mode: str, blend_weight: float) -> dict[str, Any]:
    conn = connect()
    run_id = start_refresh_run(conn, mode)
    notes: list[str] = []
    metros_updated = 0
    status = "ok"
    fetched_at = utc_now()

    try:
        log(f"SQLite: {DB_PATH}")
        seeded = seed_from_registry(conn, force=(mode == "seed"))
        notes.append(f"restored {len(METROS)} seed metros" if mode == "seed" else f"ensured registry ({seeded} inserted)")

        if mode == "seed":
            metros_updated = upsert_metros(conn, METROS, fetched_at)
            layers = seed_company_layers(conn, force=True)
            notes.append("pillars restored from curated seed")
            notes.append(
                f"wave3 layers: {layers['companies']} companies, {layers['news']} news, "
                f"{layers['projects']} capex projects"
            )
        else:
            acs, year, dataset = latest_acs()
            if acs is None:
                metros_updated = upsert_metros(conn, METROS, fetched_at)
                layers = seed_company_layers(conn, force=True)
                notes.append("Census ACS unavailable; stored seed panel")
                notes.append(f"wave3 layers: {layers['companies']} companies")
                status = "partial"
            else:
                prior = prior_acs_population(year, dataset)
                scored, panel = apply_live_scores(pd.DataFrame(METROS), acs, prior, blend_weight)
                metros_updated = upsert_metros(conn, scored.to_dict(orient="records"), fetched_at)
                inserted = insert_metrics(conn, metrics_from_acs(panel, year, fetched_at, dataset.replace("/", "_")))
                layers = seed_company_layers(conn, force=True)
                notes.append(f"{dataset} {year}; {inserted} metric rows; blend={blend_weight:.2f}")
                notes.append(f"wave3 layers: {layers['companies']} companies, {layers['news']} headlines")
                if prior is None:
                    notes.append("5-year population lookback missing; growth stayed closer to seed")
                    status = "partial"

        log("Public facility directories (EPA TRI + USDA FSIS + OSHA ITA)…")
        facilities = ingest_public_facilities(conn, force=True)
        notes.append(
            "named plants "
            f"{facilities.get('facilities', 0):,} "
            f"auto={facilities.get('n_automotive', 0)} "
            f"food={facilities.get('n_food_manufacturing', 0)} "
            f"semi={facilities.get('n_semiconductors', 0)} "
            f"battery={facilities.get('n_battery_manufacturing', 0)} "
            f"warehouse={facilities.get('n_warehousing', 0)} "
            f"dc={facilities.get('n_distribution_centers', 0)} "
            f"mh={facilities.get('n_materials_handling', 0)}"
        )

        finish_refresh_run(conn, run_id, status, metros_updated, "; ".join(notes))
        if status in ("ok", "partial"):
            record_last_refresh_stamp()
        return {
            "status": status,
            "metros_updated": metros_updated,
            "notes": notes,
            "db": str(DB_PATH),
        }
    except Exception as exc:
        finish_refresh_run(conn, run_id, "error", metros_updated, str(exc))
        raise
    finally:
        try:
            checkpoint_wal(conn)
        except Exception:
            pass
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Manufacturing Opportunity Index data into SQLite.")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Write the curated metro panel into SQLite and skip public APIs.",
    )
    parser.add_argument(
        "--blend",
        type=float,
        default=0.55,
        help="Weight on live Census percentiles vs curated seed (0-1). Default 0.55.",
    )
    return parser.parse_args()


def main() -> int:
    load_env()
    args = parse_args()
    if not 0 <= args.blend <= 1:
        log("--blend must be between 0 and 1")
        return 2
    mode = "seed" if args.seed_only else "census"
    result = refresh(mode, args.blend)
    log("")
    log(f"Status:   {result['status']}")
    log(f"Metros:   {result['metros_updated']}")
    log(f"Database: {result['db']}")
    for note in result["notes"]:
        log(f"  - {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
