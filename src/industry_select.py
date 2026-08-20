"""Industry options for the sidebar: pinned MOI lenses plus top NAICS codes."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .naics_titles import format_naics_label
from .scoring import EQUAL_WEIGHTS, INDUSTRIES

TOP_NAICS = 100
DEFAULT_INDUSTRY_KEYS = ("automotive",)
NAICS_OPTION_PREFIX = "naics:"

# MOI lens → NAICS prefixes used at ingest (TRI / FSIS / OSHA ITA).
MOI_NAICS_PREFIXES: dict[str, tuple[str, ...]] = {
    "automotive": ("3361", "3362", "3363"),
    "warehousing": ("493",),
    "food_manufacturing": ("311", "3121"),
    "battery_manufacturing": ("33591",),
    "semiconductors": ("3344",),
    "distribution_centers": ("493",),
    "materials_handling": ("33392",),
}


@dataclass(frozen=True)
class IndustryOptions:
    keys: list[str]
    labels: dict[str, str]


def naics_digits(raw: object) -> str:
    text = str(raw or "").strip().replace(".0", "")
    return "".join(ch for ch in text if ch.isdigit())


def naics_group_key(raw: object) -> str:
    """6-digit group when present; 3-digit FSIS 311 (and other short codes) stay short."""
    digits = naics_digits(raw)
    if len(digits) >= 6:
        return digits[:6]
    if len(digits) >= 3:
        return digits
    return ""


def naics_option_key(code: str) -> str:
    return f"{NAICS_OPTION_PREFIX}{code}"


def naics_code_from_option(key: str) -> str | None:
    if key.startswith(NAICS_OPTION_PREFIX):
        return key[len(NAICS_OPTION_PREFIX) :]
    return None


def selected_moi_keys(selected: list[str]) -> list[str]:
    return [key for key in selected if key in INDUSTRIES]


def top_naics_codes(companies: pd.DataFrame, n: int = TOP_NAICS) -> list[str]:
    if companies.empty or "naics" not in companies.columns:
        return []
    grouped = companies["naics"].map(naics_group_key)
    grouped = grouped[grouped != ""]
    if grouped.empty:
        return []
    return grouped.value_counts().head(n).index.tolist()


def build_industry_options(companies: pd.DataFrame, n: int = TOP_NAICS) -> IndustryOptions:
    keys = list(INDUSTRIES.keys())
    labels = {key: f"MOI · {profile.label}" for key, profile in INDUSTRIES.items()}
    for code in top_naics_codes(companies, n=n):
        option = naics_option_key(code)
        if option in labels:
            continue
        keys.append(option)
        labels[option] = format_naics_label(code)
    return IndustryOptions(keys=keys, labels=labels)


def sanitize_selection(selected: list[str] | None, option_keys: list[str]) -> list[str]:
    allowed = set(option_keys)
    cleaned = [key for key in (selected or []) if key in allowed]
    if cleaned:
        return cleaned
    for key in DEFAULT_INDUSTRY_KEYS:
        if key in allowed:
            return [key]
    return option_keys[:1]


def selection_summary(selected: list[str]) -> str:
    moi = selected_moi_keys(selected)
    naics_keys = [key for key in selected if naics_code_from_option(key)]
    parts: list[str] = [INDUSTRIES[key].label.lower() for key in moi]
    if len(naics_keys) == 1:
        parts.append(f"NAICS {naics_code_from_option(naics_keys[0])}")
    elif len(naics_keys) > 1:
        parts.append(f"{len(naics_keys)} NAICS industries")
    if not parts:
        return INDUSTRIES["automotive"].label.lower()
    if len(parts) == 1:
        return parts[0]
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def filter_companies_by_industries(frame: pd.DataFrame, selected: list[str]) -> pd.DataFrame:
    if frame.empty:
        return frame
    moi = selected_moi_keys(selected)
    naics_codes = [code for code in (naics_code_from_option(key) for key in selected) if code]
    if not moi and not naics_codes:
        moi = list(DEFAULT_INDUSTRY_KEYS)

    mask = pd.Series(False, index=frame.index)
    industry = frame["industry"].fillna("").astype(str) if "industry" in frame.columns else pd.Series("", index=frame.index)
    digits = (
        frame["naics"].map(naics_digits)
        if "naics" in frame.columns
        else pd.Series("", index=frame.index)
    )
    if moi:
        mask = mask | industry.isin(moi)
        prefixes = tuple(prefix for key in moi for prefix in MOI_NAICS_PREFIXES[key])
        if prefixes:
            mask = mask | digits.str.startswith(prefixes)
    if naics_codes:
        mask = mask | digits.str.startswith(tuple(naics_codes))
    return frame.loc[mask].copy()


def scoring_caption(selected: list[str], equal_weight: bool) -> str:
    moi = selected_moi_keys(selected)
    if equal_weight:
        return "Metro scores use equal-weight pillars (no cluster overlay)."
    if moi:
        label = INDUSTRIES[moi[0]].label
        extra = ""
        if len(moi) > 1:
            others = ", ".join(INDUSTRIES[k].label for k in moi[1:])
            extra = f" Other MOI lenses ({others}) filter companies only."
        return f"Metro scores use {label} pillar weights (first selected MOI lens).{extra}"
    return "No MOI lens selected. Metro scores use equal-weight pillars with no cluster overlay."


def scoring_params(selected: list[str], equal_weight: bool) -> tuple[str | None, dict[str, float], float]:
    """Industry key, default pillar weights, and cluster blend for the current selection."""
    moi = selected_moi_keys(selected)
    if equal_weight or not moi:
        return (moi[0] if moi else None), dict(EQUAL_WEIGHTS), 0.0
    profile = INDUSTRIES[moi[0]]
    return profile.key, dict(profile.weights), profile.cluster_blend
