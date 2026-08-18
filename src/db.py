"""SQLite storage for the Manufacturing Opportunity Index."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "moi.sqlite"

PILLAR_COLS = ("manufacturing", "logistics", "labor", "warehouse", "growth")
CLUSTER_COLS = (
    "automotive",
    "warehousing",
    "food_manufacturing",
    "battery_manufacturing",
    "semiconductors",
    "distribution_centers",
    "materials_handling",
)
IDENTITY_COLS = (
    "cbsa",
    "short",
    "name",
    "state",
    "region",
    "lat",
    "lon",
    "population",
    "tagline",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS metros (
    cbsa TEXT PRIMARY KEY,
    short TEXT NOT NULL,
    name TEXT NOT NULL,
    state TEXT NOT NULL,
    region TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    population INTEGER,
    tagline TEXT,
    highlights_json TEXT NOT NULL DEFAULT '[]',
    manufacturing REAL,
    logistics REAL,
    labor REAL,
    warehouse REAL,
    growth REAL,
    automotive REAL,
    warehousing REAL,
    food_manufacturing REAL,
    battery_manufacturing REAL,
    semiconductors REAL,
    distribution_centers REAL,
    materials_handling REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    cbsa TEXT NOT NULL,
    metric TEXT NOT NULL,
    year INTEGER,
    value REAL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (cbsa, metric, year, source)
);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    metros_updated INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    industry TEXT NOT NULL,
    cbsa TEXT,
    metro TEXT NOT NULL,
    city TEXT,
    segment TEXT,
    site TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    source TEXT,
    naics TEXT,
    parent TEXT,
    state TEXT,
    address TEXT,
    employees INTEGER,
    size_class TEXT,
    website TEXT
);

CREATE TABLE IF NOT EXISTS company_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL,
    published_on TEXT NOT NULL,
    headline TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    url TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS announced_projects (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    metro TEXT NOT NULL,
    industry TEXT NOT NULL,
    year INTEGER,
    capex_b REAL,
    jobs INTEGER,
    status TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS industrial_market (
    cbsa TEXT PRIMARY KEY,
    metro TEXT NOT NULL,
    vacancy_pct REAL,
    rent_index REAL,
    as_of TEXT,
    source TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(path: Path | None = None) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    _ensure_metro_columns(conn)
    _ensure_company_columns(conn)
    return conn


def _ensure_metro_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(metros)").fetchall()}
    for col in CLUSTER_COLS:
        if col not in existing:
            conn.execute(f"ALTER TABLE metros ADD COLUMN {col} REAL")
    conn.commit()


def _ensure_company_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(companies)").fetchall()}
    for col, typ in (
        ("source", "TEXT"),
        ("naics", "TEXT"),
        ("parent", "TEXT"),
        ("state", "TEXT"),
        ("address", "TEXT"),
        ("employees", "INTEGER"),
        ("size_class", "TEXT"),
        ("website", "TEXT"),
    ):
        if col not in existing:
            conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {typ}")
    conn.commit()
    _backfill_company_websites(conn)


def _backfill_company_websites(conn: sqlite3.Connection) -> None:
    missing = conn.execute(
        "SELECT COUNT(*) FROM companies WHERE website IS NULL OR trim(website) = ''"
    ).fetchone()[0]
    if not missing:
        return
    from .companies import COMPANIES, resolve_website

    by_id = {c["id"]: c.get("website") for c in COMPANIES if c.get("website")}
    rows = conn.execute(
        """
        SELECT id, name, parent, city, state
        FROM companies
        WHERE website IS NULL OR trim(website) = ''
        """
    ).fetchall()
    updates = []
    for row in rows:
        site = by_id.get(row["id"]) or resolve_website(
            row["name"] or "",
            row["parent"] or "",
            row["city"] or "",
            row["state"] or "",
        )
        updates.append((site, row["id"]))
    if updates:
        conn.executemany("UPDATE companies SET website = ? WHERE id = ?", updates)
        conn.commit()


def _row_from_seed(metro: dict[str, Any], updated_at: str) -> dict[str, Any]:
    return {
        **{col: metro[col] for col in IDENTITY_COLS},
        "highlights_json": json.dumps(list(metro.get("highlights") or []), ensure_ascii=False),
        **{col: metro[col] for col in PILLAR_COLS},
        **{col: metro[col] for col in CLUSTER_COLS},
        "updated_at": updated_at,
    }


def upsert_metros(conn: sqlite3.Connection, metros: list[dict[str, Any]], updated_at: str | None = None) -> int:
    stamp = updated_at or utc_now()
    rows = [_row_from_seed(metro, stamp) for metro in metros]
    cols = list(rows[0].keys())
    placeholders = ", ".join(f":{c}" for c in cols)
    assignments = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "cbsa")
    sql = f"""
        INSERT INTO metros ({", ".join(cols)})
        VALUES ({placeholders})
        ON CONFLICT(cbsa) DO UPDATE SET {assignments}
    """
    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


def seed_from_registry(conn: sqlite3.Connection, force: bool = False) -> int:
    from .metros import METROS

    count = conn.execute("SELECT COUNT(*) FROM metros").fetchone()[0]
    if count and not force:
        seed_company_layers(conn, force=False)
        return 0
    upsert_metros(conn, METROS)
    seed_company_layers(conn, force=True)
    return len(METROS)


def insert_metrics(conn: sqlite3.Connection, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    conn.executemany(
        """
        INSERT OR REPLACE INTO metrics (cbsa, metric, year, value, source, fetched_at)
        VALUES (:cbsa, :metric, :year, :value, :source, :fetched_at)
        """,
        records,
    )
    conn.commit()
    return len(records)


def start_refresh_run(conn: sqlite3.Connection, mode: str) -> int:
    cur = conn.execute(
        "INSERT INTO refresh_runs (started_at, status, mode) VALUES (?, 'running', ?)",
        (utc_now(), mode),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_refresh_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    metros_updated: int,
    notes: str,
) -> None:
    conn.execute(
        """
        UPDATE refresh_runs
        SET finished_at = ?, status = ?, metros_updated = ?, notes = ?
        WHERE id = ?
        """,
        (utc_now(), status, metros_updated, notes, run_id),
    )
    conn.commit()


def latest_refresh(conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            """
            SELECT id, started_at, finished_at, status, mode, metros_updated, notes
            FROM refresh_runs
            WHERE status != 'running'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def metro_count(conn: sqlite3.Connection | None = None) -> int:
    own = conn is None
    conn = conn or connect()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM metros").fetchone()[0])
    finally:
        if own:
            conn.close()


