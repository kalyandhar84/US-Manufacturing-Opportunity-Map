"""US Manufacturing Opportunity Index — interactive metro and company maps."""

from __future__ import annotations

import html
import json
import textwrap
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.companies import is_search_website
from src.contact import save_contact_message, validate_contact

from src.db import (
    DB_PATH,
    latest_refresh,
    load_companies_frame,
    load_company_news,
    load_industrial_market,
    load_metro_timeseries,
    load_projects_frame,
    metro_count,
)
from src.metros import metros_frame
from src.scoring import (
    INDUSTRIES,
    PILLAR_LABELS,
    PILLARS,
    contribution_breakdown,
    score_metros,
    weighted_pillar_score,
)

PAGE_TITLE = "US Manufacturing Opportunity Map"
PAGE_DESCRIPTION = (
    "US manufacturing opportunity map for site selection and industrial real estate. "
    "Rank metros and plants for forklifts, warehousing, battery manufacturing, and semiconductors."
)
GITHUB_REPO = "https://github.com/kalyandhar84/US-Manufacturing-Opportunity-Map"

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=":material/factory:",
    layout="wide",
    initial_sidebar_state="expanded",
)

AUDIENCES = {
    "Manufacturers": "site selectors comparing labor, utilities, suppliers, and time-to-production",
    "Investors": "allocators underwriting industrial demand, rent growth, and cluster follow-on",
    "Consultants": "advisors who need a transparent, factor-level ranking to take into a workshop",
    "Economic development": "EDOs benchmarking their metro against peer destinations",
    "Logistics companies": "3PLs and carriers hunting density, empty-backhaul, and DC concentration",
    "Real estate": "industrial developers and brokers mapping residual demand after the 2022–25 supply wave",
    "Equipment dealers": "OEMs and dealers positioning inventory where plants and warehouses are expanding",
}

INK = "#15202B"
MUTED = "#4A5866"
PAPER = "#F3EFE4"
CARD = "#FFFFFF"
NAVY = "#15456B"
COPPER = "#A84812"
GRID = "#DDD4C4"
LAND = "#E7DECC"
WATER = "#C5D7E8"
SUBUNIT = "#C4B9A6"

INDUSTRY_COLORS = {
    "automotive": "#15456B",
    "warehousing": "#A84812",
    "food_manufacturing": "#2F6A45",
    "battery_manufacturing": "#6D28D9",
    "semiconductors": "#0F766E",
    "distribution_centers": "#9A3412",
    "materials_handling": "#0369A1",
}

# Companies-tab map zones. Eastern (default) is the seaboard + Appalachia +
# Florida plus the eastern industrial belt — not the Census South (which
# includes TX/OK and is too large for a first-load map).
EASTERN_STATES = frozenset(
    {
        "ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA",
        "DE", "MD", "DC", "VA", "WV", "NC", "SC", "GA", "FL",
        "OH", "MI", "IN", "KY", "TN",
    }
)
NORTHEAST_STATES = frozenset({"ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA"})
SOUTH_STATES = frozenset(
    {
        "DE", "MD", "DC", "VA", "WV", "NC", "SC", "GA", "FL",
        "KY", "TN", "AL", "MS", "AR", "LA", "OK", "TX",
    }
)
MIDWEST_STATES = frozenset({"OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"})
WEST_STATES = frozenset({"MT", "ID", "WY", "CO", "NM", "AZ", "UT", "NV", "WA", "OR", "CA", "AK", "HI"})
ZONE_STATES: dict[str, frozenset[str] | None] = {
    "Eastern": EASTERN_STATES,
    "Northeast": NORTHEAST_STATES,
    "South": SOUTH_STATES,
    "Midwest": MIDWEST_STATES,
    "West": WEST_STATES,
    "All US": None,
}
SIZE_FILTERS = ("All sizes", "Small", "Medium", "Large", "Extra Large")
MAP_POINT_CAP = 2000


