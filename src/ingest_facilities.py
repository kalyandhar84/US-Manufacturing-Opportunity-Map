"""Download and ingest named US plants from public federal files.

Sources
-------
EPA Toxics Release Inventory (TRI) Basic Data — national CSV, reporting year 2024
  https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/2024_US/csv
  Facility name, lat/lon, parent company, primary NAICS.

USDA FSIS Meat, Poultry and Egg Product Inspection Directory — MPI API
  https://www.fsis.usda.gov/fsis/api/establishments/mpi
  Federally inspected food plants with geolocation (updated weekly).

OSHA Injury Tracking Application (ITA) Form 300A summary — CY 2025
  https://www.osha.gov/itadata
  Named establishments with NAICS and address (warehouses, plants, DCs).
  Mapped with Census ZCTA centroids (not rooftop geocodes).

Census ZCTA gazetteer
  https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip

NAICS → MOI industry
  3361/3362/3363  automotive
  311 / 3121      food and beverage manufacturing (plus all FSIS establishments)
  3344            semiconductors
  33591           battery manufacturing (+ battery/gigafactory/OEM name match)
  33392           materials handling / forklifts (333922 conveyors, 333923 cranes,
                  333924 industrial trucks) plus MH OEM name match on NAICS 33*
  493             warehousing and distribution centers
                  (+ fulfillment / distribution / sortation name match)
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .companies import resolve_website
from .db import DATA_DIR
from .metros import METROS

USER_AGENT = "ManufacturingOpportunityIndex/1.0 (facility ingest)"
RAW_DIR = DATA_DIR / "raw"

TRI_URLS = [
    "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/2024_US/csv",
    "https://data.epa.gov/efservice/downloads/tri/mv_tri_basic_download/2023_US/csv",
]
FSIS_URL = "https://www.fsis.usda.gov/fsis/api/establishments/mpi"
ITA_URL = "https://www.osha.gov/sites/default/files/ITA_300A_Summary_Data_2025_through_03-15-2026_v2.csv"
ITA_2024_URL = "https://www.osha.gov/sites/default/files/ITA_300A_Summary_Data_2024_through_12-31-2025.zip"
ZCTA_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip"

PUBLIC_SOURCES = ("epa_tri", "usda_fsis", "osha_ita")

TRI_COLUMNS = {
    "2. TRIFD": "trifd",
    "4. FACILITY NAME": "name",
    "5. STREET ADDRESS": "street",
    "6. CITY": "city",
    "8. ST": "state",
    "12. LATITUDE": "lat",
    "13. LONGITUDE": "lon",
    "15. PARENT CO NAME": "parent",
    "30. PRIMARY NAICS": "naics",
}

BATTERY_PHRASE_RE = re.compile(
    r"GIGAFACTORY|MEGAFACTORY|LITHIUM[-\s]?ION|ULTIUM|CELL MANUFACT|"
    r"BATTERY MANUFACT|BATTERY PLANT|BATTERY PACK|EV BATTERY|EV CELL|"
    r"STORAGE BATTERY|PRIMARY BATTERY|CATHODE|ANODE MATERIAL",
    re.I,
)
BATTERY_OEM_RE = re.compile(
    r"\b("
    r"PANASONIC ENERGY|SK ON|SK BATTERY|LG ENERGY|SAMSUNG SDI|"
    r"ENVISION AESC|AESC|FREYR|QUANTUMSCAPE|SOLID POWER|MICROVAST|"
    r"AMPRIUS|GROUP14|REDWOOD MATERIALS?|LI-?CYCLE|ASCEND ELEMENTS?|"
    r"CIRBA|AMERICAN BATTERY|IM3NY|FACTORIAL|A123|SAFT|ENERSYS|"
    r"CLARIOS|EAST PENN|EXIDE|CATL|BYD|SVOLT|FARASIS|"
    r"OUR NEXT ENERGY|NORTHVOLT|SES AI|STARPLUS|POWERCO|"
    r"ULTIUM CELLS?"
    r")\b",
    re.I,
)
MH_NAME_RE = re.compile(
    r"FORKLIFT|LIFT TRUCK|PALLET JACK|MATERIALS? HANDLING|"
    r"CROWN EQUIPMENT|TOYOTA MATERIAL|RAYMOND CORP|"
    r"\bHYSTER\b|YALE LIFT|YALE MATERIALS|KOMATSU FORKLIFT|JUNGHEINRICH|"
    r"MITSUBISHI LOGISNEXT|HYSTER[-\s]YALE|UNI[\s-]?CARRIERS",
    re.I,
)
DC_WORDS = (
    "FULFILLMENT CENTER",
    "FULFILLMENT CTR",
    "FULFILLMENT CENTRE",
    "DISTRIBUTION CENTER",
    "DISTRIBUTION CTR",
    "DISTRIBUTION CENTRE",
    "SORTATION CENTER",
    "SORT CENTER",
    "SORT CENTRE",
    "PARCEL SORT",
    "DELIVERY STATION",
)

LEGAL_SUFFIX = re.compile(
    r"\b(INCORPORATED|CORPORATION|COMPANY|LIMITED|LLC|INC|LTD|CORP|LP|PLLC|CO|DBA)\b",
    re.I,
)
NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")


def log(message: str) -> None:
    print(message, flush=True)


def _download(url: str, dest: Path, timeout: int = 300) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10_000:
        log(f"  cache {dest.name} ({dest.stat().st_size:,} bytes)")
        return dest
    log(f"  download {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, dest.open("wb") as out:
        while True:
            buf = resp.read(1024 * 1024)
            if not buf:
                break
            out.write(buf)
    log(f"  wrote {dest.name} ({dest.stat().st_size:,} bytes)")
    return dest


def fetch_tri() -> Path:
    last_error: Exception | None = None
    for url in TRI_URLS:
        year = url.split("/")[-2].split("_")[0]
        cached = [RAW_DIR / f"tri_{year}_US.csv", RAW_DIR / f"tri_{year}.csv"]
        for dest in cached:
            if dest.exists() and dest.stat().st_size > 10_000:
                log(f"  cache {dest.name} ({dest.stat().st_size:,} bytes)")
                return dest
        try:
            return _download(url, RAW_DIR / f"tri_{year}_US.csv")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log(f"  skip TRI {year}: {exc}")
    raise RuntimeError(f"TRI download failed: {last_error}")


def fetch_fsis() -> Path:
    return _download(FSIS_URL, RAW_DIR / "fsis_mpi.json")


def fetch_ita() -> list[Path]:
    paths = [_download(ITA_URL, RAW_DIR / "ita_300a_2025.csv")]
    try:
        paths.append(_download(ITA_2024_URL, RAW_DIR / "ita_300a_2024.zip"))
    except Exception as exc:  # noqa: BLE001
        log(f"  skip ITA 2024: {exc}")
    return paths


def fetch_zcta() -> Path:
    return _download(ZCTA_URL, RAW_DIR / "zcta_national_2025.zip")


def _naics6(value: Any) -> str:
    text = str(value or "").strip().replace(".0", "")
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[:6]


def _norm_name(value: Any) -> str:
    text = NON_ALNUM.sub(" ", str(value or "").upper())
    text = LEGAL_SUFFIX.sub(" ", text)
    return " ".join(text.split())


def _parse_employees(value: Any) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text or text.lower() in {"nan", "none"}:
        return None
    try:
        number = int(float(text))
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def size_class_from_employees(employees: int | None) -> str:
    if employees is None:
        return "Unknown"
    if employees < 50:
        return "Small"
    if employees < 250:
        return "Medium"
    if employees < 1000:
        return "Large"
    return "Extra Large"


def industries_for(naics: str, name: str, parent: str = "") -> list[str]:
    n = _naics6(naics)
    found: list[str] = []
    if n.startswith(("3361", "3362", "3363")):
        found.append("automotive")
    if n.startswith("311") or n.startswith("3121"):
        found.append("food_manufacturing")
    if n.startswith("3344"):
        found.append("semiconductors")
    if n.startswith("33591"):
        found.append("battery_manufacturing")
    if n.startswith("493"):
        found.extend(["warehousing", "distribution_centers"])
    if n.startswith("33392"):
        found.append("materials_handling")

    upper = f"{name or ''} {parent or ''}".upper()
    if "battery_manufacturing" not in found:
        if BATTERY_PHRASE_RE.search(upper) or BATTERY_OEM_RE.search(upper):
            if n[:2] in {"32", "33"} or not n:
                found.append("battery_manufacturing")
    if "materials_handling" not in found and MH_NAME_RE.search(upper):
        if n.startswith("33") or not n:
            found.append("materials_handling")
    if not any(item in found for item in ("warehousing", "distribution_centers")):
        if any(word in upper for word in DC_WORDS):
            found.extend(["warehousing", "distribution_centers"])
    return found


def _nearest_metros(lats: np.ndarray, lons: np.ndarray, max_miles: float = 90.0) -> tuple[list[str], list[str]]:
    if len(lats) == 0:
        return [], []
    metros = pd.DataFrame(METROS)[["short", "cbsa", "lat", "lon"]]
    mlat = np.radians(metros["lat"].to_numpy(dtype=float))
    mlon = np.radians(metros["lon"].to_numpy(dtype=float))
    lat = np.radians(lats.astype(float))
    lon = np.radians(lons.astype(float))
    dlat = mlat[None, :] - lat[:, None]
    dlon = mlon[None, :] - lon[:, None]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat)[:, None] * np.cos(mlat)[None, :] * np.sin(dlon / 2) ** 2
    miles = 3958.8 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    j = miles.argmin(axis=1)
    nearest = miles[np.arange(len(lats)), j]
    shorts = metros["short"].to_numpy()
    cbsas = metros["cbsa"].to_numpy()
    out_short = np.where(nearest <= max_miles, shorts[j], "")
    out_cbsa = np.where(nearest <= max_miles, cbsas[j], "")
    return out_short.tolist(), out_cbsa.tolist()


def _rows_from_frame(frame: pd.DataFrame, source: str, segment: str) -> list[dict[str, Any]]:
    frame = frame.copy()
    frame["lat"] = pd.to_numeric(frame["lat"], errors="coerce")
    frame["lon"] = pd.to_numeric(frame["lon"], errors="coerce")
    good = frame[frame["lat"].notna() & frame["lon"].notna() & (frame["lat"].abs() > 1) & (frame["lon"].abs() > 1)].copy()
    if good.empty:
        return []
    shorts, cbsas = _nearest_metros(good["lat"].astype(float).to_numpy(), good["lon"].astype(float).to_numpy())
    rows = []
    for i, (_, rec) in enumerate(good.iterrows()):
        name = str(rec.get("name") or "").strip()
        if not name:
            continue
        city = str(rec.get("city") or "").strip()
        state = str(rec.get("state") or "").strip()
        metro = shorts[i] or f"{city}, {state}".strip(", ")
        industries = rec.get("industries")
        if industries is None or (isinstance(industries, float) and pd.isna(industries)):
            industries = industries_for(str(rec.get("naics") or ""), name, str(rec.get("parent") or ""))
        elif isinstance(industries, np.ndarray):
            industries = industries.tolist()
        site = str(rec.get("street") or "").strip()
        parent = str(rec.get("parent") or "").strip()
        raw_seg = rec.get("segment")
        if raw_seg is None or (isinstance(raw_seg, float) and pd.isna(raw_seg)) or str(raw_seg).strip() in {"", "nan", "None"}:
            segment_label = segment
        else:
            segment_label = str(raw_seg)[:80]
        if parent and parent.lower() not in {"nan", "none"}:
            site = f"{site} · parent {parent}" if site else f"Parent: {parent}"
        employees = _parse_employees(rec.get("employees"))
        raw_size = rec.get("size_class")
        if raw_size is None or (isinstance(raw_size, float) and pd.isna(raw_size)) or str(raw_size).strip() in {"", "nan", "None"}:
            size_class = size_class_from_employees(employees)
        else:
            size_class = str(raw_size)
        for industry in industries:
            rows.append(
                {
                    "id": f"{source}:{rec.get('ext_id')}:{industry}",
                    "name": name[:180],
                    "industry": industry,
                    "cbsa": cbsas[i] or None,
                    "metro": metro or state or "US",
                    "city": city,
                    "segment": segment_label or segment,
                    "site": site[:240],
                    "lat": float(rec["lat"]),
                    "lon": float(rec["lon"]),
                    "source": source,
                    "naics": _naics6(rec.get("naics")),
                    "parent": parent if parent.lower() not in {"nan", "none"} else "",
                    "state": state,
                    "address": str(rec.get("street") or "")[:200],
                    "employees": employees,
                    "size_class": size_class,
                    "website": resolve_website(name, parent, city, state),
                }
            )
    return rows


def load_tri_rows() -> list[dict[str, Any]]:
    path = fetch_tri()
    raw = pd.read_csv(path, usecols=list(TRI_COLUMNS), dtype=str, low_memory=False)
    raw = raw.rename(columns=TRI_COLUMNS)
    raw["ext_id"] = raw["trifd"].astype(str)
    raw["lat"] = pd.to_numeric(raw["lat"], errors="coerce")
    raw["lon"] = pd.to_numeric(raw["lon"], errors="coerce")
    raw = raw.drop_duplicates("ext_id")
    raw["industries"] = [
        industries_for(naics, name, parent)
        for naics, name, parent in zip(raw["naics"].fillna(""), raw["name"].fillna(""), raw["parent"].fillna(""))
    ]
    raw = raw[raw["industries"].map(bool)]
    log(f"  TRI mapped facilities: {len(raw):,}")
    return _rows_from_frame(raw, "epa_tri", "TRI reporter")


def load_fsis_rows() -> list[dict[str, Any]]:
    path = fetch_fsis()
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for item in payload:
        geo = str(item.get("geolocation") or "")
        if "," not in geo:
            continue
        try:
            lat_s, lon_s = geo.split(",", 1)
            lat, lon = float(lat_s.strip()), float(lon_s.strip())
        except ValueError:
            continue
        activities = item.get("activities") or []
        if isinstance(activities, list):
            segment = ", ".join(str(a) for a in activities[:3]) or "FSIS inspected"
        else:
            segment = str(activities) or "FSIS inspected"
        records.append(
            {
                "ext_id": str(item.get("establishment_id") or item.get("establishment_number")),
                "name": item.get("establishment_name") or (item.get("dbas") or [None])[0],
                "street": item.get("address"),
                "city": item.get("city"),
                "state": item.get("state"),
                "lat": lat,
                "lon": lon,
                "parent": "",
                "naics": "311",
                "industries": ["food_manufacturing"],
            }
        )
    frame = pd.DataFrame(records)
    log(f"  FSIS geocoded establishments: {len(frame):,}")
    return _rows_from_frame(frame, "usda_fsis", "FSIS inspected")


def _read_ita_csv(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            inner = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            with zf.open(inner) as fh:
                frame = pd.read_csv(fh, dtype=str, low_memory=False)
    else:
        frame = pd.read_csv(path, dtype=str, low_memory=False)
    rename = {
        "establishment_name": "name",
        "company_name": "parent",
        "street_address": "street",
        "zip_code": "zip",
        "naics_code": "naics",
        "establishment_id": "ext_id",
        "industry_description": "industry_description",
    }
    frame = frame.rename(columns={k: v for k, v in rename.items() if k in frame.columns})
    needed = {"name", "city", "state", "zip", "naics"}
    missing = needed - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns {sorted(missing)}")
    if "ext_id" not in frame.columns:
        frame["ext_id"] = frame["name"].fillna("") + "|" + frame["zip"].fillna("")
    if "parent" not in frame.columns:
        frame["parent"] = ""
    if "street" not in frame.columns:
        frame["street"] = ""
    if "industry_description" not in frame.columns:
        frame["industry_description"] = ""
    keep = ["ext_id", "name", "parent", "street", "city", "state", "zip", "naics", "industry_description"]
    if "annual_average_employees" in frame.columns:
        keep.append("annual_average_employees")
    return frame[keep]


def load_zcta_centroids() -> pd.DataFrame:
    path = fetch_zcta()
    with zipfile.ZipFile(path) as zf:
        inner = next(n for n in zf.namelist() if not n.endswith("/"))
        with zf.open(inner) as fh:
            sample = fh.read(800).decode("utf-8", "replace")
        sep = "|" if sample.count("|") > sample.count("\t") else "\t"
        frame = pd.read_csv(zf.open(inner), sep=sep, dtype=str)
    cols = {str(c).strip().upper(): c for c in frame.columns}
    geoid = cols.get("GEOID") or cols.get("GEOID20") or cols.get("ZCTA5") or list(frame.columns)[0]
    lat_col = cols.get("INTPTLAT") or cols.get("INTPTLAT20")
    lon_col = cols.get("INTPTLONG") or cols.get("INTPTLONG20")
    if not lat_col or not lon_col:
        raise ValueError(f"ZCTA file missing lat/lon columns: {list(frame.columns)}")
    out = pd.DataFrame(
        {
            "zip": frame[geoid].astype(str).str.extract(r"(\d{5})", expand=False),
            "lat": pd.to_numeric(frame[lat_col], errors="coerce"),
            "lon": pd.to_numeric(frame[lon_col], errors="coerce"),
        }
    ).dropna()
    return out.drop_duplicates("zip")


def _zip_jitter(name: str, zip_code: str) -> tuple[float, float]:
    digest = hashlib.md5(f"{name}|{zip_code}".encode("utf-8")).digest()
    return (digest[0] / 255 - 0.5) * 0.028, (digest[1] / 255 - 0.5) * 0.028


def load_ita_rows() -> list[dict[str, Any]]:
    paths = fetch_ita()
    chunks = []
    for path in paths:
        chunk = _read_ita_csv(path)
        chunk["_file"] = path.name
        chunks.append(chunk)
        log(f"  ITA file {path.name}: {len(chunk):,} rows")
    raw = pd.concat(chunks, ignore_index=True)
    raw["ext_id"] = raw["ext_id"].astype(str)
    raw = raw.drop_duplicates("ext_id", keep="first")
    raw["industries"] = [
        industries_for(naics, name, parent)
        for naics, name, parent in zip(raw["naics"].fillna(""), raw["name"].fillna(""), raw["parent"].fillna(""))
    ]
    raw = raw[raw["industries"].map(bool)].copy()
    if "annual_average_employees" in raw.columns:
        raw["employees"] = raw["annual_average_employees"].map(_parse_employees)
    else:
        raw["employees"] = pd.Series([None] * len(raw), index=raw.index)
    raw["size_class"] = raw["employees"].map(size_class_from_employees)
    raw["zip5"] = raw["zip"].astype(str).str.extract(r"(\d{5})", expand=False)
    zcta = load_zcta_centroids()
    raw = raw.merge(zcta, left_on="zip5", right_on="zip", how="left", suffixes=("", "_zcta"))
    raw = raw[raw["lat"].notna() & raw["lon"].notna()].copy()
    jit = [_zip_jitter(n, z) for n, z in zip(raw["name"].fillna(""), raw["zip5"].fillna(""))]
    raw["lat"] = raw["lat"] + [j[0] for j in jit]
    raw["lon"] = raw["lon"] + [j[1] for j in jit]
    desc = raw["industry_description"].fillna("").astype(str)
    raw["segment"] = np.where(desc.str.strip().ne(""), "ITA · " + desc.str.slice(0, 80), "OSHA ITA establishment")
    log(f"  ITA mapped facilities: {len(raw):,}")
    return _rows_from_frame(raw, "osha_ita", "OSHA ITA establishment")


def _dedupe_public(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    rank = {"epa_tri": 0, "usda_fsis": 1, "osha_ita": 2}
    frame["_rank"] = frame["source"].map(rank).fillna(9)
    frame["_key"] = (
        frame["industry"].fillna("")
        + "|"
        + frame["name"].map(_norm_name)
        + "|"
        + frame["state"].fillna("").str.upper()
        + "|"
        + frame["city"].fillna("").str.upper().str[:24]
    )
    frame = frame.sort_values(["_rank"]).drop_duplicates("_key", keep="first")
    return frame.drop(columns=["_rank", "_key"]).to_dict(orient="records")


def ingest_public_facilities(conn: Any, force: bool = True) -> dict[str, int]:
    if force:
        placeholders = ",".join("?" * len(PUBLIC_SOURCES))
        conn.execute(f"DELETE FROM companies WHERE source IN ({placeholders})", PUBLIC_SOURCES)
        conn.commit()
    rows: list[dict[str, Any]] = []
    try:
        rows.extend(load_tri_rows())
    except Exception as exc:  # noqa: BLE001
        log(f"TRI ingest failed: {exc}")
    try:
        rows.extend(load_fsis_rows())
    except Exception as exc:  # noqa: BLE001
        log(f"FSIS ingest failed: {exc}")
    try:
        rows.extend(load_ita_rows())
    except Exception as exc:  # noqa: BLE001
        log(f"ITA ingest failed: {exc}")
    rows = _dedupe_public(rows)
    if not rows:
        return {"facilities": 0}
    conn.executemany(
        """
        INSERT OR REPLACE INTO companies
        (id, name, industry, cbsa, metro, city, segment, site, lat, lon, source, naics, parent, state, address, employees, size_class, website)
        VALUES
        (:id, :name, :industry, :cbsa, :metro, :city, :segment, :site, :lat, :lon, :source, :naics, :parent, :state, :address, :employees, :size_class, :website)
        """,
        rows,
    )
    conn.commit()
    counts = pd.Series([r["industry"] for r in rows]).value_counts().to_dict()
    log("  inserted " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return {"facilities": len(rows), **{f"n_{k}": int(v) for k, v in counts.items()}}
