from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests


DEFAULT_PREDICTIONS = Path("data/processed/world_cup_2026_predictions_final.csv")
DEFAULT_GROUP_SIMULATION = Path("data/processed/group_simulation_2026.csv")
DEFAULT_OUTPUT_DIR = Path("data/external/polymarket")

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"
POLYMARKET_BASE_URL = "https://polymarket.com"
WORLD_CUP_GAMES_URLS = [
    "https://polymarket.com/sports/world-cup/games",
    "https://polymarket.com/sports/world-cup/games/week/1",
]

DEFAULT_SEARCH_TERMS = [
    "World Cup",
    "FIFA World Cup",
    "Brazil World Cup",
    "Argentina World Cup",
    "France World Cup",
    "England World Cup",
    "Spain World Cup",
    "Germany World Cup",
    "Mexico World Cup",
    "United States World Cup",
]
RELEVANCE_TERMS = [
    "world cup",
    "fifa",
    "brazil",
    "argentina",
    "france",
    "england",
    "spain",
    "germany",
    "mexico",
    "united states",
]

MAPPING_COLUMNS = [
    "match_id",
    "home_team",
    "away_team",
    "polymarket_market_id",
    "polymarket_question",
    "outcome_type",
    "token_id",
    "mapped_outcome",
    "market_slug",
    "market_liquidity",
    "market_end_date",
    "mapping_status",
    "notes",
]

EVENT_COLUMNS = [
    "event_name",
    "event_url",
    "event_slug",
    "start_date",
    "home_team",
    "away_team",
    "source_page",
    "fetch_status",
]

USER_AGENT = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )
}

TEAM_ALIASES = {
    "bosnia herzegovina": "bosnia and herzegovina",
    "bosnia-herzegovina": "bosnia and herzegovina",
    "cabo verde": "cape verde",
    "cote divoire": "cote d ivoire",
    "cote d'ivoire": "cote d ivoire",
    "czech republic": "czechia",
    "curacao": "curacao",
    "curaaao": "curacao",
    "ivory coast": "cote d ivoire",
    "ir iran": "iran",
    "iran": "iran",
    "korea republic": "south korea",
    "south korea": "south korea",
    "turkiye": "turkey",
    "turkey": "turkey",
    "usa": "united states",
    "us": "united states",
    "united states": "united states",
}


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


