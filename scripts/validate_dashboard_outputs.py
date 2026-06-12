from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BASELINE = Path("data/processed/world_cup_2026_baseline.csv")
DEFAULT_FINAL = Path("data/processed/world_cup_2026_predictions_final.csv")
DEFAULT_CHECKS = Path("data/reports/dashboard_validation_checks.csv")
DEFAULT_REPORT = Path("data/reports/dashboard_validation_report.zh-CN.md")

WINNER_MODEL = "v4_elo_ensemble_calibrated_v1"
PROBABILITY_MODEL = "calibrated_v3_floor_010_T1.2"


def validate(baseline: pd.DataFrame, final: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    merged = final.merge(
        baseline[["match_id", "predicted_winner", "model_version", "home_is_placeholder", "away_is_placeholder"]],
        on="match_id",
        how="left",
        validate="one_to_one",
    )
    known = merged["home_win_prob"].notna()
    placeholder = ~known

    prob_sum = merged[["home_win_prob", "draw_prob", "away_win_prob"]].sum(axis=1)
    home_odds_expected = 1 / merged["home_win_prob"]
    draw_odds_expected = 1 / merged["draw_prob"]
    away_odds_expected = 1 / merged["away_win_prob"]

    checks = pd.DataFrame(
        {
            "match_id": merged["match_id"],
            "match": merged["home_team"].astype(str) + " vs " + merged["away_team"].astype(str),
            "row_type": np.where(known, "predicted_group_match", "knockout_placeholder"),
            "probability_sum": prob_sum.where(known),
            "probability_sum_ok": np.where(known, np.isclose(prob_sum, 1.0, atol=1e-9), True),
            "home_fair_odds_ok": np.where(known, np.isclose(merged["home_fair_odds"], home_odds_expected, atol=1e-9), True),
            "draw_fair_odds_ok": np.where(known, np.isclose(merged["draw_fair_odds"], draw_odds_expected, atol=1e-9), True),
            "away_fair_odds_ok": np.where(known, np.isclose(merged["away_fair_odds"], away_odds_expected, atol=1e-9), True),
            "favorite_from_winner_model_ok": np.where(known, merged["winner_model_pick"] == merged["predicted_winner"], True),
            "winner_model_version_ok": np.where(known, merged["model_version"] == WINNER_MODEL, True),
            "probability_model_note_ok": np.where(known, merged["model_note"].astype(str).str.contains(PROBABILITY_MODEL, regex=False), True),
            "placeholder_handled_ok": np.where(placeholder, merged["model_note"].astype(str).str.contains("placeholder", case=False), True),
        }
    )

    summary = {
        "total_matches": len(final),
        "group_stage_matches": int(final["group"].notna().sum()),
        "known_prediction_rows": int(known.sum()),
        "knockout_placeholders": int(placeholder.sum()),
        "all_probability_sums_ok": bool(checks["probability_sum_ok"].all()),
        "all_fair_odds_ok": bool(checks[["home_fair_odds_ok", "draw_fair_odds_ok", "away_fair_odds_ok"]].all().all()),
        "all_favorites_from_winner_model": bool(checks["favorite_from_winner_model_ok"].all()),
        "all_winner_model_versions_ok": bool(checks["winner_model_version_ok"].all()),
        "all_probability_model_notes_ok": bool(checks["probability_model_note_ok"].all()),
        "all_placeholders_handled_ok": bool(checks["placeholder_handled_ok"].all()),
    }
    return checks, summary


def write_report(path: Path, checks: pd.DataFrame, summary: dict[str, object]) -> None:
    failing = checks[
        ~checks[
            [
                "probability_sum_ok",
                "home_fair_odds_ok",
                "draw_fair_odds_ok",
                "away_fair_odds_ok",
                "favorite_from_winner_model_ok",
                "winner_model_version_ok",
                "probability_model_note_ok",
                "placeholder_handled_ok",
            ]
        ].all(axis=1)
    ]
    lines = [
        "# Dashboard 输出校验报告",
        "",
        "## Summary",
        "",
        f"- 总赛程：{summary['total_matches']} 场",
        f"- 小组赛：{summary['group_stage_matches']} 场",
        f"- 已知球队预测：{summary['known_prediction_rows']} 场",
        f"- 淘汰赛 placeholder：{summary['knockout_placeholders']} 场",
        f"- 概率加总为 100%：{summary['all_probability_sums_ok']}",
        f"- Fair odds = 1 / probability：{summary['all_fair_odds_ok']}",
        f"- Favorite 来自 winner model：{summary['all_favorites_from_winner_model']}",
        f"- Winner model 版本一致：{summary['all_winner_model_versions_ok']}",
        f"- Probability model note 一致：{summary['all_probability_model_notes_ok']}",
        f"- Placeholder 单独处理：{summary['all_placeholders_handled_ok']}",
        "",
        "## 模型口径",
        "",
        f"- Winner model：`{WINNER_MODEL}`",
        f"- Probability model：`{PROBABILITY_MODEL}`",
        "- Draw 不作为 final pick，只作为 risk signal。",
        "",
        "## 异常行",
        "",
    ]
    if failing.empty:
        lines.append("没有发现异常行。")
    else:
        lines.append(failing.to_markdown(index=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dashboard prediction outputs.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--final", type=Path, default=DEFAULT_FINAL)
    parser.add_argument("--checks", type=Path, default=DEFAULT_CHECKS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    baseline = pd.read_csv(args.baseline)
    final = pd.read_csv(args.final)
    checks, summary = validate(baseline, final)
    args.checks.parent.mkdir(parents=True, exist_ok=True)
    checks.to_csv(args.checks, index=False)
    write_report(args.report, checks, summary)
    print(f"Wrote checks to {args.checks}")
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
