from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_PATH = ROOT / "data/processed/world_cup_2026_predictions_final.csv"
GROUP_SIMULATION_PATH = ROOT / "data/processed/group_simulation_2026.csv"
TRAINING_PATH = ROOT / "data/processed/international_match_training.csv"
V3_SUMMARY_PATH = ROOT / "data/reports/diagnostics/calibrated_v3_summary.csv"
MODEL_HISTORY_PATH = ROOT / "data/reports/model_version_summary.csv"
CALIBRATION_PATH = ROOT / "data/reports/backtests/world_cup_backtest_calibration.csv"
CONFUSION_PATH = ROOT / "data/reports/backtests/world_cup_backtest_confusion_matrix.csv"
WORST_MATCHES_PATH = ROOT / "data/reports/diagnostics/worst_log_loss_matches.csv"
POLYMARKET_MARKETS_PATH = ROOT / "data/external/polymarket/polymarket_markets_raw.csv"
POLYMARKET_MAPPING_PATH = ROOT / "data/external/polymarket/polymarket_match_mapping.csv"
POLYMARKET_PRICES_PATH = ROOT / "data/external/polymarket/polymarket_prices.csv"
POLYMARKET_EDGES_PATH = ROOT / "data/external/polymarket/polymarket_edges.csv"
POLYMARKET_GROUP_LINKS_PATH = ROOT / "data/external/polymarket/polymarket_worldcup_group_stage_api_links.csv"
PREDICTION_MARKETS_PATH = ROOT / "data/processed/world_cup_2026_prediction_markets.csv"
ACCURACY_SUMMARY_PATH = ROOT / "data/processed/model_prediction_accuracy_summary.csv"
ACTUAL_RESULTS_PATH = ROOT / "data/actuals/world_cup_2026_actual_results.csv"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"

WINNER_MODEL = "v4_elo_ensemble_calibrated_v1"
PROBABILITY_MODEL = "calibrated_v3_floor_010_T1.2"
OUTCOMES = ["home_win", "draw", "away_win"]
USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}
TEAM_ALIASES = {
    "bosnia herzegovina": "bosnia and herzegovina",
    "cabo verde": "cape verde",
    "cote divoire": "cote d ivoire",
    "cote d'ivoire": "cote d ivoire",
    "ir iran": "iran",
    "ivory coast": "cote d ivoire",
    "korea republic": "south korea",
    "turkiye": "turkey",
    "usa": "united states",
    "us": "united states",
}


st.set_page_config(page_title="World Cup 2026 Predictor", layout="wide")


