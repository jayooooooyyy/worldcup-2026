# 第一版胜平负模型报告

## 当前主模型

- 模型版本：`v4_elo_ensemble_calibrated_v1`
- 主模型：V4（Elo + recent form + goal stats）
- Ensemble：V4 + Elo-only，二者概率等权平均
- Calibration：使用 ensemble 概率 logits 训练 multinomial logistic calibrator
- Draw 不再作为最终 pick；改为 `draw_prob` + `draw_risk_level` 风险提示

## 权重

- 0-4 年：1.00
- 4-8 年：0.70
- 8-12 年：0.45
- 12-20 年：0.25
- 20 年以上：0.10
- World Cup：3.0
- Continental Championship：2.0
- World Cup Qualifier：1.5
- Friendly：0.5
- Other：1.0

最终样本权重：`sample_weight = recency_weight * tournament_weight`

## 数据量

- 训练样本起始日期：1990-01-01
- 入模要求：双方 ELO 存在，双方赛前近期状态至少各有 5 场
- 入模总样本数：30452
- Base model train 样本数：21316
- Calibration 样本数：4568
- Validation 样本数：4568
- 主胜样本数：17380
- 平局样本数：7370
- 客胜样本数：5702

## Validation 概率指标

| version | top1_accuracy | non_draw_pick_accuracy | log_loss | brier_score | draw_recall | avg_draw_prob | draw_risk_flags |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw ensemble | 0.5841 | 0.7653 | 1.6889 | 0.5279 | 0.0000 | 0.2283 | 2375 |
| calibrated ensemble | 0.6344 | 0.8285 | 2.2242 | 0.4783 | 0.0176 | 0.2232 | 2287 |

## 世界杯预测输出

- 已写入预测概率的世界杯比赛数：72
- 淘汰赛占位符比赛暂不预测，等待小组赛模拟后再填充球队。

## 新增/更新字段

- `home_win_prob`：主胜概率
- `draw_prob`：平局概率，用作风险提示
- `away_win_prob`：客胜概率
- `model_prediction`：只在主胜/客胜中选择，不再输出 draw
- `predicted_winner`：非平局方向上的预测胜者
- `draw_risk_level`：`low` / `medium` / `high`
- `draw_risk_flag`：平局风险是否需要提示
- `model_version`：模型版本