def inject_seo() -> None:
    description = json.dumps(PAGE_DESCRIPTION)
    title = json.dumps(PAGE_TITLE)
    st.html(
        f"""
        <script>
        (function () {{
          const title = {title};
          const description = {description};
          function upsert(attr, key, content) {{
            let el = document.querySelector('meta[' + attr + '="' + key + '"]');
            if (!el) {{
              el = document.createElement('meta');
              el.setAttribute(attr, key);
              document.head.appendChild(el);
            }}
            el.setAttribute('content', content);
          }}
          document.title = title;
          upsert('name', 'description', description);
          upsert('name', 'robots', 'index, follow');
          upsert('name', 'googlebot', 'index, follow');
          upsert('property', 'og:title', title);
          upsert('property', 'og:description', description);
          upsert('property', 'og:type', 'website');
          upsert('name', 'twitter:card', 'summary');
          upsert('name', 'twitter:title', title);
          upsert('name', 'twitter:description', description);
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def inject_css() -> None:
    st.html(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap");

        html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; color: #15202B; }
        .block-container { padding-top: 1.15rem; padding-bottom: 2.6rem; max-width: 1680px; }
        header[data-testid="stHeader"] { background: rgba(243,239,228,0.94); border-bottom: 1px solid #D6CCBB; }
        h1, h2, h3 { font-family: "Source Serif 4", "IBM Plex Serif", serif; letter-spacing: -0.02em; color: #15202B; }
        .hero-panel {
            background: linear-gradient(165deg, #FFFFFF 0%, #F7F3EA 100%);
            border: 1px solid #D6CCBB; border-radius: 16px;
            box-shadow: 0 14px 36px rgba(21, 32, 43, 0.07);
            padding: 1.35rem 1.55rem 1.2rem; margin: 0 0 1rem 0;
        }
        .hero-kicker {
            color: #A84812; font-size: 0.78rem; font-weight: 600;
            letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 0.4rem;
        }
        .hero-title {
            font-family: "Source Serif 4", serif; font-size: 2.28rem; font-weight: 600;
            line-height: 1.12; margin: 0 0 0.45rem 0; color: #15202B;
        }
        .hero-sub { color: #4A5866; font-size: 1.04rem; max-width: 52rem; line-height: 1.5; margin: 0 0 0.7rem 0; }
        .hero-about {
            color: #15202B; font-size: 0.95rem; max-width: 54rem; line-height: 1.55;
            margin: 0; padding-top: 0.55rem; border-top: 1px solid #E4D9C8;
        }
        .market-banner {
            background: #FFFFFF; padding: 0.95rem 1.15rem; margin: 0.9rem 0 0.2rem 0;
            color: #3A4654; font-size: 0.95rem; line-height: 1.5;
            border: 1px solid #D6CCBB; border-left: 4px solid #A84812; border-radius: 10px;
            box-shadow: 0 6px 18px rgba(21, 32, 43, 0.04);
        }
        .market-banner strong { color: #15202B; }
        .caption-src { color: #6B7784; font-size: 0.78rem; margin-top: 0.35rem; }
        div[data-testid="stMetric"] {
            background: #FFFFFF; border: 1px solid #D6CCBB; border-radius: 12px;
            padding: 0.9rem 1.05rem; box-shadow: 0 8px 22px rgba(21, 32, 43, 0.05);
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #15202B; font-family: "Source Serif 4", serif; font-weight: 600;
        }
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] { color: #4A5866; font-weight: 600; }
        .metro-card, .news-card, .contact-card {
            background: #FFFFFF; border: 1px solid #D6CCBB; border-radius: 14px;
            padding: 1.1rem 1.2rem; box-shadow: 0 10px 28px rgba(21, 32, 43, 0.06);
        }
        .metro-card h3, .news-card h3, .contact-card h3 {
            font-family: "Source Serif 4", serif; margin: 0 0 0.25rem 0;
            font-size: 1.35rem; color: #15202B;
        }
        .rank-pill {
            display: inline-block; background: #15456B; color: #FFFFFF;
            font-weight: 700; font-size: 0.75rem; letter-spacing: 0.04em;
            padding: 0.18rem 0.55rem; margin-bottom: 0.5rem; border-radius: 999px;
        }
        .tagline { color: #A84812; font-size: 0.95rem; margin: 0.15rem 0 0.7rem 0; }
        .section-label {
            color: #A84812; font-size: 0.75rem; font-weight: 600;
            letter-spacing: 0.14em; text-transform: uppercase; margin: 0.15rem 0 0.55rem 0;
        }
        .news-item { padding: 0.7rem 0; border-bottom: 1px solid #DDD4C4; }
        .news-item:last-child { border-bottom: none; }
        .news-date { color: #6B7784; font-size: 0.78rem; }
        .company-web { color: #4A5866; font-size: 0.88rem; margin: 0.28rem 0 0.4rem 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .company-web a { color: #15456B; }
        [data-testid="stSidebar"] { background: #E6DCC8; }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            font-family: "Source Serif 4", serif; color: #15202B;
        }
        [data-testid="stSidebar"] label { color: #15202B; font-weight: 600; }
        [data-testid="stPlotlyChart"] {
            background: #FFFFFF; border: 1px solid #D6CCBB; border-radius: 14px;
            box-shadow: 0 12px 30px rgba(21, 32, 43, 0.06); padding: 0.4rem;
        }
        div[data-testid="stTabs"] button[role="tab"] { font-weight: 600; }
        .stButton button, .stDownloadButton button, .stFormSubmitButton button, .stLinkButton a {
            border-radius: 8px !important; font-weight: 600 !important;
            box-shadow: 0 1px 2px rgba(21, 32, 43, 0.08);
        }
        .stButton button:hover, .stDownloadButton button:hover, .stFormSubmitButton button:hover {
            box-shadow: 0 6px 16px rgba(21, 69, 107, 0.16);
        }
        button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
            outline: 2px solid #15456B !important; outline-offset: 2px !important;
        }
        </style>
        """
    )


