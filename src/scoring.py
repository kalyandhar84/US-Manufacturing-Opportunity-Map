"""Manufacturing Opportunity Index (MOI) scoring engine.

Pillar scores are structural metro attributes (0-100). The composite MOI
reweights those pillars by industry and blends in a cluster-affinity overlay
that captures existing OEM, supplier, fab, and 3PL presence.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

PILLARS = ("manufacturing", "logistics", "labor", "warehouse", "growth")

PILLAR_LABELS = {
    "manufacturing": "Manufacturing",
    "logistics": "Logistics",
    "labor": "Labor",
    "warehouse": "Warehouse",
    "growth": "Growth",
}

CLUSTER_KEYS = {
    "automotive": "automotive",
    "warehousing": "warehousing",
    "food_manufacturing": "food_manufacturing",
    "battery_manufacturing": "battery_manufacturing",
    "semiconductors": "semiconductors",
    "distribution_centers": "distribution_centers",
    "materials_handling": "materials_handling",
}


@dataclass(frozen=True)
class IndustryProfile:
    key: str
    label: str
    blurb: str
    weights: dict[str, float]
    cluster_blend: float
    what_matters: tuple[str, ...]


INDUSTRIES: dict[str, IndustryProfile] = {
    "automotive": IndustryProfile(
        key="automotive",
        label="Automotive",
        blurb="OEM assembly, Tier-1/2 suppliers, and EV transition capacity.",
        weights={
            "manufacturing": 0.30,
            "logistics": 0.18,
            "labor": 0.22,
            "warehouse": 0.12,
            "growth": 0.18,
        },
        cluster_blend=0.18,
        what_matters=(
            "Supplier density within a one-day truck radius",
            "Skilled production labor and technical colleges",
            "Inbound steel, stamping, and parts logistics",
            "Industrial land for body shops and sequencing centers",
        ),
    ),
    "warehousing": IndustryProfile(
        key="warehousing",
        label="Warehousing",
        blurb="Bulk storage, 3PL, cold chain, and industrial inventory.",
        weights={
            "manufacturing": 0.08,
            "logistics": 0.28,
            "labor": 0.18,
            "warehouse": 0.30,
            "growth": 0.16,
        },
        cluster_blend=0.16,
        what_matters=(
            "Available industrial inventory and developable land",
            "Highway, rail, and intermodal connectivity",
            "Warehouse labor pool and wage competitiveness",
            "Permit velocity and speculative construction pipeline",
        ),
    ),
    "food_manufacturing": IndustryProfile(
        key="food_manufacturing",
        label="Food manufacturing",
        blurb="Processing, CPG, cold storage, and ingredient inbound.",
        weights={
            "manufacturing": 0.24,
            "logistics": 0.20,
            "labor": 0.22,
            "warehouse": 0.18,
            "growth": 0.16,
        },
        cluster_blend=0.16,
        what_matters=(
            "Proximity to agricultural inbound and protein/grain corridors",
            "Cold-storage and food-grade industrial stock",
            "Stable production labor at competitive wages",
            "Water, wastewater, and utility capacity",
        ),
    ),
    "battery_manufacturing": IndustryProfile(
        key="battery_manufacturing",
        label="Battery manufacturing",
        blurb="Cells, modules, packs, and EV supply-chain co-location.",
        weights={
            "manufacturing": 0.26,
            "logistics": 0.16,
            "labor": 0.20,
            "warehouse": 0.14,
            "growth": 0.24,
        },
        cluster_blend=0.20,
        what_matters=(
            "Power availability and industrial electricity cost",
            "Auto OEM offtake within a one-day haul",
            "Large-site industrial land and mega-permit capacity",
            "Workforce pipeline for process technicians",
        ),
    ),
    "semiconductors": IndustryProfile(
        key="semiconductors",
        label="Semiconductors",
        blurb="Fabs, ATMP, materials, and CHIPS-aligned ecosystems.",
        weights={
            "manufacturing": 0.22,
            "logistics": 0.12,
            "labor": 0.28,
            "warehouse": 0.10,
            "growth": 0.28,
        },
        cluster_blend=0.22,
        what_matters=(
            "STEM labor, research universities, and technician supply",
            "Ultra-reliable power and process water",
            "Existing fab/tooling/materials cluster",
            "Population and construction momentum for a long ramp",
        ),
    ),
    "distribution_centers": IndustryProfile(
        key="distribution_centers",
        label="Distribution centers",
        blurb="Fulfillment, sortation, and two-day population coverage.",
        weights={
            "manufacturing": 0.06,
            "logistics": 0.32,
            "labor": 0.16,
            "warehouse": 0.28,
            "growth": 0.18,
        },
        cluster_blend=0.16,
        what_matters=(
            "National or regional population coverage by truck",
            "Air cargo, intermodal, and interstate confluence",
            "Big-box industrial product and land",
            "Parcel/3PL density and last-mile labor",
        ),
    ),
    # Forklift / conveyor / crane OEMs need a manufacturing labor bench; demand
    # follows warehouse and 3PL density. Weights sit between automotive (plant)
    # and warehousing (customer). Cluster blend 0.17 is between those two.
    "materials_handling": IndustryProfile(
        key="materials_handling",
        label="Materials handling & forklifts",
        blurb="Industrial trucks, conveyors, cranes, and warehouse equipment.",
        weights={
            "manufacturing": 0.24,
            "logistics": 0.22,
            "labor": 0.22,
            "warehouse": 0.20,
            "growth": 0.12,
        },
        cluster_blend=0.17,
        what_matters=(
            "Lift-truck OEM, dealer, and service density",
            "Warehouse and 3PL customers within a one-day haul",
            "Production labor for industrial trucks, conveyors, and cranes",
            "Inbound steel/components and outbound parts logistics",
        ),
    ),
}

EQUAL_WEIGHTS = {pillar: 1.0 / len(PILLARS) for pillar in PILLARS}


def weighted_pillar_score(row: pd.Series, weights: dict[str, float]) -> float:
    total = sum(weights.values()) or 1.0
    return sum(float(row[pillar]) * weights[pillar] for pillar in PILLARS) / total


def opportunity_index(
    row: pd.Series,
    industry_key: str | None,
    custom_weights: dict[str, float] | None = None,
    cluster_blend: float | None = None,
) -> float:
    if not industry_key or industry_key not in INDUSTRIES:
        weights = custom_weights or EQUAL_WEIGHTS
        return weighted_pillar_score(row, weights)
    profile = INDUSTRIES[industry_key]
    weights = custom_weights or profile.weights
    blend = profile.cluster_blend if cluster_blend is None else cluster_blend
    pillars = weighted_pillar_score(row, weights)
    if blend <= 0:
        return pillars
    cluster = float(row[profile.key])
    return (1.0 - blend) * pillars + blend * cluster


def score_metros(
    metros: pd.DataFrame,
    industry_key: str | None,
    custom_weights: dict[str, float] | None = None,
    cluster_blend: float | None = None,
) -> pd.DataFrame:
    df = metros.copy()
    df["score"] = df.apply(
        lambda row: opportunity_index(row, industry_key, custom_weights, cluster_blend),
        axis=1,
    )
    df["score"] = df["score"].round(1)
    df["rank"] = df["score"].rank(ascending=False, method="min").astype(int)
    return df.sort_values(["score", "short"], ascending=[False, True]).reset_index(drop=True)


def contribution_breakdown(
    row: pd.Series,
    industry_key: str | None,
    custom_weights: dict[str, float] | None = None,
    cluster_blend: float | None = None,
) -> pd.DataFrame:
    profile = INDUSTRIES.get(industry_key) if industry_key else None
    weights = custom_weights or (profile.weights if profile else EQUAL_WEIGHTS)
    if cluster_blend is None:
        blend = profile.cluster_blend if profile else 0.0
    else:
        blend = cluster_blend
    total_w = sum(weights.values()) or 1.0
    rows = []
    for pillar in PILLARS:
        weight = weights[pillar] / total_w
        value = float(row[pillar])
        rows.append(
            {
                "component": PILLAR_LABELS[pillar],
                "raw": value,
                "weight": weight * (1.0 - blend),
                "contribution": value * weight * (1.0 - blend),
            }
        )
    if profile and blend > 0:
        cluster_val = float(row[profile.key])
        rows.append(
            {
                "component": f"{profile.label} cluster",
                "raw": cluster_val,
                "weight": blend,
                "contribution": cluster_val * blend,
            }
        )
    return pd.DataFrame(rows)
