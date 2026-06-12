from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from train_match_result_model import (
    CLASS_ORDER,
    ELO_ONLY_FEATURE_COLUMNS,
    MODEL_VERSION,
    V4_FEATURE_COLUMNS,
    calibrated_probabilities,
    draw_risk_level,
    ensemble_probabilities,
)


DEFAULT_BASELINE = Path("data/processed/world_cup_2026_baseline.csv")
DEFAULT_MODEL = Path("models/match_result_v4_elo_ensemble_calibrated.joblib")
DEFAULT_CONFIG = Path("models/calibrated_v3_probability_config.json")
DEFAULT_OUTPUT = Path("data/processed/world_cup_2026_predictions_final.csv")


def apply_probability_floor(probabilities: pd.DataFrame, floor: float) -> pd.DataFrame:
    floored = probabilities[CLASS_ORDER].clip(lower=floor)
    return floored.div(floored.sum(axis=1), axis=0)


def temperature_scale(probabilities: pd.DataFrame, temperature: float) -> pd.DataFrame:
    clipped = probabilities[CLASS_ORDER].clip(lower=1e-12)
    scaled = np.power(clipped, 1 / temperature)
    return scaled.div(scaled.sum(axis=1), axis=0)


def probability_model_v3(calibrated_v1: pd.DataFrame, raw_ensemble: pd.DataFrame, floor: float, temperature: float) -> pd.DataFrame:
    v2_50_50 = 0.50 * calibrated_v1[CLASS_ORDER] + 0.50 * raw_ensemble[CLASS_ORDER]
    v2_50_50 = apply_probability_floor(v2_50_50, 0.05)
    floored = apply_probability_floor(v2_50_50, floor)
    return temperature_scale(floored, temperature)


def confidence_level(probability: float | pd.NA) -> str | pd.NA:
    if pd.isna(probability):
        return pd.NA
    if probability >= 0.70:
        return "high"
    if probability >= 0.55:
        return "medium"
    return "low"


def upset_risk(favorite_probability: float | pd.NA, draw_probability: float | pd.NA) -> str | pd.NA:
    if pd.isna(favorite_probability) or pd.isna(draw_probability):
        return pd.NA
    if favorite_probability < 0.50 or draw_probability >= 0.30:
        return "high"
    if favorite_probability < 0.60 or draw_probability >= 0.24:
        return "medium"
    return "low"


def build_final_predictions(baseline: pd.DataFrame, model_bundle: dict, config: dict) -> pd.DataFrame:
    output = pd.DataFrame(
        {
            "match_id": baseline["match_id"],
            "date": baseline["date"],
            "group": baseline["group"],
            "round": baseline["round"],
            "home_team": baseline["home_team"],
            "away_team": baseline["away_team"],
        }
    )

    for column in [
        "winner_model_pick",
        "winner_model_confidence",
        "home_win_prob",
        "draw_prob",
        "away_win_prob",
        "home_fair_odds",
        "draw_fair_odds",
        "away_fair_odds",
        "draw_risk",
        "upset_risk",
        "confidence_level",
        "model_note",
    ]:
        output[column] = pd.NA

    known_mask = ~baseline["home_is_placeholder"].astype(bool) & ~baseline["away_is_placeholder"].astype(bool)
    usable_mask = known_mask & baseline["home_elo"].notna() & baseline["away_elo"].notna()
    if not usable_mask.any():
        return output

    usable = baseline.loc[usable_mask].copy()
    v4_model = model_bundle["v4_model"]
    elo_model = model_bundle["elo_model"]
    calibrator = model_bundle["calibrator"]

    raw = ensemble_probabilities(v4_model, elo_model, usable)
    calibrated_v1 = calibrated_probabilities(calibrator, raw)
    fair_probs = probability_model_v3(
        calibrated_v1=calibrated_v1,
        raw_ensemble=raw,
        floor=float(config["probability_floor"]),
        temperature=float(config["temperature"]),
    )
    fair_probs.index = usable.index
    calibrated_v1.index = usable.index

    winner_direction = calibrated_v1[["home_win", "away_win"]].idxmax(axis=1)
    winner_confidence = pd.Series(
        np.where(winner_direction == "home_win", calibrated_v1["home_win"], calibrated_v1["away_win"]),
        index=usable.index,
    )
    favorite_probability = fair_probs[CLASS_ORDER].max(axis=1)

    output.loc[usable.index, "winner_model_pick"] = np.where(
        winner_direction == "home_win",
        usable["home_team"],
        usable["away_team"],
    )
    output.loc[usable.index, "winner_model_confidence"] = winner_confidence
    output.loc[usable.index, "home_win_prob"] = fair_probs["home_win"]
    output.loc[usable.index, "draw_prob"] = fair_probs["draw"]
    output.loc[usable.index, "away_win_prob"] = fair_probs["away_win"]
    output.loc[usable.index, "home_fair_odds"] = 1 / fair_probs["home_win"]
    output.loc[usable.index, "draw_fair_odds"] = 1 / fair_probs["draw"]
    output.loc[usable.index, "away_fair_odds"] = 1 / fair_probs["away_win"]
    output.loc[usable.index, "draw_risk"] = fair_probs["draw"].map(draw_risk_level)
    output.loc[usable.index, "upset_risk"] = [
        upset_risk(favorite, draw) for favorite, draw in zip(favorite_probability, fair_probs["draw"])
    ]
    output.loc[usable.index, "confidence_level"] = winner_confidence.map(confidence_level)
    output.loc[usable.index, "model_note"] = (
        f"winner={MODEL_VERSION}; probability={config['model_version']}; "
        f"draw is risk indicator, not final pick"
    )

    placeholder_mask = ~usable_mask
    output.loc[placeholder_mask, "model_note"] = "placeholder knockout match; teams not known yet"
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final World Cup 2026 prediction CSV for dashboard MVP.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    baseline = pd.read_csv(args.baseline)
    model_bundle = joblib.load(args.model)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    predictions = build_final_predictions(baseline, model_bundle, config)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output, index=False)
    predicted_rows = predictions["home_win_prob"].notna().sum()
    print(f"Wrote {len(predictions)} rows to {args.output}")
    print(f"Predicted known-team rows: {predicted_rows}")


if __name__ == "__main__":
    main()