st.markdown(
    """
    <style>
    :root {
        --wc-bg: #f3f7fb;
        --wc-card: rgba(255,255,255,0.88);
        --wc-border: rgba(148,163,184,0.28);
        --wc-blue: #2563eb;
        --wc-cyan: #06b6d4;
        --wc-green: #059669;
        --wc-red: #dc2626;
        --wc-yellow: #d97706;
        --wc-ink: #0f172a;
        --wc-muted: #64748b;
    }
    .stApp {
        background:
            radial-gradient(circle at 18% 8%, rgba(37,99,235,0.14), transparent 28%),
            radial-gradient(circle at 82% 0%, rgba(6,182,212,0.16), transparent 24%),
            linear-gradient(180deg, #f8fbff 0%, var(--wc-bg) 46%, #eef4fb 100%);
    }
    .block-container {padding-top: 1.35rem; padding-bottom: 2.4rem; max-width: 1420px;}
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
    }
    [data-testid="stSidebar"] * {color: #e5eefb;}
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        border-radius: 10px;
        padding: 4px 8px;
    }
    h1, h2, h3 {letter-spacing: 0;}
    .hero-card {
        border: 1px solid rgba(37,99,235,0.22);
        border-radius: 18px;
        padding: 24px 26px;
        background:
            linear-gradient(135deg, rgba(15,23,42,0.96), rgba(30,64,175,0.86)),
            radial-gradient(circle at 80% 10%, rgba(6,182,212,0.42), transparent 32%);
        box-shadow: 0 20px 55px rgba(15,23,42,0.22);
        color: #f8fafc;
        margin-bottom: 18px;
    }
    .hero-eyebrow {font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: #93c5fd; font-weight: 800;}
    .hero-title {font-size: 2.15rem; line-height: 1.08; font-weight: 850; margin-top: 8px;}
    .hero-subtitle {font-size: 0.98rem; color: #cbd5e1; max-width: 760px; margin-top: 8px;}
    .status-row {display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px;}
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid rgba(147,197,253,0.24);
        background: rgba(15,23,42,0.38);
        color: #e0f2fe;
        border-radius: 999px;
        padding: 7px 11px;
        font-size: 0.82rem;
        font-weight: 700;
    }
    .kpi-card, .metric-card, .outcome-card, .signal-card, .score-card, .mini-match-card {
        border: 1px solid var(--wc-border);
        border-radius: 16px;
        background: var(--wc-card);
        box-shadow: 0 14px 38px rgba(15,23,42,0.08);
        backdrop-filter: blur(14px);
    }
    .kpi-card {
        padding: 16px 17px;
        min-height: 120px;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::after {
        content: "";
        position: absolute;
        inset: auto 14px 0 14px;
        height: 3px;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--accent, #2563eb), rgba(6,182,212,0.2));
    }
    .kpi-label {font-size: 0.75rem; color: var(--wc-muted); margin-bottom: 8px; font-weight: 800; text-transform: uppercase;}
    .kpi-value {font-size: 1.65rem; font-weight: 850; color: var(--wc-ink); line-height: 1.1;}
    .kpi-sub {font-size: 0.84rem; color: #475569; margin-top: 7px;}
    .match-card, .match-hero {
        border: 1px solid rgba(37,99,235,0.18);
        border-radius: 18px;
        padding: 20px;
        background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(239,246,255,0.88));
        box-shadow: 0 18px 48px rgba(15,23,42,0.10);
        margin-bottom: 14px;
    }
    .match-title {font-size: 1.55rem; font-weight: 850; color: var(--wc-ink);}
    .match-subtitle {font-size: 0.9rem; color: var(--wc-muted); margin-top: 4px;}
    .match-teams {display:flex; align-items:center; justify-content:space-between; gap: 16px;}
    .team-name {font-size: 1.65rem; font-weight: 850; color: var(--wc-ink);}
    .vs-token {font-size: 0.82rem; font-weight: 850; color: #2563eb; border: 1px solid #bfdbfe; background:#eff6ff; border-radius:999px; padding: 8px 10px;}
    .highlight-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin-top: 16px;
    }
    .highlight-group {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 14px;
        padding: 12px;
        background: rgba(255,255,255,0.64);
        min-height: 94px;
    }
    .highlight-title {
        color: #64748b;
        font-size: 0.68rem;
        font-weight: 900;
        letter-spacing: 0.03em;
        margin-bottom: 8px;
        text-transform: uppercase;
    }
    .highlight-pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    .badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 800;
        border: 1px solid transparent;
    }
    .badge-low {background: #ecfdf5; color: #047857; border-color: #a7f3d0;}
    .badge-medium {background: #fffbeb; color: #b45309; border-color: #fde68a;}
    .badge-high {background: #fef2f2; color: #b91c1c; border-color: #fecaca;}
    .badge-blue {background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe;}
    .badge-dark {background: #0f172a; color: #e2e8f0; border-color: #334155;}
    .section-title {font-size: 1.05rem; font-weight: 850; color: var(--wc-ink); margin: 20px 0 10px;}
    .outcome-card {padding: 16px; min-height: 218px;}
    .outcome-strong {border-color: rgba(5,150,105,0.70); box-shadow: 0 18px 46px rgba(5,150,105,0.18);}
    .outcome-watch {border-color: rgba(245,158,11,0.72); box-shadow: 0 18px 42px rgba(245,158,11,0.15);}
    .outcome-overpriced {border-color: rgba(220,38,38,0.64); box-shadow: 0 18px 42px rgba(220,38,38,0.13);}
    .outcome-neutral {border-color: rgba(148,163,184,0.34);}
    .outcome-title {font-size: 0.84rem; color: var(--wc-muted); font-weight: 850; text-transform: uppercase;}
    .outcome-main {font-size: 1.8rem; color: var(--wc-ink); font-weight: 900; margin-top: 7px;}
    .outcome-grid {display:grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-top: 13px;}
    .tiny-label {font-size: 0.72rem; color: var(--wc-muted); font-weight: 750;}
    .tiny-value {font-size: 1rem; color: var(--wc-ink); font-weight: 850;}
    .edge-positive {color: var(--wc-green); font-weight: 900;}
    .edge-negative {color: var(--wc-red); font-weight: 900;}
    .edge-neutral {color: #475569; font-weight: 850;}
    .score-pill {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border: 1px solid rgba(148,163,184,0.26);
        border-radius: 13px;
        padding: 11px 12px;
        background: rgba(255,255,255,0.78);
        margin-bottom: 8px;
    }
    .score-code {font-size: 1.05rem; color: var(--wc-ink); font-weight: 900;}
    .score-prob {font-size: 0.96rem; color: var(--wc-blue); font-weight: 850;}
    .score-card {padding: 18px; background: linear-gradient(135deg, #0f172a, #1e3a8a); color: #f8fafc;}
    .score-card .scoreline {font-size: 2.2rem; font-weight: 950; margin: 8px 0 2px;}
    .score-card .score-meta {color: #bfdbfe; font-size: 0.86rem; font-weight: 750;}
    .mini-match-card {padding: 15px; margin-bottom: 12px;}
    .mini-prob-track {height: 10px; border-radius:999px; background:#e2e8f0; overflow:hidden; display:flex; margin-top: 12px;}
    .mini-home {background:#2563eb;}
    .mini-draw {background:#f59e0b;}
    .mini-away {background:#ef4444;}
    .sidebar-card {
        border: 1px solid rgba(148,163,184,0.24);
        border-radius: 14px;
        padding: 12px;
        margin: 10px 0;
        background: rgba(255,255,255,0.06);
    }
    .sidebar-label {font-size: 0.7rem; color:#93c5fd; text-transform:uppercase; font-weight:850;}
    .sidebar-value {font-size:0.9rem; color:#f8fafc; font-weight:850; margin-top:3px;}
    .edge-note {
        border: 1px solid rgba(37,99,235,0.18);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(239,246,255,0.82);
        color: #334155;
        font-size: 0.88rem;
        margin: 8px 0 14px;
    }
    div[data-baseweb="select"] > div {
        border-color: #cbd5e1 !important;
        box-shadow: none !important;
    }
    div[data-baseweb="select"]:focus-within > div {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 1px rgba(37,99,235,0.20) !important;
    }
    @media (max-width: 900px) {
        .highlight-grid {grid-template-columns: repeat(2, minmax(0, 1fr));}
        .team-name {font-size: 1.3rem;}
    }
    @media (max-width: 560px) {
        .highlight-grid {grid-template-columns: 1fr;}
        .match-teams {align-items: flex-start;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_predictions() -> pd.DataFrame:
    source = PREDICTION_MARKETS_PATH if PREDICTION_MARKETS_PATH.exists() else PREDICTIONS_PATH
    frame = pd.read_csv(source)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame


@st.cache_data
def load_group_simulation() -> pd.DataFrame:
    return pd.read_csv(GROUP_SIMULATION_PATH)


@st.cache_data
def load_training() -> pd.DataFrame:
    return pd.read_csv(TRAINING_PATH)


@st.cache_data
def load_v3_summary() -> pd.DataFrame:
    return pd.read_csv(V3_SUMMARY_PATH)


@st.cache_data
def load_model_history() -> pd.DataFrame:
    return pd.read_csv(MODEL_HISTORY_PATH)


@st.cache_data
def load_calibration() -> pd.DataFrame:
    return pd.read_csv(CALIBRATION_PATH)


@st.cache_data
def load_confusion() -> pd.DataFrame:
    return pd.read_csv(CONFUSION_PATH)


@st.cache_data
def load_worst_matches() -> pd.DataFrame:
    return pd.read_csv(WORST_MATCHES_PATH)


@st.cache_data
def load_polymarket_edges() -> pd.DataFrame:
    if not POLYMARKET_EDGES_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(POLYMARKET_EDGES_PATH)


@st.cache_data
def load_polymarket_markets() -> pd.DataFrame:
    if not POLYMARKET_MARKETS_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(POLYMARKET_MARKETS_PATH)


@st.cache_data
def load_polymarket_mapping() -> pd.DataFrame:
    if not POLYMARKET_MAPPING_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(POLYMARKET_MAPPING_PATH)


@st.cache_data
def load_polymarket_group_links() -> pd.DataFrame:
    if not POLYMARKET_GROUP_LINKS_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(POLYMARKET_GROUP_LINKS_PATH)


@st.cache_data(ttl=15)
def load_accuracy_summary() -> pd.DataFrame:
    if not ACCURACY_SUMMARY_PATH.exists():
        return pd.DataFrame(
            [
                {"metric": "winner_accuracy", "display_name": "赢家预测准确率", "evaluated_matches": 0, "correct_predictions": 0, "accuracy": pd.NA, "status": "pending actual results"},
                {"metric": "scoreline_top1_accuracy", "display_name": "比分预测准确率 Top 1", "evaluated_matches": 0, "correct_predictions": 0, "accuracy": pd.NA, "status": "pending actual results"},
                {"metric": "first_goalscorer_accuracy", "display_name": "进球球员预测准确率", "evaluated_matches": 0, "correct_predictions": 0, "accuracy": pd.NA, "status": "pending scorer model/data"},
                {"metric": "corners_total_direction_accuracy", "display_name": "角球数量方向准确率", "evaluated_matches": 0, "correct_predictions": 0, "accuracy": pd.NA, "status": "pending corners model/data"},
            ]
        )
    return pd.read_csv(ACCURACY_SUMMARY_PATH)


@st.cache_data(ttl=15)
def load_actual_results() -> pd.DataFrame:
    if not ACTUAL_RESULTS_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(ACTUAL_RESULTS_PATH)


@st.cache_data
def scoreline_pool() -> pd.DataFrame:
    training = load_training().copy()
    training["date"] = pd.to_datetime(training["date"], errors="coerce")
    training = training[(training["date"].dt.year >= 1990) & training["result"].isin(OUTCOMES)]
    training["home_goals"] = training["home_score"].clip(0, 5).astype(int)
    training["away_goals"] = training["away_score"].clip(0, 5).astype(int)
    counts = training.groupby(["result", "home_goals", "away_goals"], as_index=False).size()
    counts["conditional_prob"] = counts["size"] / counts.groupby("result")["size"].transform("sum")
    return counts[["result", "home_goals", "away_goals", "conditional_prob"]]


def as_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return parsed if isinstance(parsed, list) else [parsed]
    return [value]


def normalize_team(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    return TEAM_ALIASES.get(text, text)


def best_price(levels: list[dict[str, Any]], side: str) -> float | None:
    prices = []
    for level in levels:
        try:
            price = float(level.get("price"))
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
    if not prices:
        return None
    return max(prices) if side == "bid" else min(prices)


def book_depth(levels: list[dict[str, Any]]) -> float:
    total = 0.0
    for level in levels:
        try:
            total += float(level.get("size"))
        except (TypeError, ValueError):
            continue
    return total


def percent(value: float | int | None, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}%}"


def odds(value: float | int | None) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2f}"


def match_label(row: pd.Series) -> str:
    date = row["date"].strftime("%Y-%m-%d") if not pd.isna(row["date"]) else ""
    return f"{row['match_id']} | {date} | {row['home_team']} vs {row['away_team']}"


def result_type_label(value: object) -> str:
    labels = {"home_win": "Home Win", "draw": "Draw", "away_win": "Away Win"}
    if value is None or pd.isna(value):
        return "N/A"
    return labels.get(str(value), str(value))


def predicted_result_type(row: pd.Series) -> str:
    if "prediction_result_type" in row and pd.notna(row.get("prediction_result_type")):
        return str(row["prediction_result_type"])
    values = {
        "home_win": row.get("home_win_prob"),
        "draw": row.get("draw_prob"),
        "away_win": row.get("away_win_prob"),
    }
    values = {key: value for key, value in values.items() if pd.notna(value)}
    return max(values, key=values.get) if values else ""


def actual_result_for_match(match_id: str) -> pd.Series | None:
    actuals = load_actual_results()
    if actuals.empty or "match_id" not in actuals:
        return None
    rows = actuals[actuals["match_id"].astype(str) == str(match_id)]
    return None if rows.empty else rows.iloc[0]


def actual_status_text(match_id: str) -> str:
    actual = actual_result_for_match(match_id)
    if actual is None:
        return "Scheduled"
    status = str(actual.get("status", "scheduled"))
    if status.lower() in {"ft", "finished", "complete", "completed", "final"}:
        home = actual.get("actual_home_goals")
        away = actual.get("actual_away_goals")
        if pd.notna(home) and pd.notna(away):
            return f"FT {int(home)}-{int(away)}"
        return "FT"
    return status.title()


def polymarket_url_for_match(match_id: str) -> str | None:
    links = load_polymarket_group_links()
    if links.empty or "match_id" not in links:
        return None
    rows = links[links["match_id"].astype(str) == str(match_id)]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return str(row.get("event_url") or row.get("sports_url") or "") or None


def model_pick_probability(row: pd.Series) -> float | None:
    pick = row.get("winner_model_pick")
    if pick == row.get("home_team"):
        return row.get("home_win_prob")
    if pick == row.get("away_team"):
        return row.get("away_win_prob")
    return None


def risk_badge(label: str, value: object) -> str:
    risk = "low" if pd.isna(value) else str(value).lower()
    css = "badge-high" if risk == "high" else "badge-medium" if risk == "medium" else "badge-low"
    return f"<span class='badge {css}'>{label}: {risk.title()}</span>"


def edge_class(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "edge-neutral"
    if float(value) > 0.02:
        return "edge-positive"
    if float(value) < -0.02:
        return "edge-negative"
    return "edge-neutral"


def edge_text(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{float(value):.1%}"


def display_signal(signal: object) -> str:
    mapping = {
        "Strong Value": "Strong Value · Paper Signal",
        "Watch": "Watchlist",
        "No Bet": "No Bet",
        "Overpriced": "Overpriced / Avoid",
        "Ignore": "Ignore",
        "Needs Mapping": "Needs Mapping",
        "No market": "No market",
    }
    return mapping.get(str(signal), str(signal))


def signal_css(signal: object) -> str:
    signal_text = str(signal)
    if signal_text == "Strong Value":
        return "badge-low"
    if signal_text == "Watch":
        return "badge-medium"
    if signal_text == "Overpriced":
        return "badge-high"
    return "badge-blue"


def outcome_card_css(signal: object) -> str:
    signal_text = str(signal)
    if signal_text == "Strong Value":
        return "outcome-strong"
    if signal_text == "Watch":
        return "outcome-watch"
    if signal_text == "Overpriced":
        return "outcome-overpriced"
    return "outcome-neutral"


def probability_band(metric: str, value: float | int | None) -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "Pending", "#64748b"
    number = float(value)
    thresholds = {
        "high_scoring": [(0.35, "Very High", "#dc2626"), (0.28, "High", "#f97316"), (0.20, "Medium", "#f59e0b")],
        "blowout": [(0.28, "Very High", "#dc2626"), (0.20, "High", "#f97316"), (0.12, "Medium", "#f59e0b")],
        "team_3plus": [(0.40, "Very High", "#dc2626"), (0.32, "High", "#f97316"), (0.22, "Medium", "#f59e0b")],
    }
    for cutoff, label, color in thresholds.get(metric, []):
        if number >= cutoff:
            return label, color
    return "Low", "#64748b"


def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    if number >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"${number / 1_000:.0f}K"
    return f"${number:.0f}"


def kpi_card(label: str, value: str, subtext: str = "", accent: str = "#2563eb") -> None:
    st.markdown(
        f"""
        <div class="kpi-card" style="--accent: {accent};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, pills: list[str]) -> None:
    pill_markup = "".join(f"<span class='status-pill'>{pill}</span>" for pill in pills)
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-eyebrow">World Cup 2026 Analytics</div>
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
            <div class="status-row">{pill_markup}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str) -> None:
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def market_coverage_text() -> str:
    links = load_polymarket_group_links()
    if links.empty:
        return "0 / 72"
    return f"{len(links)} / 72"


