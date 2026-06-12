# 世界杯预测准确率追踪说明

## 当前预测项目

第一版追踪四类预测：

1. 赢家预测准确率：预测胜平负方向是否正确。
2. 比分预测准确率：默认展示 Top 1 exact score，系统也保存 Top 3 命中率。
3. 进球球员预测准确率：第一版暂未启用，等待球员首发、射门、赔率或事件数据。
4. 角球数量预测准确率：第一版暂未启用，等待角球历史和实时技术统计数据。

## 文件

- `data/processed/world_cup_2026_prediction_markets.csv`
  - 扩展预测表，包含胜平负、Top 3 比分、xG、大小球、BTTS，以及进球球员/角球字段占位。

- `data/actuals/world_cup_2026_actual_results.csv`
  - 实际赛果模板。比赛结束后更新这里的实际比分、状态、进球球员和角球数据。

- `data/processed/model_prediction_accuracy_summary.csv`
  - Dashboard Overview 使用的准确率汇总。

- `data/processed/model_prediction_accuracy_details.csv`
  - 每场比赛的预测和真实结果对比明细。

## 更新流程

比赛结束后，更新 `data/actuals/world_cup_2026_actual_results.csv` 中对应比赛：

- `status`：改成 `FT`
- `actual_home_goals`
- `actual_away_goals`
- 如有数据，再填：
  - `actual_first_goalscorer`
  - `actual_total_corners`
  - `actual_first_half_corners`
  - `actual_second_half_corners`

然后运行：

```bash
.venv/bin/python scripts/update_prediction_accuracy.py
```

Dashboard 的 Overview 页面会读取新的准确率汇总。

## 后续自动化

如果要全自动更新，需要接入稳定的数据源：

- 比分：API-Football fixtures endpoint 可以实现。
- 进球球员：需要 fixture events。
- 角球：需要 fixture statistics，且确认 API plan 是否提供上下半场角球。

