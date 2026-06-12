# 2026 世界杯 Baseline 字段说明

本文档说明 `data/processed/world_cup_2026_baseline.csv` 中每个字段的含义。

## 比赛标识与赛程字段

| 字段名 | 中文说明 |
|---|---|
| `match_id` | 每场比赛的唯一 ID。优先使用官方比赛编号生成，例如 `wc2026_m001`；如果官方编号为空，则使用赛程行号生成，例如 `wc2026_r103`。 |
| `source_row` | 该比赛在原始赛程表中的行号，从 1 开始。 |
| `competition` | 赛事名称，例如 `World Cup 2026`。 |
| `round` | 比赛阶段，例如小组赛 Matchday、Round of 32、Final。 |
| `group` | 小组名称，例如 `Group A`；淘汰赛为空。 |
| `date` | 原始赛程日期。 |
| `time` | 原始赛程时间，包含 UTC 偏移，例如 `13:00 UTC-6`。 |
| `match_datetime_utc` | 换算后的 UTC 比赛时间，便于后续统一排序和接外部数据。 |
| `city` | 比赛举办城市。 |
| `venue_country` | 比赛举办国家，目前用于区分美国、墨西哥、加拿大三个东道主国家。 |

## 球队字段

| 字段名 | 中文说明 |
|---|---|
| `home_team` | 标准化后的主队名称，用于跨数据源匹配。 |
| `away_team` | 标准化后的客队名称，用于跨数据源匹配。 |
| `home_is_placeholder` | 主队是否为淘汰赛占位符，例如 `1A`、`W73`。 |
| `away_is_placeholder` | 客队是否为淘汰赛占位符，例如 `2B`、`W74`。 |
| `home_advantage` | 主队是否拥有真实主场优势。只有球队在本国比赛时为 1。 |
| `away_advantage` | 客队是否拥有真实主场优势。只有球队在本国比赛时为 1。 |
| `neutral_venue` | 是否为中立场。当前世界杯 baseline 中，美国、墨西哥、加拿大之外的球队互相比赛视为中立场。 |

## ELO 字段

| 字段名 | 中文说明 |
|---|---|
| `home_elo` | 主队在比赛日前最新可用的 ELO rating。 |
| `away_elo` | 客队在比赛日前最新可用的 ELO rating。 |
| `elo_diff_home_minus_away` | 主队 ELO 减去客队 ELO。正数代表主队 ELO 更高。 |
| `home_elo_date` | 主队 ELO rating 对应的日期。 |
| `away_elo_date` | 客队 ELO rating 对应的日期。 |
| `home_elo_last_change` | 主队该条 ELO 记录中的 rating 变化值。 |
| `away_elo_last_change` | 客队该条 ELO 记录中的 rating 变化值。 |

## 主队近期状态字段

这些字段基于主队在比赛日前最近 10 场历史国家队比赛计算。

| 字段名 | 中文说明 |
|---|---|
| `home_recent10_matches` | 主队最近可用比赛场数，最多 10 场。 |
| `home_recent10_wins` | 主队最近 10 场胜场数。 |
| `home_recent10_draws` | 主队最近 10 场平局数。 |
| `home_recent10_losses` | 主队最近 10 场负场数。 |
| `home_recent10_win_rate` | 主队最近 10 场胜率。 |
| `home_recent10_points_per_match` | 主队最近 10 场场均积分，胜 3 分、平 1 分、负 0 分。 |
| `home_recent10_goals_for_avg` | 主队最近 10 场场均进球。 |
| `home_recent10_goals_against_avg` | 主队最近 10 场场均失球。 |

## 客队近期状态字段

这些字段基于客队在比赛日前最近 10 场历史国家队比赛计算。

| 字段名 | 中文说明 |
|---|---|
| `away_recent10_matches` | 客队最近可用比赛场数，最多 10 场。 |
| `away_recent10_wins` | 客队最近 10 场胜场数。 |
| `away_recent10_draws` | 客队最近 10 场平局数。 |
| `away_recent10_losses` | 客队最近 10 场负场数。 |
| `away_recent10_win_rate` | 客队最近 10 场胜率。 |
| `away_recent10_points_per_match` | 客队最近 10 场场均积分，胜 3 分、平 1 分、负 0 分。 |
| `away_recent10_goals_for_avg` | 客队最近 10 场场均进球。 |
| `away_recent10_goals_against_avg` | 客队最近 10 场场均失球。 |

## 历史交锋字段

这些字段基于两队在比赛日前所有历史交锋计算。这里的“主队”和“客队”指当前赛程中的主队、客队，不一定等同于历史比赛里的主客场。

| 字段名 | 中文说明 |
|---|---|
| `h2h_matches` | 两队历史交锋总场数。 |
| `h2h_home_team_wins` | 当前主队在历史交锋中击败当前客队的次数。 |
| `h2h_away_team_wins` | 当前客队在历史交锋中击败当前主队的次数。 |
| `h2h_draws` | 两队历史交锋平局次数。 |
| `h2h_home_team_win_rate` | 当前主队在历史交锋中的胜率。 |
| `h2h_away_team_win_rate` | 当前客队在历史交锋中的胜率。 |
| `h2h_draw_rate` | 两队历史交锋平局率。 |
| `h2h_home_goals_avg` | 当前主队在历史交锋中的场均进球。 |
| `h2h_away_goals_avg` | 当前客队在历史交锋中的场均进球。 |
| `h2h_last_match_date` | 两队最近一次历史交锋日期。 |

## 模型预测字段

这些字段由第一版胜平负模型写入。当前只对双方球队已知、且特征完整的小组赛比赛生成预测；淘汰赛占位符比赛暂时为空。

| 字段名 | 中文说明 |
|---|---|
| `home_win_prob` | 模型预测的主胜概率。 |
| `draw_prob` | 模型预测的平局概率。 |
| `away_win_prob` | 模型预测的客胜概率。 |
| `home_fair_odds` | 主胜公平赔率，计算方式为 `1 / home_win_prob`。 |
| `draw_fair_odds` | 平局公平赔率，计算方式为 `1 / draw_prob`。 |
| `away_fair_odds` | 客胜公平赔率，计算方式为 `1 / away_win_prob`。 |
| `model_prediction` | 非平局方向上的预测结果，只会是 `home_win` 或 `away_win`。平局改由 `draw_prob` 和风险字段表达。 |
| `predicted_winner` | 非平局方向上更可能获胜的球队名称。 |
| `draw_risk_level` | 平局风险等级，取值为 `low`、`medium`、`high`。 |
| `draw_risk_flag` | 是否需要提示平局风险。 |
| `model_version` | 生成该预测的模型版本。 |

## 建模使用建议

第一版模型可以优先使用以下字段：

- `elo_diff_home_minus_away`
- `home_elo`
- `away_elo`
- `home_recent10_points_per_match`
- `away_recent10_points_per_match`
- `home_recent10_goals_for_avg`
- `away_recent10_goals_for_avg`
- `home_recent10_goals_against_avg`
- `away_recent10_goals_against_avg`
- `h2h_matches`
- `h2h_home_team_win_rate`
- `h2h_away_team_win_rate`
- `h2h_draw_rate`

需要注意：历史交锋样本可能很少，不能过度依赖。ELO 差值通常更适合作为 baseline 模型的核心变量。