def load_metros_frame(auto_seed: bool = True) -> pd.DataFrame:
    conn = connect()
    try:
        if auto_seed:
            seed_from_registry(conn)
        rows = conn.execute("SELECT * FROM metros ORDER BY short").fetchall()
    finally:
        conn.close()

    records = []
    for row in rows:
        item = dict(row)
        item["highlights"] = json.loads(item.pop("highlights_json") or "[]")
        item.pop("updated_at", None)
        records.append(item)
    return pd.DataFrame(records)


def _jitter(lat: float, lon: float, key: str, amplitude: float = 0.22) -> tuple[float, float]:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    dlat = (int(digest[:8], 16) / 0xFFFFFFFF - 0.5) * amplitude
    dlon = (int(digest[8:16], 16) / 0xFFFFFFFF - 0.5) * amplitude
    return lat + dlat, lon + dlon


def seed_company_layers(conn: sqlite3.Connection, force: bool = False) -> dict[str, int]:
    from .companies import COMPANIES, NEWS, PROJECTS, VACANCY_TILT
    from .metros import METROS

    existing = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    if existing and not force:
        return {"companies": 0, "news": 0, "projects": 0, "market": 0, "timeseries": 0}

    metro_by_short = {m["short"]: m for m in METROS}
    company_rows = []
    for company in COMPANIES:
        metro = metro_by_short.get(company["metro"])
        if not metro:
            continue
        if company.get("lat") is not None and company.get("lon") is not None:
            lat, lon = float(company["lat"]), float(company["lon"])
        else:
            lat, lon = _jitter(metro["lat"], metro["lon"], company["id"])
        company_rows.append(
            {
                "id": company["id"],
                "name": company["name"],
                "industry": company["industry"],
                "cbsa": metro["cbsa"],
                "metro": company["metro"],
                "city": company["city"],
                "segment": company["segment"],
                "site": company["site"],
                "lat": lat,
                "lon": lon,
                "source": "curated",
                "naics": "",
                "parent": company["name"],
                "state": metro["state"],
                "address": company["city"],
                "employees": company.get("employees"),
                "size_class": company.get("size_class") or "Unknown",
                "website": company.get("website") or "",
            }
        )

    conn.execute("DELETE FROM company_news")
    conn.execute("DELETE FROM companies")
    conn.execute("DELETE FROM announced_projects")
    conn.execute("DELETE FROM industrial_market")
    conn.executemany(
        """
        INSERT INTO companies
        (id, name, industry, cbsa, metro, city, segment, site, lat, lon, source, naics, parent, state, address, employees, size_class, website)
        VALUES
        (:id, :name, :industry, :cbsa, :metro, :city, :segment, :site, :lat, :lon, :source, :naics, :parent, :state, :address, :employees, :size_class, :website)
        """,
        company_rows,
    )
    known_ids = {row["id"] for row in company_rows}
    news_rows = [item for item in NEWS if item["company_id"] in known_ids]
    conn.executemany(
        """
        INSERT INTO company_news (company_id, published_on, headline, summary, source, url)
        VALUES (:company_id, :date, :headline, :summary, :source, :url)
        """,
        news_rows,
    )
    conn.executemany(
        """
        INSERT INTO announced_projects (id, company, metro, industry, year, capex_b, jobs, status, notes)
        VALUES (:id, :company, :metro, :industry, :year, :capex_b, :jobs, :status, :notes)
        """,
        PROJECTS,
    )

    market_rows = []
    for metro in METROS:
        vacancy = VACANCY_TILT.get(metro["short"], 7.3)
        rent_index = round(40 + metro["warehouse"] * 0.45 + (10 - vacancy), 1)
        market_rows.append(
            {
                "cbsa": metro["cbsa"],
                "metro": metro["short"],
                "vacancy_pct": vacancy,
                "rent_index": rent_index,
                "as_of": "2026-Q2",
                "source": "Model tilt on Colliers Q2 2026 national 7.3% vacancy — not licensed submarket data",
            }
        )
    conn.executemany(
        """
        INSERT INTO industrial_market (cbsa, metro, vacancy_pct, rent_index, as_of, source)
        VALUES (:cbsa, :metro, :vacancy_pct, :rent_index, :as_of, :source)
        """,
        market_rows,
    )

    fetched = utc_now()
    series_rows = []
    for metro in METROS:
        equal = sum(metro[col] for col in PILLAR_COLS) / len(PILLAR_COLS)
        for year, drift in zip(range(2021, 2027), (-4.2, -2.8, -1.1, 0.4, 1.2, 1.8)):
            series_rows.append(
                {
                    "cbsa": metro["cbsa"],
                    "metric": "equal_weight_moi",
                    "year": year,
                    "value": max(40.0, min(100.0, round(equal + drift, 1))),
                    "source": "wave3_backcast",
                    "fetched_at": fetched,
                }
            )
    conn.executemany(
        """
        INSERT OR REPLACE INTO metrics (cbsa, metric, year, value, source, fetched_at)
        VALUES (:cbsa, :metric, :year, :value, :source, :fetched_at)
        """,
        series_rows,
    )
    conn.commit()
    return {
        "companies": len(company_rows),
        "news": len(news_rows),
        "projects": len(PROJECTS),
        "market": len(market_rows),
        "timeseries": len(series_rows),
    }