def market_last_updated() -> str:
    edges = load_polymarket_edges()
    if edges.empty or "timestamp" not in edges:
        return "Live on demand"
    timestamp = edges["timestamp"].dropna()
    return str(timestamp.max())[:19] if not timestamp.empty else "Live on demand"


def model_status_sidebar() -> None:
    st.sidebar.markdown(
        f"""
        <div class="sidebar-card">
            <div class="sidebar-label">Winner Model</div>
            <div class="sidebar-value">v4 calibrated</div>
        </div>
        <div class="sidebar-card">
            <div class="sidebar-label">Probability Model</div>
            <div class="sidebar-value">v3 floor 010 · T1.2</div>
        </div>
        <div class="sidebar-card">
            <div class="sidebar-label">Market Data</div>
            <div class="sidebar-value">Live · {market_coverage_text()} group links</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def accuracy_value(value: Any) -> str:
    return "Pending" if pd.isna(value) else percent(value)


def render_accuracy_cards() -> None:
    summary = load_accuracy_summary()
    if summary.empty:
        return
    desired = [
        "winner_accuracy",
        "scoreline_top3_accuracy",
        "first_goalscorer_accuracy",
        "corners_total_direction_accuracy",
    ]
    accents = {
        "winner_accuracy": "#2563eb",
        "scoreline_top3_accuracy": "#7c3aed",
        "first_goalscorer_accuracy": "#f59e0b",
        "corners_total_direction_accuracy": "#059669",
    }
    labels = {
        "winner_accuracy": "Winner Accuracy",
        "scoreline_top3_accuracy": "Score Accuracy",
        "first_goalscorer_accuracy": "Scorer Accuracy",
        "corners_total_direction_accuracy": "Corners Accuracy",
    }
    frame = summary[summary["metric"].isin(desired)].copy()
    frame["sort_order"] = frame["metric"].map({metric: index for index, metric in enumerate(desired)})
    frame = frame.sort_values("sort_order")
    cols = st.columns(4)
    for column, item in zip(cols, frame.itertuples(index=False)):
        evaluated = int(getattr(item, "evaluated_matches", 0))
        correct = getattr(item, "correct_predictions", pd.NA)
        if pd.isna(correct) and evaluated and not pd.isna(item.accuracy):
            correct = round(float(item.accuracy) * evaluated)
        correct = int(correct) if not pd.isna(correct) else 0
        status = getattr(item, "status", "")
        subtext = f"{correct}/{evaluated} correct" if evaluated else str(status)
        with column:
            kpi_card(labels.get(item.metric, item.display_name), accuracy_value(item.accuracy), subtext, accents.get(item.metric, "#64748b"))


def raw_prediction_table(frame: pd.DataFrame) -> pd.DataFrame:
    table = frame.copy()
    if "date" in table:
        table["date"] = pd.to_datetime(table["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return table


def probability_bar(row: pd.Series) -> go.Figure:
    labels = [row["home_team"], "Draw", row["away_team"]]
    values = [row["home_win_prob"], row["draw_prob"], row["away_win_prob"]]
    colors = ["#2563eb", "#64748b", "#dc2626"]
    fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=colors, text=[percent(v) for v in values], textposition="auto"))
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    fig.update_layout(height=240, margin=dict(l=8, r=20, t=8, b=8), showlegend=False)
    return fig


def probability_mini_bar(row: pd.Series) -> str:
    home = max(0, min(100, float(row["home_win_prob"]) * 100))
    draw = max(0, min(100, float(row["draw_prob"]) * 100))
    away = max(0, min(100, float(row["away_win_prob"]) * 100))
    return (
        "<div class='mini-prob-track'>"
        f"<div class='mini-home' style='width:{home:.1f}%'></div>"
        f"<div class='mini-draw' style='width:{draw:.1f}%'></div>"
        f"<div class='mini-away' style='width:{away:.1f}%'></div>"
        "</div>"
    )


def scoreline_distribution(row: pd.Series) -> pd.DataFrame:
    pool = scoreline_pool().copy()
    weights = {
        "home_win": row["home_win_prob"],
        "draw": row["draw_prob"],
        "away_win": row["away_win_prob"],
    }
    pool["probability"] = pool["conditional_prob"] * pool["result"].map(weights)
    grid = (
        pool.groupby(["home_goals", "away_goals"], as_index=False)["probability"]
        .sum()
        .sort_values("probability", ascending=False)
    )
    grid["probability"] = grid["probability"] / grid["probability"].sum()
    grid["scoreline"] = grid["home_goals"].astype(str) + "-" + grid["away_goals"].astype(str)
    return grid


def scoreline_metrics(scorelines: pd.DataFrame) -> dict[str, float | str]:
    expected_home = (scorelines["home_goals"] * scorelines["probability"]).sum()
    expected_away = (scorelines["away_goals"] * scorelines["probability"]).sum()
    total_goals = scorelines["home_goals"] + scorelines["away_goals"]
    goal_diff = (scorelines["home_goals"] - scorelines["away_goals"]).abs()
    over25 = scorelines.loc[total_goals > 2.5, "probability"].sum()
    btts = scorelines.loc[(scorelines["home_goals"] > 0) & (scorelines["away_goals"] > 0), "probability"].sum()
    high_scoring = scorelines.loc[total_goals >= 4, "probability"].sum()
    blowout = scorelines.loc[goal_diff >= 3, "probability"].sum()
    either_team_3plus = scorelines.loc[(scorelines["home_goals"] >= 3) | (scorelines["away_goals"] >= 3), "probability"].sum()
    top = scorelines.iloc[0]
    return {
        "expected_home_goals": expected_home,
        "expected_away_goals": expected_away,
        "over_2_5": over25,
        "under_2_5": 1 - over25,
        "btts": btts,
        "high_scoring": high_scoring,
        "blowout": blowout,
        "either_team_3plus": either_team_3plus,
        "most_likely_score": top["scoreline"],
        "most_likely_score_prob": top["probability"],
    }


def scoreline_heatmap(scorelines: pd.DataFrame, home: str, away: str) -> go.Figure:
    pivot = scorelines.pivot_table(index="home_goals", columns="away_goals", values="probability", fill_value=0)
    pivot = pivot.reindex(index=range(0, 6), columns=range(0, 6), fill_value=0)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[str(col) for col in pivot.columns],
            y=[str(idx) for idx in pivot.index],
            colorscale="Blues",
            text=[[percent(value, 0) for value in row_values] for row_values in pivot.values],
            texttemplate="%{text}",
            hovertemplate=f"{home} %{{y}} - %{{x}} {away}<br>Probability: %{{z:.1%}}<extra></extra>",
        )
    )
    fig.update_layout(
        height=390,
        margin=dict(l=20, r=20, t=24, b=20),
        xaxis_title=f"{away} goals",
        yaxis_title=f"{home} goals",
    )
    return fig


def polymarket_snapshot(match_id: str) -> pd.DataFrame:
    edges = load_polymarket_edges()
    if edges.empty or "match_id" not in edges:
        return pd.DataFrame()
    frame = edges[(edges["match_id"] == match_id) & (edges["mapping_status"] == "auto_sports_event")].copy()
    if frame.empty:
        return frame
    for column in ["model_prob", "best_bid", "best_ask", "edge", "spread", "market_liquidity"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    order = {"home_win": 0, "draw": 1, "away_win": 2}
    frame["outcome_rank"] = frame["mapped_outcome"].map(order).fillna(9)
    return frame.sort_values("outcome_rank")


def mapped_outcome_from_market(market: dict[str, Any], home_team: str, away_team: str) -> str:
    title = normalize_team(market.get("groupItemTitle") or "")
    question = normalize_team(market.get("question") or "")
    home = normalize_team(home_team)
    away = normalize_team(away_team)
    if "draw" in title or "draw" in question:
        return "draw"
    if title == home or (home and f"will {home} win" in question):
        return "home_win"
    if title == away or (away and f"will {away} win" in question):
        return "away_win"
    return ""


def model_probability_for_outcome(row: pd.Series, mapped_outcome: str) -> float | None:
    column_map = {
        "home_win": "home_win_prob",
        "draw": "draw_prob",
        "away_win": "away_win_prob",
    }
    column = column_map.get(mapped_outcome)
    if column is None:
        return None
    value = row.get(column)
    return None if pd.isna(value) else float(value)


@st.cache_data(ttl=30, show_spinner=False)
def fetch_live_clob_book(token_id: str) -> dict[str, Any]:
    response = requests.get(CLOB_BOOK_URL, params={"token_id": token_id}, headers=USER_AGENT, timeout=8)
    response.raise_for_status()
    book = response.json()
    bids = book.get("bids") or book.get("buys") or []
    asks = book.get("asks") or book.get("sells") or []
    best_bid = best_price(bids, "bid")
    best_ask = best_price(asks, "ask")
    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None,
        "spread": best_ask - best_bid if best_bid is not None and best_ask is not None else None,
        "bid_depth": book_depth(bids),
        "ask_depth": book_depth(asks),
        "last_trade_price": book.get("last_trade_price") or book.get("lastTradePrice"),
        "price_fetch_status": "live_clob",
    }


@st.cache_data(ttl=30, show_spinner=False)
def fetch_live_polymarket_event(gamma_api_url: str) -> dict[str, Any]:
    response = requests.get(gamma_api_url, headers=USER_AGENT, timeout=8)
    if response.status_code == 404:
        return {"fetch_status": "not_found", "markets": []}
    response.raise_for_status()
    payload = response.json()
    return {"fetch_status": "ok", **payload}


def live_polymarket_snapshot(row: pd.Series) -> pd.DataFrame:
    links = load_polymarket_group_links()
    if links.empty:
        return pd.DataFrame()

    link = links[links["match_id"].astype(str) == str(row["match_id"])]
    if link.empty:
        return pd.DataFrame()

    gamma_url = str(link.iloc[0].get("gamma_api_url") or "")
    if not gamma_url:
        return pd.DataFrame()

    try:
        event = fetch_live_polymarket_event(gamma_url)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(
            [
                {
                    "match_id": row["match_id"],
                    "fetch_status": f"gamma_error: {exc}",
                    "source": "live_gamma",
                }
            ]
        )

    if event.get("fetch_status") != "ok":
        return pd.DataFrame(
            [
                {
                    "match_id": row["match_id"],
                    "fetch_status": event.get("fetch_status", "unknown"),
                    "source": "live_gamma",
                    "gamma_api_url": gamma_url,
                }
            ]
        )

    records = []
    for market in event.get("markets", []):
        if market.get("sportsMarketType") != "moneyline":
            continue
        mapped_outcome = mapped_outcome_from_market(market, str(row["home_team"]), str(row["away_team"]))
        if mapped_outcome not in OUTCOMES:
            continue
        token_ids = as_list(market.get("clobTokenIds"))
        token_id = str(token_ids[0]) if token_ids else ""
        model_prob = model_probability_for_outcome(row, mapped_outcome)
        book = {
            "best_bid": pd.to_numeric(market.get("bestBid"), errors="coerce"),
            "best_ask": pd.to_numeric(market.get("bestAsk"), errors="coerce"),
            "mid_price": None,
            "spread": pd.to_numeric(market.get("spread"), errors="coerce"),
            "bid_depth": None,
            "ask_depth": None,
            "last_trade_price": market.get("lastTradePrice"),
            "price_fetch_status": "gamma_fallback",
        }
        if token_id:
            try:
                book = fetch_live_clob_book(token_id)
            except Exception:
                pass
        market_prob = book.get("best_ask")
        edge = model_prob - market_prob if model_prob is not None and market_prob is not None else None
        records.append(
            {
                "match_id": row["match_id"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "polymarket_question": market.get("question"),
                "polymarket_event_title": event.get("title"),
                "polymarket_slug": event.get("slug"),
                "polymarket_market_id": market.get("id"),
                "token_id": token_id,
                "mapped_outcome": mapped_outcome,
                "model_prob": model_prob,
                "market_prob": market_prob,
                "edge": edge,
                "market_liquidity": pd.to_numeric(market.get("liquidityNum") or market.get("liquidity"), errors="coerce"),
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source": "live_gamma_clob",
                "gamma_api_url": gamma_url,
                **book,
            }
        )

    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    order = {"home_win": 0, "draw": 1, "away_win": 2}
    frame["outcome_rank"] = frame["mapped_outcome"].map(order).fillna(9)
    frame["signal"] = frame.apply(lambda item: market_signal(item.get("edge"), item.get("spread"), item.get("market_liquidity")), axis=1)
    return frame.sort_values("outcome_rank")


def market_signal(edge: float | None, spread: float | None, liquidity: float | None) -> str:
    if edge is None or spread is None or pd.isna(edge) or pd.isna(spread):
        return "Needs Mapping"
    if liquidity is not None and not pd.isna(liquidity) and liquidity < 500:
        return "Ignore"
    if spread > 0.08:
        return "Ignore"
    if edge > 0.08 and spread < 0.03:
        return "Strong Value"
    if edge > 0.05 and spread < 0.05:
        return "Watch"
    if edge < -0.05:
        return "Overpriced"
    return "No Bet"


def polymarket_comparison_chart(frame: pd.DataFrame) -> go.Figure:
    labels = frame["mapped_outcome"].replace({"home_win": "Home win", "draw": "Draw", "away_win": "Away win"})
    fig = go.Figure()
    fig.add_bar(name="Model probability", x=labels, y=frame["model_prob"], marker_color="#2563eb")
    fig.add_bar(name="Polymarket best ask", x=labels, y=frame["best_ask"], marker_color="#f97316")
    fig.update_yaxes(range=[0, 1], tickformat=".0%")
    fig.update_layout(
        barmode="group",
        height=320,
        margin=dict(l=8, r=20, t=24, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def outcome_label(mapped_outcome: str, row: pd.Series) -> str:
    labels = {
        "home_win": f"{row['home_team']} Win",
        "draw": "Draw",
        "away_win": f"{row['away_team']} Win",
    }
    return labels.get(mapped_outcome, mapped_outcome)


def market_row_for_outcome(market: pd.DataFrame, mapped_outcome: str) -> pd.Series | None:
    if market.empty or "mapped_outcome" not in market:
        return None
    rows = market[market["mapped_outcome"] == mapped_outcome]
    return None if rows.empty else rows.iloc[0]


def outcome_card(row: pd.Series, mapped_outcome: str, market: pd.DataFrame) -> None:
    model_prob = model_probability_for_outcome(row, mapped_outcome)
    fair_odds = 1 / model_prob if model_prob and model_prob > 0 else None
    market_row = market_row_for_outcome(market, mapped_outcome)
    best_ask = market_row.get("best_ask") if market_row is not None else None
    edge = market_row.get("edge") if market_row is not None else None
    signal = market_row.get("signal") if market_row is not None else "No market"
    st.markdown(
        f"""
        <div class="outcome-card {outcome_card_css(signal)}">
            <div class="outcome-title">{outcome_label(mapped_outcome, row)}</div>
            <div class="outcome-main">{percent(model_prob)}</div>
            <span class="badge {signal_css(signal)}">{display_signal(signal)}</span>
            <div class="outcome-grid">
                <div><div class="tiny-label">Fair Odds</div><div class="tiny-value">{odds(fair_odds)}</div></div>
                <div><div class="tiny-label">Poly Ask</div><div class="tiny-value">{percent(best_ask) if best_ask is not None and not pd.isna(best_ask) else "N/A"}</div></div>
                <div><div class="tiny-label">Edge</div><div class="{edge_class(edge)}">{edge_text(edge)}</div></div>
                <div><div class="tiny-label">Spread</div><div class="tiny-value">{percent(market_row.get("spread")) if market_row is not None and not pd.isna(market_row.get("spread")) else "N/A"}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def market_signal_summary(market: pd.DataFrame) -> dict[str, Any]:
    if market.empty or "mapped_outcome" not in market:
        return {
            "best_edge": None,
            "best_outcome": "N/A",
            "avg_spread": None,
            "liquidity": None,
            "signal": "No market",
        }
    best = market["edge"].dropna().max() if "edge" in market else None
    best_outcome = "N/A"
    if best is not None and not pd.isna(best):
        best_row = market.sort_values("edge", ascending=False).iloc[0]
        best_outcome = str(best_row.get("mapped_outcome", "N/A")).replace("_", " ").title()
    spread = market["spread"].dropna().mean() if "spread" in market else None
    liquidity = market["market_liquidity"].dropna().sum() if "market_liquidity" in market else None
    signals = market["signal"].dropna().tolist() if "signal" in market else []
    signal_rank = {"Strong Value": 0, "Watch": 1, "No Bet": 2, "Overpriced": 3, "Ignore": 4, "Needs Mapping": 5}
    signal = sorted(signals, key=lambda item: signal_rank.get(item, 9))[0] if signals else "No market"
    return {"best_edge": best, "best_outcome": best_outcome, "avg_spread": spread, "liquidity": liquidity, "signal": signal}


def scoreline_pills(scorelines: pd.DataFrame, count: int = 5) -> None:
    for item in scorelines.head(count).itertuples(index=False):
        st.markdown(
            f"""
            <div class="score-pill">
                <span class="score-code">{item.scoreline.replace("-", " - ")}</span>
                <span class="score-prob">{percent(item.probability)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def edge_opportunity_card(row: pd.Series) -> None:
    edge = row.get("edge")
    signal = row.get("signal", "No Bet")
    st.markdown(
        f"""
        <div class="mini-match-card">
            <div class="tiny-label">{row.get('match_id', '')} · {row.get('mapped_outcome', '')}</div>
            <div style="font-size:1.05rem;font-weight:900;color:#0f172a;margin-top:4px;">
                {row.get('home_team', '')} vs {row.get('away_team', '')}
            </div>
            <div style="margin-top:8px;">
                <span class="badge {signal_css(signal)}">{display_signal(signal)}</span>
                <span class="{edge_class(edge)}">Edge {edge_text(edge)}</span>
            </div>
            <div class="outcome-grid">
                <div><div class="tiny-label">Model</div><div class="tiny-value">{percent(row.get('model_prob'))}</div></div>
                <div><div class="tiny-label">Best Ask</div><div class="tiny-value">{percent(row.get('best_ask'))}</div></div>
                <div><div class="tiny-label">Spread</div><div class="tiny-value">{percent(row.get('spread'))}</div></div>
                <div><div class="tiny-label">Liquidity</div><div class="tiny-value">{money(row.get('market_liquidity'))}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_match(frame: pd.DataFrame, key: str) -> pd.Series:
    known = frame[frame["home_win_prob"].notna()].copy().sort_values(["date", "match_id"])
    known["date_label"] = known["date"].dt.strftime("%Y-%m-%d")

    selector_cols = st.columns([0.24, 0.22, 0.54])
    date_options = known["date_label"].dropna().unique().tolist()
    selected_date = selector_cols[0].selectbox("Match Date", date_options, key=f"{key}_date")
    date_frame = known[known["date_label"] == selected_date].copy()

    group_options = ["All Groups"] + sorted(date_frame["group"].dropna().unique().tolist())
    selected_group = selector_cols[1].selectbox("Group", group_options, key=f"{key}_group")
    if selected_group != "All Groups":
        date_frame = date_frame[date_frame["group"] == selected_group].copy()

    labels = {}
    for index, row in date_frame.iterrows():
        label = (
            f"{actual_status_text(row['match_id'])} · {row['group']} · "
            f"{row['home_team']} vs {row['away_team']} · Model: {row['winner_model_pick']}"
        )
        labels[label] = index
    choice = selector_cols[2].selectbox("Match", list(labels.keys()), key=f"{key}_match")
    return known.loc[labels[choice]]


def match_card(row: pd.Series) -> None:
    st.markdown(
        f"""
        <div class="match-card">
            <div class="match-title">{row['home_team']} &nbsp; vs &nbsp; {row['away_team']}</div>
            <div class="match-subtitle">{row['date'].strftime('%Y-%m-%d')} · {row['group']} · {row['round']}</div>
            <div style="margin-top: 12px;">
                <span class="badge badge-low">Favorite: {row['winner_model_pick']}</span>
                {risk_badge("Confidence", row['confidence_level'])}
                {risk_badge("Draw Risk", row['draw_risk'])}
                {risk_badge("Upset Risk", row['upset_risk'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def featured_match_card(row: pd.Series, tag: str) -> None:
    st.markdown(
        f"""
        <div class="mini-match-card">
            <div class="tiny-label">{tag} · {row['group']} · {row['round']}</div>
            <div style="font-size:1.12rem;font-weight:900;color:#0f172a;margin-top:5px;">
                {row['home_team']} vs {row['away_team']}
            </div>
            <div style="margin-top:8px;">
                <span class="badge badge-blue">Favorite: {row['winner_model_pick']}</span>
                {risk_badge("Draw Risk", row['draw_risk'])}
            </div>
            {probability_mini_bar(row)}
            <div class="match-subtitle">Confidence {percent(row['winner_model_confidence'])} · Draw {percent(row['draw_prob'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(frame: pd.DataFrame) -> None:
    hero(
        "World Cup 2026 Command Center",
        "Model-driven match predictions, group simulations, scorelines and live Polymarket market edges.",
        [
            "Live Mode: Polymarket Connected",
            f"Last Snapshot: {market_last_updated()}",
            f"Covered Markets: {market_coverage_text()} Group Matches",
        ],
    )
    known = frame[frame["home_win_prob"].notna()].copy()
    simulation = load_group_simulation()

    highest_conf = known.sort_values("winner_model_confidence", ascending=False).iloc[0]
    highest_draw = known.sort_values("draw_prob", ascending=False).iloc[0]

    cards = st.columns(5)
    with cards[0]:
        kpi_card("Total Matches", f"{len(frame)}", "Full 2026 schedule", "#2563eb")
    with cards[1]:
        kpi_card("Avg Confidence", percent(known["winner_model_confidence"].mean()), "Winner model favorites", "#7c3aed")
    with cards[2]:
        kpi_card("Highest Draw Risk", percent(highest_draw["draw_prob"]), f"{highest_draw['home_team']} vs {highest_draw['away_team']}", "#f59e0b")
    with cards[3]:
        kpi_card("Polymarket Covered", market_coverage_text(), "Live game links", "#059669")
    with cards[4]:
        kpi_card("Probability Model", "v3", "Calibrated fair odds", "#64748b")

    section_header("Model Accuracy Tracker")
    render_accuracy_cards()
    st.caption("Accuracy updates from completed matches in `data/actuals/world_cup_2026_actual_results.csv` after running `scripts/update_prediction_accuracy.py`.")

    left, right = st.columns([1.2, 1])
    top_advance = simulation.sort_values("prob_advance", ascending=False).head(10)
    fig = px.bar(
        top_advance,
        x="prob_advance",
        y="team",
        color="group",
        orientation="h",
        text=top_advance["prob_advance"].map(percent),
        title="Group Advance Probability - Top Teams",
    )
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    fig.update_layout(height=420, yaxis=dict(autorange="reversed"), margin=dict(l=8, r=20, t=52, b=8))
    left.plotly_chart(fig, use_container_width=True)

    with right:
        section_header("Featured Matches")
        featured_match_card(highest_conf, "Highest Confidence")
        featured_match_card(highest_draw, "Highest Draw Risk")
        featured_match_card(known.sort_values("home_win_prob", ascending=False).iloc[0], "Biggest Favorite")

    with st.expander("Show raw data"):
        st.dataframe(raw_prediction_table(frame), width="stretch", hide_index=True)


def render_match_predictor(frame: pd.DataFrame) -> None:
    st.title("Match Predictor")
    row = selected_match(frame, "match_predictor")
    market = polymarket_snapshot(str(row["match_id"]))
    refresh_col, status_col = st.columns([0.26, 0.74])
    refresh = refresh_col.button("Refresh Polymarket Odds", key=f"refresh_poly_{row['match_id']}")
    if refresh:
        fetch_live_polymarket_event.clear()
        fetch_live_clob_book.clear()

    with st.spinner("Loading live Polymarket odds..."):
        live_market = live_polymarket_snapshot(row)
    if not live_market.empty:
        market = live_market

    summary = market_signal_summary(market)
    if refresh:
        st.success(f"Odds refreshed · {row['match_id']} · {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    status_col.caption(
        f"Market source: {'live' if not market.empty and 'mapped_outcome' in market else 'pending'} · "
        f"Last refresh: {market_last_updated()}"
    )

    signal_badge = summary["signal"]
    pick_prob = model_pick_probability(row)
    predicted_type = predicted_result_type(row)
    actual_status = actual_status_text(str(row["match_id"]))
    polymarket_url = polymarket_url_for_match(str(row["match_id"]))
    st.markdown(
        f"""
        <div class="match-hero">
            <div class="match-subtitle">{row['group']} · {row['round']} · {row['date'].strftime('%Y-%m-%d')}</div>
            <div class="match-teams">
                <div class="team-name">{row['home_team']}</div>
                <div class="vs-token">VS</div>
                <div class="team-name" style="text-align:right;">{row['away_team']}</div>
            </div>
            <div class="highlight-grid">
                <div class="highlight-group">
                    <div class="highlight-title">Model Forecast</div>
                    <div class="highlight-pill-row">
                        <span class="badge badge-blue">Pick: {row['winner_model_pick']}</span>
                        <span class="badge badge-dark">{result_type_label(predicted_type)}</span>
                        <span class="badge badge-blue">{percent(pick_prob)}</span>
                    </div>
                </div>
                <div class="highlight-group">
                    <div class="highlight-title">Match Status</div>
                    <div class="highlight-pill-row">
                        <span class="badge badge-dark">{actual_status}</span>
                    </div>
                </div>
                <div class="highlight-group">
                    <div class="highlight-title">Risk Profile</div>
                    <div class="highlight-pill-row">
                        {risk_badge("Confidence", row['confidence_level'])}
                        {risk_badge("Draw", row['draw_risk'])}
                        {risk_badge("Upset", row['upset_risk'])}
                    </div>
                </div>
                <div class="highlight-group">
                    <div class="highlight-title">Market Edge</div>
                    <div class="highlight-pill-row">
                        <span class="badge {signal_css(signal_badge)}">{display_signal(signal_badge)}</span>
                        <span class="badge badge-dark">{summary['best_outcome']}</span>
                    </div>
                </div>
            </div>
            <div class="match-subtitle" style="margin-top:10px;">
                Model probabilities: {row['home_team']} {percent(row['home_win_prob'])} · Draw {percent(row['draw_prob'])} · {row['away_team']} {percent(row['away_win_prob'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    model_cols = st.columns(4)
    with model_cols[0]:
        kpi_card("Model Prediction", str(row["winner_model_pick"]), f"{result_type_label(predicted_type)} · {percent(pick_prob)}", "#2563eb")
    with model_cols[1]:
        kpi_card("Confidence", str(row["confidence_level"]).title(), f"Winner model {percent(row['winner_model_confidence'])}", "#7c3aed")
    with model_cols[2]:
        kpi_card("Actual Result", actual_status, "Updates accuracy when FT", "#059669" if actual_status.startswith("FT") else "#64748b")
    with model_cols[3]:
        if polymarket_url:
            st.link_button("Open Polymarket Event", polymarket_url, width="stretch")
        else:
            kpi_card("Polymarket Event", "N/A", "No event link", "#64748b")

    section_header("Outcome Cards")
    st.markdown(
        """
        <div class="edge-note">
            Edge = model probability - Polymarket best ask. Positive edge means the model thinks the market may be underpricing that outcome.
            Signals are for paper trading and monitoring only, not betting advice.
            Confidence measures how certain the model is about the match result; Market Edge Signal measures whether the current market price looks cheap relative to the model.
        </div>
        """,
        unsafe_allow_html=True,
    )
    outcome_cols = st.columns(3)
    for column, outcome in zip(outcome_cols, OUTCOMES):
        with column:
            outcome_card(row, outcome, market if "mapped_outcome" in market else pd.DataFrame())

    section_header("Market Edge Signal Snapshot")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Best Edge", edge_text(summary["best_edge"]))
    metric_cols[1].metric("Best Outcome", summary["best_outcome"])
    metric_cols[2].metric("Avg Spread", percent(summary["avg_spread"]) if summary["avg_spread"] is not None else "N/A")
    metric_cols[3].metric("Signal", display_signal(summary["signal"]))

    chart_left, score_right = st.columns([1.35, 0.75])
    with chart_left:
        if not market.empty and "mapped_outcome" in market:
            st.plotly_chart(polymarket_comparison_chart(market), use_container_width=True)
        else:
            st.plotly_chart(probability_bar(row), use_container_width=True)

    scorelines = scoreline_distribution(row)
    with score_right:
        section_header("Top Scorelines")
        scoreline_pills(scorelines)

    section_header("Polymarket Market Snapshot")
    if market.empty:
        st.info("No matched Polymarket 1X2 market snapshot for this match yet.")
    elif "mapped_outcome" not in market:
        status = market.iloc[0].get("fetch_status", "unknown")
        gamma_url = market.iloc[0].get("gamma_api_url", "")
        st.info(f"Polymarket market is not available yet for this match. Status: {status}")
        if gamma_url:
            st.caption(gamma_url)
    else:
        latest_timestamp = market["timestamp"].dropna().max() if "timestamp" in market else ""
        source = market["source"].dropna().iloc[0] if "source" in market and market["source"].notna().any() else "snapshot"
        st.caption(f"Paper trading only. Source: {source}. Last refreshed: {latest_timestamp}")
        display = market[
            [
                "mapped_outcome",
                "model_prob",
                "best_bid",
                "best_ask",
                "edge",
                "spread",
                "market_liquidity",
                "signal",
            ]
        ].copy()
        for column in ["model_prob", "best_bid", "best_ask", "edge", "spread"]:
            display[column] = display[column].map(percent)
        with st.expander("Show raw Polymarket rows"):
            st.dataframe(display, width="stretch", hide_index=True)

    with st.expander("Show raw data"):
        st.dataframe(raw_prediction_table(pd.DataFrame([row])), width="stretch", hide_index=True)


def render_group_simulation() -> None:
    st.title("Group Simulation")
    simulation = load_group_simulation()
    selected_group = st.selectbox("Group", sorted(simulation["group"].unique().tolist()))
    group_frame = simulation[simulation["group"] == selected_group].sort_values("prob_advance", ascending=False)

    cards = st.columns(4)
    leader = group_frame.iloc[0]
    likely_first = group_frame.sort_values("prob_group_1st", ascending=False).iloc[0]
    most_at_risk = group_frame.sort_values("prob_eliminated", ascending=False).iloc[0]
    with cards[0]:
        kpi_card("Teams", str(len(group_frame)), selected_group, "#2563eb")
    with cards[1]:
        kpi_card("Most Likely 1st", likely_first["team"], percent(likely_first["prob_group_1st"]), "#7c3aed")
    with cards[2]:
        kpi_card("Top Advance", leader["team"], percent(leader["prob_advance"]), "#059669")
    with cards[3]:
        kpi_card("Most At Risk", most_at_risk["team"], f"Elim {percent(most_at_risk['prob_eliminated'])}", "#dc2626")

    left, right = st.columns([1, 1])
    advance_fig = px.bar(
        group_frame,
        x="prob_advance",
        y="team",
        orientation="h",
        text=group_frame["prob_advance"].map(percent),
        title=f"{selected_group} Advance Probability",
        color="prob_advance",
        color_continuous_scale="Blues",
    )
    advance_fig.update_xaxes(range=[0, 1], tickformat=".0%")
    advance_fig.update_layout(height=360, yaxis=dict(autorange="reversed"), margin=dict(l=8, r=20, t=52, b=8), showlegend=False)
    left.plotly_chart(advance_fig, use_container_width=True)

    rank_long = group_frame.melt(
        id_vars=["team"],
        value_vars=["prob_group_1st", "prob_group_2nd", "prob_group_3rd", "prob_group_4th"],
        var_name="rank",
        value_name="probability",
    )
    rank_long["rank"] = rank_long["rank"].replace(
        {
            "prob_group_1st": "1st",
            "prob_group_2nd": "2nd",
            "prob_group_3rd": "3rd",
            "prob_group_4th": "4th",
        }
    )
    rank_fig = px.bar(
        rank_long,
        x="probability",
        y="team",
        color="rank",
        orientation="h",
        title=f"{selected_group} Rank Probability",
        color_discrete_map={"1st": "#2563eb", "2nd": "#38bdf8", "3rd": "#f59e0b", "4th": "#ef4444"},
    )
    rank_fig.update_xaxes(range=[0, 1], tickformat=".0%")
    rank_fig.update_layout(height=360, yaxis=dict(autorange="reversed"), margin=dict(l=8, r=20, t=52, b=8))
    right.plotly_chart(rank_fig, use_container_width=True)

    scatter = px.scatter(
        simulation,
        x="avg_points",
        y="prob_advance",
        color="group",
        hover_name="team",
        title="Avg Points vs Advance Probability",
    )
    scatter.update_yaxes(range=[0, 1], tickformat=".0%")
    scatter.update_layout(height=420, margin=dict(l=8, r=20, t=52, b=8))
    st.plotly_chart(scatter, use_container_width=True)

    with st.expander("Show raw data"):
        st.dataframe(group_frame, width="stretch", hide_index=True)


def render_score_predictor(frame: pd.DataFrame) -> None:
    st.title("Score Predictor")
    row = selected_match(frame, "score_predictor")
    match_card(row)
    polymarket_url = polymarket_url_for_match(str(row["match_id"]))
    link_cols = st.columns([0.24, 0.76])
    with link_cols[0]:
        if polymarket_url:
            st.link_button("Open Polymarket Event", polymarket_url, width="stretch")
        else:
            kpi_card("Polymarket Event", "N/A", "No event link", "#64748b")
    with link_cols[1]:
        st.caption("Use this link to compare scoreline and big-score risk with the related Polymarket match page.")

    scorelines = scoreline_distribution(row)
    metrics = scoreline_metrics(scorelines)
    home_goals, away_goals = str(metrics["most_likely_score"]).split("-")

    metric_cols = st.columns(5)
    with metric_cols[0]:
        kpi_card(f"{row['home_team']} xG", f"{metrics['expected_home_goals']:.2f}", "Expected goals", "#2563eb")
    with metric_cols[1]:
        kpi_card(f"{row['away_team']} xG", f"{metrics['expected_away_goals']:.2f}", "Expected goals", "#ef4444")
    with metric_cols[2]:
        lean = "Over lean" if metrics["over_2_5"] > 0.52 else "Nearly balanced"
        kpi_card("Over 2.5", percent(metrics["over_2_5"]), lean, "#f59e0b")
    with metric_cols[3]:
        lean = "Under lean" if metrics["under_2_5"] > 0.52 else "Nearly balanced"
        kpi_card("Under 2.5", percent(metrics["under_2_5"]), lean, "#06b6d4")
    with metric_cols[4]:
        kpi_card("BTTS", percent(metrics["btts"]), "Both teams score", "#7c3aed")

    big_score_cols = st.columns(3)
    high_scoring_band, high_scoring_color = probability_band("high_scoring", metrics["high_scoring"])
    blowout_band, blowout_color = probability_band("blowout", metrics["blowout"])
    team_3plus_band, team_3plus_color = probability_band("team_3plus", metrics["either_team_3plus"])
    with big_score_cols[0]:
        kpi_card("High-Scoring Game", percent(metrics["high_scoring"]), f"{high_scoring_band} · Total goals 4+", high_scoring_color)
    with big_score_cols[1]:
        kpi_card("Blowout Risk", percent(metrics["blowout"]), f"{blowout_band} · Win margin 3+", blowout_color)
    with big_score_cols[2]:
        kpi_card("Team 3+ Goals", percent(metrics["either_team_3plus"]), f"{team_3plus_band} · Either team scores 3+", team_3plus_color)

    left, right = st.columns([1.2, 0.8])
    left.plotly_chart(scoreline_heatmap(scorelines, row["home_team"], row["away_team"]), use_container_width=True)

    with right:
        st.markdown(
            f"""
            <div class="score-card">
                <div class="tiny-label" style="color:#93c5fd;">Most Likely Score</div>
                <div class="scoreline">{row['home_team']} {home_goals} - {away_goals} {row['away_team']}</div>
                <div class="score-meta">{percent(metrics['most_likely_score_prob'])} model probability</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        section_header("Top 5 Scorelines")
        scoreline_pills(scorelines)

    with st.expander("Show raw scoreline distribution"):
        raw = scorelines.copy()
        raw["probability"] = raw["probability"].map(percent)
        st.dataframe(raw[["scoreline", "home_goals", "away_goals", "probability"]], width="stretch", hide_index=True)


def render_model_info() -> None:
    st.title("Model Info")
    history = load_model_history()
    selected = history[history["version"] == PROBABILITY_MODEL].iloc[0]

    cards = st.columns(4)
    cards[0].metric("Accuracy", percent(selected["world_cup_backtest_avg_top1_accuracy"]))
    cards[1].metric("Log Loss", f"{selected['world_cup_backtest_avg_log_loss']:.3f}")
    cards[2].metric("Brier", f"{selected['world_cup_backtest_avg_brier']:.3f}")
    cards[3].metric("Avg Draw Prob", percent(selected["world_cup_backtest_avg_draw_prob"]))

    st.subheader("Frozen Model Stack")
    st.table(
        pd.DataFrame(
            [
                {"item": "Winner model", "value": WINNER_MODEL},
                {"item": "Probability model", "value": PROBABILITY_MODEL},
                {"item": "Note", "value": "Draw is a risk signal, not final pick."},
            ]
        )
    )


def render_model_diagnostics(frame: pd.DataFrame) -> None:
    st.title("Model Diagnostics")
    summary = load_v3_summary()
    calibration = load_calibration()
    confusion = load_confusion()
    worst = load_worst_matches()

    metrics = summary.melt(
        id_vars=["model"],
        value_vars=["top1_accuracy", "log_loss", "brier_score"],
        var_name="metric",
        value_name="value",
    )
    fig = px.bar(metrics, x="model", y="value", color="metric", barmode="group", title="Model Metrics Comparison")
    fig.update_layout(height=430, margin=dict(l=8, r=20, t=52, b=110), xaxis_tickangle=-35)
    st.plotly_chart(fig, use_container_width=True)

    selected_model = st.selectbox("Calibration Model", sorted(calibration["model"].unique().tolist()), index=0)
    cal = calibration[(calibration["model"] == selected_model) & (calibration["calibration_type"].isin(OUTCOMES))]
    cal_fig = px.line(
        cal,
        x="avg_predicted_prob",
        y="actual_rate",
        color="calibration_type",
        markers=True,
        title=f"Calibration Curve - {selected_model}",
    )
    cal_fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line=dict(color="#94a3b8", dash="dash")))
    cal_fig.update_xaxes(range=[0, 1], tickformat=".0%")
    cal_fig.update_yaxes(range=[0, 1], tickformat=".0%")
    cal_fig.update_layout(height=420, margin=dict(l=8, r=20, t=52, b=8))
    st.plotly_chart(cal_fig, use_container_width=True)

    left, right = st.columns([1, 1])
    confusion_model = selected_model if selected_model in set(confusion["model"]) else WINNER_MODEL
    cm = confusion[confusion["model"] == confusion_model].pivot_table(index="actual", columns="predicted", values="count", aggfunc="sum", fill_value=0)
    left.plotly_chart(
        px.imshow(cm, text_auto=True, color_continuous_scale="Blues", title=f"Confusion Matrix - {confusion_model}"),
        use_container_width=True,
    )
    draw_fig = px.histogram(frame[frame["draw_prob"].notna()], x="draw_prob", nbins=20, title="Draw Probability Distribution")
    draw_fig.update_xaxes(tickformat=".0%")
    right.plotly_chart(draw_fig, use_container_width=True)

    with st.expander("Worst predictions"):
        st.dataframe(worst.head(50), width="stretch", hide_index=True)
    with st.expander("Show model summary data"):
        st.dataframe(summary, width="stretch", hide_index=True)


def render_market_edge_scanner() -> None:
    st.title("Market Edge Scanner")
    st.caption("Paper trading only. Calibrated match probabilities vs Polymarket best ask.")

    edges = load_polymarket_edges()
    markets = load_polymarket_markets()
    mapping = load_polymarket_mapping()

    if edges.empty:
        st.warning("No Polymarket data found yet. Run `scripts/update_polymarket_data.py` to fetch Gamma markets and CLOB prices.")
        return

    edges = edges.copy()
    for column in ["best_bid", "best_ask", "mid_price", "spread", "market_liquidity", "model_prob", "edge"]:
        if column in edges:
            edges[column] = pd.to_numeric(edges[column], errors="coerce")

    liquidity_threshold = st.slider("Minimum Liquidity", min_value=0, max_value=2_000_000, value=500, step=500)
    spread_threshold = st.slider("Maximum Spread", min_value=0.001, max_value=0.100, value=0.050, step=0.001, format="%.3f")

    priced = edges[(edges["market_liquidity"].fillna(0) >= liquidity_threshold) & (edges["spread"].fillna(1) <= spread_threshold)].copy()
    comparable = priced[priced["model_prob"].notna() & priced["best_ask"].notna()].copy()
    needs_mapping = priced[priced["model_prob"].isna()].copy()

    best_edge = comparable["edge"].max() if not comparable.empty else None
    avg_spread = comparable["spread"].mean() if not comparable.empty else None
    last_updated = str(comparable["timestamp"].dropna().max())[:19] if "timestamp" in comparable and comparable["timestamp"].notna().any() else "Live on demand"
    cards = st.columns(5)
    with cards[0]:
        kpi_card("Markets Covered", market_coverage_text(), "Group match links", "#2563eb")
    with cards[1]:
        kpi_card("Strong Value", str(int(comparable["signal"].eq("Strong Value").sum())), "Current filters", "#059669")
    with cards[2]:
        kpi_card("Best Edge", edge_text(best_edge), "Highest positive edge", "#22c55e")
    with cards[3]:
        kpi_card("Avg Spread", percent(avg_spread) if avg_spread is not None else "N/A", "Execution friction", "#f59e0b")
    with cards[4]:
        kpi_card("Last Updated", last_updated[-8:] if last_updated != "Live on demand" else "Live", last_updated[:10], "#64748b")

    if comparable.empty:
        st.info(
            "No comparable value-betting rows yet. Current discovered markets are mostly tournament-winner markets, "
            "while the dashboard currently has match, group-advance, and group-winner probabilities. Add confirmed mappings "
            "in `polymarket_match_mapping.csv` before calculating edge."
        )
    else:
        comparable["edge_display"] = comparable["edge"].map(percent)
        comparable["model_prob_display"] = comparable["model_prob"].map(percent)
        comparable["best_ask_display"] = comparable["best_ask"].map(percent)
        comparable["spread_display"] = comparable["spread"].map(percent)
        comparable["paper_signal_display"] = comparable["signal"].map(display_signal)
        signal_order = {"Strong Value": 0, "Watch": 1, "No Bet": 2, "Overpriced": 3, "Ignore": 4, "Needs Mapping": 5}
        comparable["signal_rank"] = comparable["signal"].map(signal_order).fillna(9)
        comparable = comparable.sort_values(["signal_rank", "edge"], ascending=[True, False])

        section_header("Top Edge Opportunities")
        top_cards = comparable[comparable["signal"].isin(["Strong Value", "Watch"])].head(6)
        if top_cards.empty:
            st.write("No positive edge opportunities under current filters.")
        else:
            cols = st.columns(3)
            for index, item in enumerate(top_cards.itertuples(index=False)):
                with cols[index % 3]:
                    edge_opportunity_card(pd.Series(item._asdict()))

        section_header("Edge Radar")
        fig = px.bar(
            comparable.head(20),
            x="edge",
            y="polymarket_question",
            color="signal",
            orientation="h",
            text="edge_display",
            title="Model Edge vs Polymarket Best Ask",
        )
        fig.update_xaxes(tickformat=".0%")
        fig.update_layout(height=520, yaxis=dict(autorange="reversed"), margin=dict(l=8, r=20, t=52, b=8))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Show full edge table"):
            st.dataframe(
                comparable[
                    [
                        "match_id",
                        "home_team",
                        "away_team",
                        "polymarket_question",
                        "outcome_type",
                        "mapped_outcome",
                        "model_prob_display",
                        "best_ask_display",
                        "edge_display",
                        "spread_display",
                        "market_liquidity",
                        "paper_signal_display",
                    ]
                ],
                width="stretch",
                hide_index=True,
            )

    section_header("Markets Needing Mapping")
    if needs_mapping.empty:
        st.write("No unmapped priced markets under current filters.")
    else:
        display = needs_mapping[
            [
                "polymarket_question",
                "mapped_outcome",
                "best_bid",
                "best_ask",
                "spread",
                "market_liquidity",
                "mapping_status",
                "notes",
            ]
        ].copy()
        for column in ["best_bid", "best_ask", "spread"]:
            display[column] = display[column].map(lambda value: percent(value) if not pd.isna(value) else "")
        with st.expander("Show unmapped markets"):
            st.dataframe(display, width="stretch", hide_index=True)

    with st.expander("Mapping workflow"):
        st.write(
            "Use Gamma markets to identify the market, confirm the rule text, then edit the mapping file. "
            "Only set `mapping_status` to `mapped` when the market outcome matches one of the supported model outputs."
        )
        st.table(
            pd.DataFrame(
                [
                    {"outcome_type": "match_1x2", "mapped_outcome": "home_win / draw / away_win", "model source": "calibrated_v3 match probability"},
                    {"outcome_type": "team_qualifies", "mapped_outcome": "team name", "model source": "group simulation prob_advance"},
                    {"outcome_type": "team_wins_group", "mapped_outcome": "team name", "model source": "group simulation prob_group_1st"},
                ]
            )
        )

    with st.expander("Show raw Polymarket markets"):
        st.dataframe(markets, width="stretch", hide_index=True)
    with st.expander("Show mapping file"):
        st.dataframe(mapping, width="stretch", hide_index=True)
    with st.expander("Show raw edge rows"):
        st.dataframe(edges, width="stretch", hide_index=True)


def main() -> None:
    frame = load_predictions()
    st.sidebar.title("World Cup Predictor")
    page_options = {
        "🏠 Overview": "Overview",
        "⚽ Match Predictor": "Match Predictor",
        "🏆 Group Simulation": "Group Simulation",
        "🎯 Score Predictor": "Score Predictor",
        "📈 Market Edge Scanner": "Market Edge Scanner",
        "🧠 Model Info": "Model Info",
        "🧪 Diagnostics": "Model Diagnostics",
    }
    selected_page = st.sidebar.radio(
        "Page",
        list(page_options.keys()),
    )
    page = page_options[selected_page]
    model_status_sidebar()

    if page == "Overview":
        render_overview(frame)
    elif page == "Match Predictor":
        render_match_predictor(frame)
    elif page == "Group Simulation":
        render_group_simulation()
    elif page == "Score Predictor":
        render_score_predictor(frame)
    elif page == "Market Edge Scanner":
        render_market_edge_scanner()
    elif page == "Model Info":
        render_model_info()
    else:
        render_model_diagnostics(frame)


if __name__ == "__main__":
    main()