def as_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_team(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    return TEAM_ALIASES.get(text, text)


def fetch_text(url: str, timeout: int) -> str:
    response = requests.get(url, headers=USER_AGENT, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_gamma_market_search(search_terms: list[str], limit: int, timeout: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for term in search_terms:
        response = requests.get(GAMMA_URL, params={"search": term, "limit": limit}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        markets = payload if isinstance(payload, list) else payload.get("markets", [])

        for market in markets:
            market_id = str(market.get("id") or market.get("conditionId") or market.get("slug"))
            if market_id in seen:
                continue
            seen.add(market_id)
            question = str(market.get("question") or "")
            slug = str(market.get("slug") or "")
            haystack = f"{question} {slug}".lower()
            if not any(term in haystack for term in RELEVANCE_TERMS):
                continue
            clob_ids = as_list(market.get("clobTokenIds"))
            outcomes = as_list(market.get("outcomes"))
            rows.append(
                {
                    "market_id": market_id,
                    "question": question,
                    "slug": slug,
                    "conditionId": market.get("conditionId"),
                    "tokens": json.dumps(market.get("tokens", []), ensure_ascii=False),
                    "clobTokenIds": json.dumps(clob_ids, ensure_ascii=False),
                    "outcomes": json.dumps(outcomes, ensure_ascii=False),
                    "active": bool(market.get("active")),
                    "closed": bool(market.get("closed")),
                    "volume": as_float(market.get("volume") or market.get("volumeNum")),
                    "liquidity": as_float(market.get("liquidity") or market.get("liquidityNum")),
                    "endDate": market.get("endDate") or market.get("endDateIso"),
                    "search_term": term,
                }
            )
    return pd.DataFrame(rows)


def discover_world_cup_game_events(timeout: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source_url in WORLD_CUP_GAMES_URLS:
        try:
            html = fetch_text(source_url, timeout)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "event_name": "",
                    "event_url": "",
                    "event_slug": "",
                    "start_date": "",
                    "home_team": "",
                    "away_team": "",
                    "source_page": source_url,
                    "fetch_status": f"error: {exc}",
                }
            )
            continue

        event_paths = sorted(
            {
                path.rstrip("/")
                for path in re.findall(r"/sports/world-cup/fifwc-[a-z0-9-]+-2026-\d\d-\d\d", html)
            }
        )
        for path in event_paths:
            if path in seen:
                continue
            seen.add(path)
            slug = path.rsplit("/", 1)[-1]
            rows.append(
                {
                    "event_name": "",
                    "event_url": f"{POLYMARKET_BASE_URL}{path}",
                    "event_slug": slug,
                    "start_date": slug[-10:],
                    "home_team": "",
                    "away_team": "",
                    "source_page": source_url,
                    "fetch_status": "listed",
                }
            )

    return pd.DataFrame(rows, columns=EVENT_COLUMNS).drop_duplicates(subset=["event_url"])


def event_team_names_from_json_ld(html: str) -> tuple[str, str, str]:
    for match in re.finditer(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    ):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if payload.get("@type") != "SportsEvent":
            continue
        home = payload.get("homeTeam") or {}
        away = payload.get("awayTeam") or {}
        return (
            str(payload.get("name") or ""),
            str(home.get("name") or ""),
            str(away.get("name") or ""),
        )
    return "", "", ""


def iter_moneyline_market_objects(html: str) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in re.finditer(r'\{"id":"\d+","question":"', html):
        try:
            market, _ = json.JSONDecoder().raw_decode(html[match.start() :])
        except json.JSONDecodeError:
            continue
        if market.get("sportsMarketType") != "moneyline":
            continue
        key = (str(market.get("id") or ""), str(market.get("slug") or ""))
        if key in seen:
            continue
        seen.add(key)
        markets.append(market)
    return markets


def market_object_to_row(market: dict[str, Any]) -> dict[str, Any]:
    token_ids = as_list(market.get("clobTokenIds"))
    return {
        "polymarket_market_id": str(market.get("id") or ""),
        "polymarket_question": str(market.get("question") or ""),
        "market_slug": str(market.get("slug") or ""),
        "market_liquidity": as_float(market.get("liquidityNum") or market.get("liquidity")),
        "market_end_date": market.get("endDateIso") or market.get("endDate") or "",
        "token_id": str(token_ids[0]) if token_ids else "",
        "mapped_outcome": "",
        "group_item_title": str(market.get("groupItemTitle") or ""),
        "best_bid_from_page": market.get("bestBid"),
        "best_ask_from_page": market.get("bestAsk"),
        "market_description": str(market.get("description") or ""),
    }


def event_slug_from_market_slug(slug: str) -> str:
    match = re.match(r"^(fifwc-.+-2026-\d\d-\d\d)-[^-]+$", slug)
    return match.group(1) if match else slug


def discover_world_cup_games_from_listing(timeout: int) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    event_records: dict[str, dict[str, Any]] = {}
    market_rows_by_event: dict[str, list[dict[str, Any]]] = {}

    for source_url in WORLD_CUP_GAMES_URLS:
        try:
            html = fetch_text(source_url, timeout)
        except Exception as exc:  # noqa: BLE001
            event_records[f"fetch_error_{source_url}"] = {
                "event_name": "",
                "event_url": "",
                "event_slug": "",
                "start_date": "",
                "home_team": "",
                "away_team": "",
                "source_page": source_url,
                "fetch_status": f"error: {exc}",
            }
            continue

        event_paths = sorted(
            {
                path.rstrip("/")
                for path in re.findall(r"/sports/world-cup/fifwc-[a-z0-9-]+-2026-\d\d-\d\d", html)
            }
        )
        for path in event_paths:
            slug = path.rsplit("/", 1)[-1]
            event_records.setdefault(
                slug,
                {
                    "event_name": "",
                    "event_url": f"{POLYMARKET_BASE_URL}{path}",
                    "event_slug": slug,
                    "start_date": slug[-10:],
                    "home_team": "",
                    "away_team": "",
                    "source_page": source_url,
                    "fetch_status": "listed",
                },
            )

        for market in iter_moneyline_market_objects(html):
            event_slug = event_slug_from_market_slug(str(market.get("slug") or ""))
            if not event_slug.startswith("fifwc-"):
                continue
            market_rows_by_event.setdefault(event_slug, []).append(market_object_to_row(market))

    for slug, market_rows in market_rows_by_event.items():
        event_records.setdefault(
            slug,
            {
                "event_name": "",
                "event_url": f"{POLYMARKET_BASE_URL}/sports/world-cup/{slug}",
                "event_slug": slug,
                "start_date": slug[-10:],
                "home_team": "",
                "away_team": "",
                "source_page": "market_object",
                "fetch_status": "listed",
            },
        )
        titles = [str(row.get("group_item_title") or "") for row in market_rows]
        team_titles = [title for title in titles if title and not title.lower().startswith("draw")]
        draw_titles = [title for title in titles if title.lower().startswith("draw")]
        if len(team_titles) >= 2:
            event_records[slug]["home_team"] = team_titles[0]
            event_records[slug]["away_team"] = team_titles[1]
        if draw_titles and not event_records[slug]["event_name"]:
            event_records[slug]["event_name"] = draw_titles[0].replace("Draw (", "").rstrip(")")
        elif len(team_titles) >= 2 and not event_records[slug]["event_name"]:
            event_records[slug]["event_name"] = f"{team_titles[0]} vs. {team_titles[1]}"
        if event_records[slug]["fetch_status"] == "listed":
            event_records[slug]["fetch_status"] = "ok"

    events = pd.DataFrame(
        [row for key, row in event_records.items() if not key.startswith("fetch_error_")],
        columns=EVENT_COLUMNS,
    )
    markets = {
        slug: pd.DataFrame(rows).drop_duplicates(subset=["token_id"])
        for slug, rows in market_rows_by_event.items()
    }
    return events, markets


def extract_event_markets(event_url: str, timeout: int) -> tuple[dict[str, str], pd.DataFrame]:
    html = fetch_text(event_url, timeout)
    event_name, home_team, away_team = event_team_names_from_json_ld(html)
    market_rows: list[dict[str, Any]] = []

    for market in iter_moneyline_market_objects(html):
        market_rows.append(market_object_to_row(market))

    event = {
        "event_name": event_name,
        "home_team": home_team,
        "away_team": away_team,
    }
    return event, pd.DataFrame(market_rows)


def infer_mapped_outcome(market_row: pd.Series, home_team: str, away_team: str) -> str:
    title = normalize_team(market_row.get("group_item_title", ""))
    question = normalize_team(market_row.get("polymarket_question", ""))
    home = normalize_team(home_team)
    away = normalize_team(away_team)

    if "draw" in title or "draw" in question:
        return "draw"
    if title == home or (home and f"will {home} win" in question):
        return "home_win"
    if title == away or (away and f"will {away} win" in question):
        return "away_win"
    return ""


def match_event_to_prediction(event: dict[str, str], event_date: str, predictions: pd.DataFrame) -> pd.Series | None:
    group_matches = predictions[predictions["home_win_prob"].notna()].copy()
    group_matches["date_key"] = pd.to_datetime(group_matches["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    candidates = group_matches[group_matches["date_key"] == event_date].copy()

    event_teams = {normalize_team(event.get("home_team")), normalize_team(event.get("away_team"))}
    for _, row in candidates.iterrows():
        model_teams = {normalize_team(row["home_team"]), normalize_team(row["away_team"])}
        if event_teams == model_teams:
            return row

    event_datetime = pd.to_datetime(event_date, errors="coerce")
    if pd.isna(event_datetime):
        return None
    group_matches["date_delta_days"] = (
        pd.to_datetime(group_matches["date"], errors="coerce") - event_datetime
    ).abs().dt.days
    nearby = group_matches[group_matches["date_delta_days"] <= 1].copy()
    for _, row in nearby.sort_values("date_delta_days").iterrows():
        model_teams = {normalize_team(row["home_team"]), normalize_team(row["away_team"])}
        if event_teams == model_teams:
            return row
    return None


def discover_sports_game_mappings(
    predictions: pd.DataFrame,
    output_dir: Path,
    timeout: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events, markets_by_event = discover_world_cup_games_from_listing(timeout)
    enriched_events: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for event_row in events[events["event_url"].astype(str).str.len() > 0].itertuples(index=False):
        event_record = event_row._asdict()
        markets = markets_by_event.get(event_row.event_slug, pd.DataFrame())
        if markets.empty:
            try:
                event, markets = extract_event_markets(event_row.event_url, timeout)
                event_record["event_name"] = event.get("event_name") or event_record["event_name"]
                event_record["home_team"] = event.get("home_team") or event_record["home_team"]
                event_record["away_team"] = event.get("away_team") or event_record["away_team"]
                event_record["fetch_status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                event_record["fetch_status"] = f"error: {exc}"
        prediction = match_event_to_prediction(event_record, event_row.start_date, predictions)
        candidate_rows.append(
            {
                "match_id": "" if prediction is None else prediction["match_id"],
                "home_team": "" if prediction is None else prediction["home_team"],
                "away_team": "" if prediction is None else prediction["away_team"],
                "date": event_row.start_date,
                "polymarket_event_url": event_row.event_url,
                "polymarket_event_slug": event_row.event_slug,
                "polymarket_event_name": event_row.event_name,
                "polymarket_home_team": event_row.home_team,
                "polymarket_away_team": event_row.away_team,
                "match_score": 1.0 if prediction is not None else 0.0,
                "needs_review": prediction is None,
                "fetch_status": event_row.fetch_status,
            }
        )
        enriched_events.append(event_record)

        if prediction is None or markets.empty:
            continue

        for _, market in markets.iterrows():
            mapped_outcome = infer_mapped_outcome(market, prediction["home_team"], prediction["away_team"])
            if mapped_outcome not in {"home_win", "draw", "away_win"}:
                continue
            mapping_rows.append(
                {
                    "match_id": prediction["match_id"],
                    "home_team": prediction["home_team"],
                    "away_team": prediction["away_team"],
                    "polymarket_market_id": market["polymarket_market_id"],
                    "polymarket_question": market["polymarket_question"],
                    "outcome_type": "match_1x2",
                    "token_id": market["token_id"],
                    "mapped_outcome": mapped_outcome,
                    "market_slug": market["market_slug"],
                    "market_liquidity": market["market_liquidity"],
                    "market_end_date": market["market_end_date"],
                    "mapping_status": "auto_sports_event",
                    "notes": (
                        "Auto-mapped from Polymarket World Cup game page. "
                        "Market description says regular time plus stoppage time; suitable for group-stage 1X2 comparison."
                    ),
                }
            )

    events_out = pd.DataFrame(enriched_events, columns=EVENT_COLUMNS)
    candidates = pd.DataFrame(candidate_rows)
    mapping = pd.DataFrame(mapping_rows, columns=MAPPING_COLUMNS)
    events_out.to_csv(output_dir / "polymarket_world_cup_game_events.csv", index=False)
    candidates.to_csv(output_dir / "polymarket_game_event_mapping_candidates.csv", index=False)
    return events_out, candidates, mapping


def create_mapping_template(markets: pd.DataFrame, predictions: pd.DataFrame, liquidity_threshold: float) -> pd.DataFrame:
    if markets.empty:
        return pd.DataFrame(columns=MAPPING_COLUMNS)

    active = markets[
        (markets["active"] == True)
        & (markets["closed"] == False)
        & (markets["liquidity"].fillna(0) >= liquidity_threshold)
    ].copy()
    rows: list[dict[str, Any]] = []

    for market in active.itertuples(index=False):
        outcomes = as_list(market.outcomes)
        token_ids = as_list(market.clobTokenIds)
        max_len = max(len(outcomes), len(token_ids), 1)
        for index in range(max_len):
            rows.append(
                {
                    "match_id": "",
                    "home_team": "",
                    "away_team": "",
                    "polymarket_market_id": market.market_id,
                    "polymarket_question": market.question,
                    "outcome_type": "manual_review",
                    "token_id": token_ids[index] if index < len(token_ids) else "",
                    "mapped_outcome": outcomes[index] if index < len(outcomes) else "",
                    "market_slug": market.slug,
                    "market_liquidity": market.liquidity,
                    "market_end_date": market.endDate,
                    "mapping_status": "needs_manual_mapping",
                    "notes": "Confirm market rules before comparing with model probability.",
                }
            )

    if rows:
        return pd.DataFrame(rows, columns=MAPPING_COLUMNS)

    sample_matches = predictions[predictions["home_win_prob"].notna()].head(24)
    return pd.DataFrame(
        [
            {
                "match_id": row.match_id,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "polymarket_market_id": "",
                "polymarket_question": "",
                "outcome_type": "",
                "token_id": "",
                "mapped_outcome": "",
                "market_slug": "",
                "market_liquidity": "",
                "market_end_date": "",
                "mapping_status": "needs_manual_mapping",
                "notes": "Paste Polymarket token_id and set mapped_outcome to home_win/draw/away_win when market rules match.",
            }
            for row in sample_matches.itertuples(index=False)
        ],
        columns=MAPPING_COLUMNS,
    )


def read_mapping(path: Path, markets: pd.DataFrame, predictions: pd.DataFrame, liquidity_threshold: float) -> pd.DataFrame:
    if path.exists():
        mapping = pd.read_csv(path, dtype=str).fillna("")
        for column in MAPPING_COLUMNS:
            if column not in mapping:
                mapping[column] = ""
        return mapping[MAPPING_COLUMNS]
    mapping = create_mapping_template(markets, predictions, liquidity_threshold)
    path.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(path, index=False)
    return mapping


def best_price(levels: list[dict[str, Any]], side: str) -> float | None:
    prices = [as_float(level.get("price")) for level in levels if as_float(level.get("price")) > 0]
    if not prices:
        return None
    return max(prices) if side == "bid" else min(prices)


def depth(levels: list[dict[str, Any]]) -> float:
    return sum(as_float(level.get("size")) for level in levels)


def fetch_book(token_id: str, timeout: int) -> dict[str, Any]:
    response = requests.get(CLOB_BOOK_URL, params={"token_id": token_id}, timeout=timeout)
    response.raise_for_status()
    book = response.json()
    bids = book.get("bids") or book.get("buys") or []
    asks = book.get("asks") or book.get("sells") or []
    best_bid = best_price(bids, "bid")
    best_ask = best_price(asks, "ask")
    return {
        "token_id": token_id,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None,
        "spread": best_ask - best_bid if best_bid is not None and best_ask is not None else None,
        "bid_depth": depth(bids),
        "ask_depth": depth(asks),
        "last_trade_price": as_float(book.get("last_trade_price") or book.get("lastTradePrice")) or None,
        "raw_book": json.dumps(book, ensure_ascii=False),
    }


def fetch_prices(mapping: pd.DataFrame, timeout: int) -> pd.DataFrame:
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []
    token_ids = sorted({str(token).strip() for token in mapping["token_id"].dropna() if str(token).strip()})
    for token_id in token_ids:
        try:
            row = fetch_book(token_id, timeout)
            row["timestamp"] = timestamp
            row["price_fetch_status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            row = {
                "timestamp": timestamp,
                "token_id": token_id,
                "best_bid": None,
                "best_ask": None,
                "mid_price": None,
                "spread": None,
                "bid_depth": None,
                "ask_depth": None,
                "last_trade_price": None,
                "raw_book": "",
                "price_fetch_status": f"error: {exc}",
            }
        rows.append(row)
    columns = [
        "timestamp",
        "token_id",
        "best_bid",
        "best_ask",
        "mid_price",
        "spread",
        "bid_depth",
        "ask_depth",
        "last_trade_price",
        "raw_book",
        "price_fetch_status",
    ]
    return pd.DataFrame(rows, columns=columns)


def model_probability(mapping_row: pd.Series, predictions: pd.DataFrame, group_simulation: pd.DataFrame) -> float | None:
    outcome_type = str(mapping_row.get("outcome_type", "")).strip()
    mapped = str(mapping_row.get("mapped_outcome", "")).strip()
    match_id = str(mapping_row.get("match_id", "")).strip()

    if outcome_type in {"home_win", "draw", "away_win", "match_1x2"} and match_id:
        match = predictions[predictions["match_id"] == match_id]
        if match.empty:
            return None
        row = match.iloc[0]
        column = mapped if mapped in {"home_win", "draw", "away_win"} else outcome_type
        column_map = {"home_win": "home_win_prob", "draw": "draw_prob", "away_win": "away_win_prob"}
        return as_float(row[column_map[column]]) if column in column_map else None

    team = str(mapping_row.get("mapped_outcome", "")).strip() or str(mapping_row.get("home_team", "")).strip()
    if outcome_type in {"team_qualifies", "advance", "group_advance"} and team:
        rows = group_simulation[group_simulation["team"].str.lower() == team.lower()]
        return as_float(rows.iloc[0]["prob_advance"]) if not rows.empty else None

    if outcome_type in {"team_wins_group", "group_winner"} and team:
        rows = group_simulation[group_simulation["team"].str.lower() == team.lower()]
        return as_float(rows.iloc[0]["prob_group_1st"]) if not rows.empty else None

    return None


def signal(edge: float | None, spread: float | None, liquidity: float | None, liquidity_threshold: float) -> str:
    if edge is None or spread is None or pd.isna(edge) or pd.isna(spread):
        return "Needs Mapping"
    if liquidity is not None and liquidity < liquidity_threshold:
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


def build_edges(
    mapping: pd.DataFrame,
    prices: pd.DataFrame,
    predictions: pd.DataFrame,
    group_simulation: pd.DataFrame,
    liquidity_threshold: float,
) -> pd.DataFrame:
    if mapping.empty:
        return pd.DataFrame()
    merged = mapping.merge(prices.drop(columns=["raw_book"], errors="ignore"), on="token_id", how="left")
    merged["model_prob"] = merged.apply(lambda row: model_probability(row, predictions, group_simulation), axis=1)
    merged["market_prob"] = merged["best_ask"]
    merged["edge"] = merged["model_prob"] - merged["market_prob"]
    merged["signal"] = merged.apply(lambda row: signal(row["edge"], row["spread"], as_float(row.get("market_liquidity")), liquidity_threshold), axis=1)
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Polymarket markets/prices and compute paper-trading edge signals.")
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--group-simulation", type=Path, default=DEFAULT_GROUP_SIMULATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--liquidity-threshold", type=float, default=500.0)
    parser.add_argument("--search-term", action="append", dest="search_terms")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--skip-sports-games",
        action="store_true",
        help="Skip scraping Polymarket sports World Cup game pages.",
    )
    parser.add_argument(
        "--skip-gamma",
        action="store_true",
        help="Skip Gamma market discovery and keep any existing raw market file.",
    )
    parser.add_argument(
        "--skip-prices",
        action="store_true",
        help="Skip CLOB price fetching and keep any existing price file.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(args.predictions)
    group_simulation = pd.read_csv(args.group_simulation)
    search_terms = args.search_terms or DEFAULT_SEARCH_TERMS

    markets_path = args.output_dir / "polymarket_markets_raw.csv"
    if args.skip_gamma and markets_path.exists():
        markets = pd.read_csv(markets_path)
    elif args.skip_gamma:
        markets = pd.DataFrame()
    else:
        markets = fetch_gamma_market_search(search_terms, args.limit, args.timeout)
        markets.to_csv(markets_path, index=False)

    sports_mapping = pd.DataFrame(columns=MAPPING_COLUMNS)
    events_count = 0
    candidates_count = 0
    if not args.skip_sports_games:
        events, candidates, sports_mapping = discover_sports_game_mappings(
            predictions=predictions,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
        events_count = len(events[events["event_url"].astype(str).str.len() > 0])
        candidates_count = len(candidates)

    mapping_path = args.output_dir / "polymarket_match_mapping.csv"
    mapping = read_mapping(mapping_path, markets, predictions, args.liquidity_threshold)
    if not sports_mapping.empty:
        mapping = mapping[mapping["mapping_status"] != "auto_sports_event"].copy()
        mapping = pd.concat([mapping, sports_mapping], ignore_index=True)
        mapping = mapping.drop_duplicates(subset=["token_id"], keep="last")
    mapping.to_csv(mapping_path, index=False)

    prices_path = args.output_dir / "polymarket_prices.csv"
    if args.skip_prices and prices_path.exists():
        prices = pd.read_csv(prices_path, dtype={"token_id": str})
    elif args.skip_prices:
        prices = pd.DataFrame(
            columns=[
                "timestamp",
                "token_id",
                "best_bid",
                "best_ask",
                "mid_price",
                "spread",
                "bid_depth",
                "ask_depth",
                "last_trade_price",
                "raw_book",
                "price_fetch_status",
            ]
        )
    else:
        prices = fetch_prices(mapping, args.timeout)
        prices.to_csv(prices_path, index=False)

    edges = build_edges(mapping, prices, predictions, group_simulation, args.liquidity_threshold)
    edges_path = args.output_dir / "polymarket_edges.csv"
    edges.to_csv(edges_path, index=False)

    print(f"Wrote {len(markets)} markets to {markets_path}")
    if not args.skip_sports_games:
        print(f"Wrote {events_count} World Cup game events to {args.output_dir / 'polymarket_world_cup_game_events.csv'}")
        print(
            f"Wrote {candidates_count} event mapping candidates to "
            f"{args.output_dir / 'polymarket_game_event_mapping_candidates.csv'}"
        )
    print(f"Wrote {len(mapping)} mapping rows to {mapping_path}")
    print(f"Wrote {len(prices)} price rows to {prices_path}")
    print(f"Wrote {len(edges)} edge rows to {edges_path}")


if __name__ == "__main__":
    main()