def load_companies_frame() -> pd.DataFrame:
    conn = connect()
    try:
        seed_from_registry(conn)
        rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()


def load_company_news(company_id: str | None = None) -> pd.DataFrame:
    conn = connect()
    try:
        if company_id:
            rows = conn.execute(
                """
                SELECT n.*, c.name AS company_name, c.metro, c.industry
                FROM company_news n
                JOIN companies c ON c.id = n.company_id
                WHERE n.company_id = ?
                ORDER BY n.published_on DESC
                """,
                (company_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT n.*, c.name AS company_name, c.metro, c.industry
                FROM company_news n
                JOIN companies c ON c.id = n.company_id
                ORDER BY n.published_on DESC
                """
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()


def load_projects_frame() -> pd.DataFrame:
    conn = connect()
    try:
        seed_from_registry(conn)
        rows = conn.execute("SELECT * FROM announced_projects ORDER BY capex_b DESC").fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()


def load_industrial_market() -> pd.DataFrame:
    conn = connect()
    try:
        seed_from_registry(conn)
        rows = conn.execute("SELECT * FROM industrial_market").fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()


def load_metro_timeseries(cbsa: str) -> pd.DataFrame:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT year, value
            FROM metrics
            WHERE cbsa = ? AND metric = 'equal_weight_moi'
            ORDER BY year
            """,
            (cbsa,),
        ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])
    finally:
        conn.close()