def render_contact() -> None:
    st.markdown('<div class="section-label">Contact us</div>', unsafe_allow_html=True)
    left, right = st.columns([1.05, 1], gap="large")
    with left:
        st.markdown(
            """
            <div class="contact-card">
                <div class="rank-pill">OPEN SOURCE</div>
                <h3>US Manufacturing Opportunity Map</h3>
                <div class="tagline">Code, issues, and architecture notes live on GitHub.</div>
                <p>This map ranks US metros for manufacturing site selection and industrial real estate,
                including forklifts, warehousing, battery plants, and semiconductors.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.link_button(
            "Open the GitHub repository",
            GITHUB_REPO,
            icon=":material/code:",
            type="primary",
            width="stretch",
        )
        st.caption("https://github.com/kalyandhar84/US-Manufacturing-Opportunity-Map")
    with right:
        with st.form("contact_us_form", clear_on_submit=False, border=True):
            st.subheader("Send a note")
            name = st.text_input("Name")
            email = st.text_input("Email")
            company = st.text_input("Company (optional)")
            message = st.text_area("Message", height=140)
            submitted = st.form_submit_button("Send message", type="primary", icon=":material/send:")
        if submitted:
            error = validate_contact(name, email, message)
            if error:
                st.error(error, icon=":material/error:")
            else:
                path = save_contact_message(name=name, email=email, company=company, message=message)
                st.success(f"Saved {path.name}.", icon=":material/check_circle:")
        st.caption("Files land in mail/ on the server. App Service wwwroot is emptied on recycle.")



def _html_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return html.escape(text, quote=True)


def _http_url(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return url


def company_website_html(company: object) -> str:
    raw = company.get("website") if hasattr(company, "get") else None
    url = _http_url(raw)
    if not url:
        return ""
    href = html.escape(url, quote=True)
    if is_search_website(url):
        return (
            f'<div class="company-web">'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">Find website</a>'
            f" · Web search</div>"
        )
    display = html.escape(url.replace("https://", "").replace("http://", "").rstrip("/"))
    return (
        f'<div class="company-web">Website · '
        f'<a href="{href}" target="_blank" rel="noopener noreferrer">{display}</a></div>'
    )


def geo_layout(height: int = 780) -> dict:
    return dict(
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor=PAPER,
        plot_bgcolor=PAPER,
        height=height,
        dragmode=False,
        font=dict(color=INK),
    )


def apply_geos(fig: go.Figure) -> None:
    fig.update_geos(
        scope="usa",
        projection_type="albers usa",
        showland=True,
        landcolor=LAND,
        showlakes=True,
        lakecolor=WATER,
        showsubunits=True,
        subunitcolor=SUBUNIT,
        subunitwidth=0.7,
        bgcolor=PAPER,
        showframe=False,
        showcoastlines=False,
        showocean=True,
        oceancolor=WATER,
    )


def map_figure(df: pd.DataFrame, selected: str) -> go.Figure:
    sizes = 11 + (df["score"] - df["score"].min()) / max(df["score"].max() - df["score"].min(), 1) * 22
    fig = go.Figure()
    fig.add_trace(
        go.Scattergeo(
            lon=df["lon"],
            lat=df["lat"],
            text=df["short"],
            customdata=df[["short", "score", "rank", "state"]].to_numpy(),
            marker=dict(
                size=sizes,
                color=df["score"],
                colorscale=[
                    [0.0, "#9BB4C8"],
                    [0.45, "#4F7FA3"],
                    [0.75, "#15456B"],
                    [1.0, "#A84812"],
                ],
                cmin=float(df["score"].min()),
                cmax=float(df["score"].max()),
                colorbar=dict(
                    title=dict(text="MOI", font=dict(color=MUTED, size=11)),
                    thickness=14,
                    len=0.55,
                    bgcolor="rgba(0,0,0,0)",
                    tickfont=dict(color=MUTED, size=11),
                    outlinewidth=0,
                ),
                line=dict(width=0.7, color=PAPER),
                opacity=0.95,
            ),
            hovertemplate="<b>%{customdata[0]}</b><br>Score %{customdata[1]:.1f} · Rank #%{customdata[2]}<extra></extra>",
        )
    )
    sel = df[df["short"] == selected]
    if not sel.empty:
        fig.add_trace(
            go.Scattergeo(
                lon=sel["lon"],
                lat=sel["lat"],
                mode="markers",
                marker=dict(size=34, color="rgba(0,0,0,0)", line=dict(width=2.4, color=NAVY)),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    apply_geos(fig)
    fig.update_layout(**geo_layout(780))
    return fig


def company_map_figure(df: pd.DataFrame, selected_id: str | None) -> go.Figure:
    n = len(df)
    if n > 1500:
        marker_size = 4
    elif n > 800:
        marker_size = 5
    elif n > 400:
        marker_size = 7
    else:
        marker_size = 11
    fig = go.Figure()
    for industry, chunk in df.groupby("industry"):
        fig.add_trace(
            go.Scattergeo(
                lon=chunk["lon"],
                lat=chunk["lat"],
                text=chunk["name"],
                customdata=chunk[["id", "name", "metro", "segment"]].to_numpy(),
                name=INDUSTRIES[industry].label if industry in INDUSTRIES else industry,
                marker=dict(
                    size=marker_size,
                    color=INDUSTRY_COLORS.get(industry, NAVY),
                    line=dict(width=0.4, color=PAPER),
                    opacity=0.82,
                ),
                hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[3]} · %{customdata[2]}<extra></extra>",
            )
        )
    if selected_id:
        sel = df[df["id"] == selected_id]
        if not sel.empty:
            fig.add_trace(
                go.Scattergeo(
                    lon=sel["lon"],
                    lat=sel["lat"],
                    mode="markers",
                    marker=dict(size=22, color="rgba(0,0,0,0)", line=dict(width=2.4, color=COPPER)),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    apply_geos(fig)
    fig.update_layout(
        **geo_layout(780),
        legend=dict(orientation="h", y=1.02, x=0, font=dict(color=INK, size=11), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def radar_figure(row: pd.Series) -> go.Figure:
    labels = [PILLAR_LABELS[p] for p in PILLARS]
    values = [float(row[p]) for p in PILLARS]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values + values[:1],
            theta=labels + labels[:1],
            fill="toself",
            fillcolor="rgba(21,69,107,0.18)",
            line=dict(color=NAVY, width=2),
            hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor=CARD,
            radialaxis=dict(range=[0, 100], tickfont=dict(size=10, color=MUTED), gridcolor=GRID, linecolor=GRID),
            angularaxis=dict(tickfont=dict(size=12, color=INK), gridcolor=GRID, linecolor=GRID),
        ),
        paper_bgcolor=CARD,
        margin=dict(l=40, r=40, t=20, b=20),
        height=300,
        showlegend=False,
    )
    return fig


def contribution_figure(row: pd.Series, industry_key: str, weights: dict[str, float]) -> go.Figure:
    contrib = contribution_breakdown(row, industry_key, weights).sort_values("contribution")
    fig = go.Figure(
        go.Bar(
            x=contrib["contribution"],
            y=contrib["component"],
            orientation="h",
            marker=dict(color=NAVY),
            hovertemplate="%{y}: %{x:.1f} pts<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        margin=dict(l=10, r=16, t=8, b=8),
        height=260,
        xaxis=dict(title="Points toward MOI", color=MUTED, gridcolor=GRID, zeroline=False),
        yaxis=dict(color=INK),
        font=dict(color=INK),
    )
    return fig


def timeseries_figure(series: pd.DataFrame, metro: str) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=series["year"],
            y=series["value"],
            mode="lines+markers",
            line=dict(color=NAVY, width=2.4),
            marker=dict(size=8, color=COPPER),
            hovertemplate="%{x}: %{y:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=f"Equal-weight MOI backcast · {metro}", font=dict(size=13, color=INK)),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        height=260,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(title="Year", color=MUTED, gridcolor=GRID, dtick=1),
        yaxis=dict(title="Index (0–100)", range=[50, 100], color=MUTED, gridcolor=GRID),
        font=dict(color=INK),
    )
    return fig


def audience_take(audience: str, industry_label: str, top: pd.DataFrame) -> str:
    leaders = ", ".join(top.head(3)["short"].tolist())
    templates = {
        "Manufacturers": (
            f"For {industry_label.lower()} operations, {leaders} currently combine "
            "production capability with a workable labor and logistics stack."
        ),
        "Investors": (
            f"{industry_label} scoring elevates {leaders}, where occupier depth and cluster "
            "follow-on can absorb space as completions stay historically low. Pair MOI with vacancy."
        ),
        "Consultants": (
            f"{leaders} lead on the {industry_label.lower()} weights. Drill the contribution bars "
            "before treating this as a site decision."
        ),
        "Economic development": (
            f"Against this {industry_label.lower()} lens, the board is {leaders}."
        ),
        "Logistics companies": (
            f"{leaders} concentrate the freight and warehouse scores that support backhaul and DC density."
        ),
        "Real estate": (
            f"Colliers’ Q2 2026 reset is not uniform. {industry_label} demand tilts toward {leaders}."
        ),
        "Equipment dealers": (
            f"Plant and DC expansions in {leaders} are the near-term install base."
        ),
    }
    return templates[audience]


def why_this_metro(row: pd.Series, industry_key: str) -> list[str]:
    profile = INDUSTRIES[industry_key]
    ranked_pillars = sorted(PILLARS, key=lambda p: float(row[p]), reverse=True)
    top_p, mid_p = ranked_pillars[0], ranked_pillars[1]
    weakest = ranked_pillars[-1]
    lines = [
        f"Strongest structural pillar is {PILLAR_LABELS[top_p]} ({int(row[top_p])}), "
        f"with {PILLAR_LABELS[mid_p]} close behind ({int(row[mid_p])}).",
        f"{profile.label} cluster affinity is {int(row[industry_key])}/100.",
        f"Watch-out: {PILLAR_LABELS[weakest]} scores {int(row[weakest])}.",
    ]
    return lines + list(row["highlights"])


def selection_id(event, field: str = "short") -> str | None:
    points = event.selection.get("points", []) if event and event.selection else []
    if not points:
        return None
    cd = points[0].get("customdata")
    if not cd:
        return None
    return cd[0] if field == "id" or field == "short" else cd[0]


def company_states(frame: pd.DataFrame) -> pd.Series:
    states = frame["state"].fillna("").astype(str).str.strip().str.upper() if "state" in frame.columns else pd.Series("", index=frame.index)
    two = states.str.len() == 2
    metro_tail = frame["metro"].fillna("").astype(str).str.rsplit(",", n=1).str[-1].str.strip().str.upper()
    inferred = metro_tail.where(metro_tail.str.len() == 2, "")
    return states.where(two, inferred)


def filter_company_view(frame: pd.DataFrame, zone: str, size_choice: str | None, query: str) -> pd.DataFrame:
    view = frame
    allowed = ZONE_STATES.get(zone)
    if allowed is not None:
        view = view[company_states(view).isin(allowed)]
    if size_choice and size_choice != "All sizes":
        if "size_class" in view.columns:
            classes = view["size_class"].fillna("Unknown").astype(str)
        else:
            classes = pd.Series("Unknown", index=view.index)
        view = view[classes == size_choice]
    if query.strip():
        blob = (
            view["name"].fillna("")
            + " "
            + view["city"].fillna("")
            + " "
            + view["parent"].fillna("")
            + " "
            + view["metro"].fillna("")
        ).str.lower()
        view = view[blob.str.contains(query.strip().lower(), regex=False)]
    return view


@st.cache_data(ttl="30m", show_spinner=False)
def cached_companies() -> pd.DataFrame:
    return load_companies_frame()


inject_seo()
inject_css()

if "selected_metro" not in st.session_state:
    st.session_state.selected_metro = "Dallas"
if "selected_company" not in st.session_state:
    st.session_state.selected_company = "hyundai-savannah"

raw = metros_frame()
companies = cached_companies()
news_all = load_company_news()
projects = load_projects_frame()
market = load_industrial_market()

with st.sidebar:
    st.markdown("### Filters")
    st.caption("Industry, audience, and index weights for this session.")
    industry_key = st.selectbox(
        "Industry",
        options=list(INDUSTRIES.keys()),
        format_func=lambda k: INDUSTRIES[k].label,
        index=0,
    )
    profile = INDUSTRIES[industry_key]
    st.caption(profile.blurb)
    audience = st.selectbox("Audience lens", list(AUDIENCES.keys()), index=0)
    region = st.selectbox("Region", ["United States", "Midwest", "South", "West", "Northeast"])
    min_pop = st.select_slider(
        "Minimum metro population",
        options=[0, 500_000, 1_000_000, 2_000_000, 4_000_000],
        value=0,
        format_func=lambda n: "No minimum" if n == 0 else f"{n/1_000_000:.1f}M+",
    )
    st.markdown("**Index construction**")
    mode = st.radio(
        "Score mode",
        ["Industry-weighted MOI", "Equal-weight pillars"],
        help="Equal-weight averages the five pillars. Industry-weighted applies cluster affinity.",
    )
    customize = st.toggle("Customize pillar weights", value=False)
    weights = dict(profile.weights)
    blend = profile.cluster_blend
    if customize:
        st.caption("Weights are normalized automatically.")
        for pillar in PILLARS:
            weights[pillar] = st.slider(PILLAR_LABELS[pillar], 0.0, 1.0, float(profile.weights[pillar]), 0.01)
        blend = st.slider("Cluster overlay", 0.0, 0.40, float(profile.cluster_blend), 0.01)
    if mode == "Equal-weight pillars":
        weights = {p: 0.2 for p in PILLARS}
        blend = 0.0
    refresh = latest_refresh()
    if refresh:
        when = (refresh.get("finished_at") or refresh.get("started_at") or "")[:16].replace("T", " ")
        st.caption(f"SQLite · {metro_count()} metros · {when} UTC ({refresh['status']})")
    else:
        st.caption(f"SQLite · {metro_count()} metros")
    st.caption(str(DB_PATH))

panel = raw.copy()
if region != "United States":
    panel = panel[panel["region"] == region]
panel = panel[panel["population"] >= min_pop]
if panel.empty:
    st.warning("No metros match these filters.")
    st.stop()

scored = score_metros(panel, industry_key, weights, blend)
if not market.empty:
    scored = scored.merge(market[["cbsa", "vacancy_pct", "rent_index"]], on="cbsa", how="left")
top = scored.iloc[0]
median = float(scored["score"].median())
spread = float(scored["score"].max() - scored["score"].min())
options = scored["short"].tolist()
if st.session_state.selected_metro not in options:
    st.session_state.selected_metro = options[0]

st.markdown(
    f"""
    <div class="hero-panel">
        <div class="hero-kicker">US Manufacturing Opportunity Map</div>
        <div class="hero-title">Manufacturing Opportunity Index</div>
        <p class="hero-sub">
            Daylight view of metro scores and the companies already on the ground for
            {profile.label.lower()}. Click the map. Built for {AUDIENCES[audience]}.
        </p>
        <p class="hero-about">
            About this map. A US manufacturing opportunity map for site selection and
            industrial real estate, covering forklifts, warehousing, battery plants,
            and semiconductors across ranked metros.
        </p>
        <div class="market-banner">
            <strong>Wave 3 layer · Q2 2026 industrial reset.</strong>
            US industrial demand exceeded new supply for the first time since 2022
            (Colliers: 59 million sq ft absorbed, vacancy 7.3%). This view adds announced
            capex, a company/news map, vacancy tilts, and a 2021–2026 score backcast.
        </div>
        <div class="caption-src">National vacancy print: Colliers U.S. Industrial Outlook, Q2 2026. Local vacancy is a model tilt, not licensed submarket data.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

industry_cos = companies[companies["industry"] == industry_key].copy() if not companies.empty else companies
industry_projects = projects[projects["industry"] == industry_key] if not projects.empty else projects
capex_sum = float(industry_projects["capex_b"].sum()) if not industry_projects.empty else 0.0
jobs_sum = int(industry_projects["jobs"].sum()) if not industry_projects.empty else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Top metro", f"{top['short']}", f"MOI {top['score']:.1f}", border=True)
k2.metric("Panel median", f"{median:.1f}", border=True)
k3.metric("Companies mapped", f"{len(industry_cos)}", profile.label, border=True)
k4.metric("Announced capex", f"${capex_sum:.0f}B", f"{jobs_sum:,} jobs", border=True)
k5.metric("Natl. vacancy", "7.3%", "Colliers Q2 2026", border=True)

tab_map, tab_cos, tab_contact = st.tabs(
    ["Opportunity map", "Companies and news", "Contact us"],
    on_change="rerun",
)

with tab_map:
    st.markdown(f'<div class="section-label">{profile.label} · {region} · click a metro</div>', unsafe_allow_html=True)
    fig = map_figure(scored, st.session_state.selected_metro)
    event = st.plotly_chart(
        fig,
        width="stretch",
        key="moi_map",
        on_select="rerun",
        selection_mode="points",
        config={"displayModeBar": False},
    )
    picked = selection_id(event, "short")
    if picked:
        st.session_state.selected_metro = picked
    st.caption("Bubble size and color are the Manufacturing Opportunity Index. The map is the primary workspace — rankings sit below.")

    st.selectbox("Metro brief", options=options, key="selected_metro")
    selected = st.session_state.selected_metro
    row = scored[scored["short"] == selected].iloc[0]
    local_projects = projects[projects["metro"] == selected] if not projects.empty else projects
    local_cos = companies[companies["metro"] == selected] if not companies.empty else companies

    table_col, brief_col = st.columns([1.25, 1], gap="large")
    with table_col:
        st.markdown('<div class="section-label">Metro rankings</div>', unsafe_allow_html=True)
        table = scored[
            ["rank", "short", "state", "manufacturing", "logistics", "labor", "warehouse", "growth", "score"]
        ].rename(
            columns={
                "rank": "Rank",
                "short": "Metro",
                "state": "ST",
                "manufacturing": "Manufacturing",
                "logistics": "Logistics",
                "labor": "Labor",
                "warehouse": "Warehouse",
                "growth": "Growth",
                "score": "Score",
            }
        )
        if "vacancy_pct" in scored.columns:
            vac = scored[["short", "vacancy_pct"]].rename(columns={"short": "Metro", "vacancy_pct": "Vacancy %"})
            table = table.merge(vac, on="Metro", how="left")
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            height=420,
            column_config={
                "Rank": st.column_config.NumberColumn(format="%d", width="small"),
                "Score": st.column_config.NumberColumn(format="%.1f"),
                "Vacancy %": st.column_config.NumberColumn(format="%.1f"),
            },
        )
        st.download_button(
            "Download rankings CSV",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name=f"moi_{industry_key}_{region.replace(' ', '_').lower()}.csv",
            mime="text/csv",
        )

    with brief_col:
        st.markdown('<div class="section-label">Metro brief</div>', unsafe_allow_html=True)
        vac = row["vacancy_pct"] if "vacancy_pct" in row and pd.notna(row.get("vacancy_pct")) else None
        vac_html = f" · vacancy {vac:.1f}% (model)" if vac is not None else ""
        st.markdown(
            f"""
            <div class="metro-card">
                <div class="rank-pill">RANK {int(row["rank"])} · MOI {row["score"]:.1f}</div>
                <h3>{row["short"]}</h3>
                <div class="tagline">{row["tagline"]}</div>
                <div>{row["name"]} · {row["population"]/1_000_000:.1f}M{vac_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Equal-weight", f"{weighted_pillar_score(row, {p: 0.2 for p in PILLARS}):.1f}")
        c2.metric("Companies here", f"{len(local_cos)}")
        c3.metric("Capex in metro", f"${float(local_projects['capex_b'].sum()):.1f}B" if not local_projects.empty else "$0")
        ts = load_metro_timeseries(str(row["cbsa"]))
        if not ts.empty:
            st.plotly_chart(timeseries_figure(ts, row["short"]), width="stretch", config={"displayModeBar": False})
            st.caption("Backcast of equal-weight MOI, 2021–2026. Not a live QCEW series — Wave 3 placeholder until BLS lands.")
        st.plotly_chart(radar_figure(row), width="stretch", config={"displayModeBar": False})
        st.markdown("**Why this metro**")
        for line in why_this_metro(row, industry_key):
            st.markdown(f"- {line}")
        if not local_projects.empty:
            st.markdown("**Announced capex (Wave 3)**")
            for _, proj in local_projects.iterrows():
                st.markdown(
                    f"- **{proj['company']}** · ${proj['capex_b']:.1f}B · {int(proj['jobs']):,} jobs · {proj['status']}"
                )

    st.markdown('<div class="section-label">Score contribution</div>', unsafe_allow_html=True)
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        st.plotly_chart(contribution_figure(row, industry_key, weights), width="stretch", config={"displayModeBar": False})
    with right:
        st.write(audience_take(audience, profile.label, scored))
        compare_to = st.multiselect(
            "Compare metros",
            options=[m for m in options if m != selected],
            default=[m for m in ["Indianapolis", "Columbus OH", "Atlanta"] if m in options and m != selected][:2],
            max_selections=4,
        )
        if compare_to:
            names = [selected, *compare_to]
            cmp = scored[scored["short"].isin(names)].set_index("short").reindex(names)
            fig = go.Figure()
            palette = ["#15456B", "#A84812", "#2F6A45", "#0F766E", "#7C3AED"]
            for i, pillar in enumerate(PILLARS):
                fig.add_trace(go.Bar(name=PILLAR_LABELS[pillar], x=cmp.index, y=cmp[pillar], marker_color=palette[i]))
            fig.update_layout(
                barmode="group",
                paper_bgcolor=PAPER,
                plot_bgcolor=PAPER,
                margin=dict(l=10, r=10, t=10, b=10),
                height=300,
                legend=dict(orientation="h", y=-0.2, font=dict(color=INK, size=11)),
                yaxis=dict(range=[0, 100], gridcolor=GRID, color=MUTED),
                xaxis=dict(color=INK),
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with tab_cos:
    if tab_cos.open:
        st.markdown(
            f'<div class="section-label">{profile.label} facilities · EPA TRI + USDA FSIS + OSHA ITA · click a site</div>',
            unsafe_allow_html=True,
        )
        if industry_cos.empty:
            st.info("No companies for this industry. Run `python refresh_data.py --seed-only` to ingest TRI, FSIS, and OSHA ITA.")
        else:
            if "source" not in industry_cos.columns:
                industry_cos = industry_cos.copy()
                industry_cos["source"] = "curated"
            for col in ("parent", "naics", "state", "address"):
                if col not in industry_cos.columns:
                    industry_cos[col] = ""
                industry_cos[col] = industry_cos[col].fillna("")
            if "size_class" not in industry_cos.columns:
                industry_cos["size_class"] = "Unknown"
            else:
                industry_cos["size_class"] = industry_cos["size_class"].fillna("Unknown")

            filter_row = st.container(horizontal=True, vertical_alignment="bottom")
            with filter_row:
                zone = st.selectbox(
                    "Zone",
                    options=list(ZONE_STATES.keys()),
                    index=0,
                    key="company_zone",
                    help="Eastern (default) is the Atlantic seaboard, Florida, and the OH–MI–IN–KY–TN industrial belt.",
                )
                size_choice = st.segmented_control(
                    "Company size",
                    options=list(SIZE_FILTERS),
                    default="All sizes",
                    key="company_size",
                    help="OSHA ITA annual average employees. TRI, FSIS, and curated campuses are Unknown and hidden unless All sizes is selected.",
                )
            query = st.text_input("Search company, city, parent, or metro", "", key="company_search")
            view = filter_company_view(industry_cos, zone, size_choice or "All sizes", query)
            src_counts = view["source"].fillna("unknown").value_counts() if not view.empty else pd.Series(dtype=int)
            map_view = view
            map_note = ""
            if len(view) > MAP_POINT_CAP:
                map_view = view.sample(n=MAP_POINT_CAP, random_state=1)
                map_note = f" Map plots {len(map_view):,} of {len(view):,} filtered sites."
            st.caption(
                f"{len(map_view):,} shown of {len(view):,} after filters · {len(industry_cos):,} {profile.label} nationwide. "
                + " · ".join(f"{k} {int(v):,}" for k, v in src_counts.items())
                + map_note
            )

            if view.empty:
                st.info("No facilities match this zone, size, and search. Try All US or All sizes.")
            else:
                view_ids = set(view["id"])
                if st.session_state.selected_company not in view_ids:
                    st.session_state.selected_company = view.iloc[0]["id"]

                cmap = company_map_figure(map_view, st.session_state.selected_company)
                cevent = st.plotly_chart(
                    cmap,
                    width="stretch",
                    key="company_map",
                    on_select="rerun",
                    selection_mode="points",
                    config={"displayModeBar": False},
                )
                cid = selection_id(cevent, "id")
                if cid and cid in view_ids:
                    st.session_state.selected_company = cid
                if st.session_state.selected_company not in view_ids:
                    st.session_state.selected_company = view.iloc[0]["id"]
                company = view[view["id"] == st.session_state.selected_company].iloc[0]
                headlines = news_all[news_all["company_id"] == company["id"]] if not news_all.empty else news_all
                source_label = {
                    "epa_tri": "EPA Toxics Release Inventory (2024)",
                    "usda_fsis": "USDA FSIS Meat, Poultry and Egg Product Inspection Directory",
                    "osha_ita": "OSHA Injury Tracking Application (Form 300A) · ZIP centroid",
                    "curated": "Tracked campus (public announcements)",
                }.get(str(company.get("source") or "curated"), str(company.get("source")))

                detail, roster = st.columns([1, 1.15], gap="large")
                with detail:
                    st.markdown('<div class="section-label">Selected company</div>', unsafe_allow_html=True)
                    extra = []
                    if company.get("naics"):
                        extra.append(f"NAICS {company['naics']}")
                    if company.get("parent"):
                        extra.append(str(company["parent"]))
                    size_label = str(company.get("size_class") or "Unknown")
                    employees = company.get("employees")
                    if size_label and size_label != "Unknown":
                        extra.append(size_label if pd.isna(employees) else f"{size_label} ({int(employees):,} employees)")
                    extra.append(source_label)
                    website_html = company_website_html(company)
                    st.markdown(
                        f"""
                        <div class="news-card">
                            <div class="rank-pill">{_html_text(str(company["segment"] or "Facility").upper())}</div>
                            <h3>{_html_text(company["name"])}</h3>
                            <div class="tagline">{_html_text(company["city"])} · {_html_text(company["metro"])}</div>
                            <div>{_html_text(company.get("site") or company.get("address") or "")}</div>
                            {website_html}
                            <div class="news-date">{_html_text(" · ".join(extra))}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Latest developments**")
                    if headlines.empty:
                        st.caption(
                            "No curated headline for this facility. TRI, FSIS, and OSHA ITA are federal plant/warehouse directories — "
                            "click a tracked campus (Tesla, TSMC, Hyundai, FedEx) for announcement notes."
                        )
                    else:
                        for _, item in headlines.iterrows():
                            link = f'<div class="news-date">{item["published_on"]} · {item["source"]}</div>'
                            href = f'<p><a href="{item["url"]}" target="_blank">{item["headline"]}</a></p>' if item.get("url") else f'<p>{item["headline"]}</p>'
                            st.markdown(
                                f'<div class="news-item">{link}{href}<p>{item["summary"]}</p></div>',
                                unsafe_allow_html=True,
                            )

                with roster:
                    st.markdown('<div class="section-label">Industry roster</div>', unsafe_allow_html=True)
                    show_cols = [
                        c for c in ["name", "metro", "city", "state", "naics", "size_class", "employees", "parent", "source"]
                        if c in view.columns
                    ]
                    show = view[show_cols].rename(
                        columns={
                            "name": "Company",
                            "metro": "Metro",
                            "city": "City",
                            "state": "ST",
                            "naics": "NAICS",
                            "size_class": "Size",
                            "employees": "Employees",
                            "parent": "Parent",
                            "source": "Source",
                        }
                    )
                    st.dataframe(show, hide_index=True, width="stretch", height=360)
                    st.markdown("**Announced capex in this industry**")
                    if industry_projects.empty:
                        st.caption("No Wave 3 projects tagged to this industry.")
                    else:
                        pshow = industry_projects[["company", "metro", "year", "capex_b", "jobs", "status"]].rename(
                            columns={
                                "company": "Company",
                                "metro": "Metro",
                                "year": "Year",
                                "capex_b": "Capex $B",
                                "jobs": "Jobs",
                                "status": "Status",
                            }
                        )
                        st.dataframe(pshow, hide_index=True, width="stretch", height=220)

                st.markdown('<div class="section-label">Recent headlines · tracked campuses in this industry</div>', unsafe_allow_html=True)
                industry_news = news_all[news_all["industry"] == industry_key] if not news_all.empty else news_all
                if not industry_news.empty:
                    feed = industry_news[["published_on", "company_name", "metro", "headline", "source"]].rename(
                        columns={
                            "published_on": "Date",
                            "company_name": "Company",
                            "metro": "Metro",
                            "headline": "Headline",
                            "source": "Source",
                        }
                    )
                    st.dataframe(feed, hide_index=True, width="stretch", height=240)

with tab_contact:
    if tab_contact.open:
        render_contact()

with st.expander("Methodology and Wave 3 data", icon=":material/menu_book:"):
    st.markdown(
        textwrap.dedent(
            f"""
            **MOI** = `(1 − λ) · Σ wᵢ · Pillarᵢ + λ · Cluster` with λ = {profile.cluster_blend:.0%} for {profile.label}.

            **Wave 3 (this build)**
            - Companies and public-development headlines in SQLite (`companies`, `company_news`)
            - Announced capex / jobs (`announced_projects`)
            - Industrial vacancy tilt on the Colliers Q2 2026 national 7.3% print (`industrial_market`) — not licensed submarket data
            - 2021–2026 equal-weight MOI backcast (`metrics.equal_weight_moi`)
            - Full 387-MSA expansion still waits on live BLS QCEW; this panel remains the calibrated 70 plus tracked plants

            Named US plants and warehouses are ingested from **EPA TRI 2024**, the
            **USDA FSIS MPI directory** (meat/poultry/egg plants), and **OSHA ITA**
            Form 300A establishments (NAICS 3361–3363 auto, 311/3121 food and beverage,
            3344 semiconductors, 33591 batteries, 33392 materials handling / forklifts,
            493 warehouses, plus fulfillment / distribution-center name matches).
            OSHA points use Census ZIP centroids. The companies tab defaults to the
            Eastern zone so the map stays usable.
            Run `python refresh_data.py --seed-only` to re-download files into
            `data/raw/` and reload SQLite.
            """
        )
    )
