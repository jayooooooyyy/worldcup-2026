# 模型版本历史

这个文件用于记录每一次模型版本更新。以后每次改模型，都需要在这里追加一节，包含：

- 模型版本 ID
- 是否为当前 active 模型
- 改动内容
- 使用特征
- 训练策略
- 校准策略
- 关键结果 summary
- 输出文件位置
- 已知问题和下一步

## 当前 Active 模型

当前 active 模型是：

```text
v4_elo_ensemble_calibrated_v1
```

当前 fair odds 概率展示模型是：

```text
calibrated_v3_floor_010_T1.2
```

对应文件：

- 模型文件：`models/match_result_v4_elo_ensemble_calibrated.joblib`
- 概率展示配置：`models/calibrated_v3_probability_config.json`
- 冻结模型栈：`models/frozen_model_stack.json`
- 预测输出：`data/processed/world_cup_2026_baseline.csv`
- Dashboard 最终预测输入：`data/processed/world_cup_2026_predictions_final.csv`
- 模型报告：`data/reports/match_result_model_v1.zh-CN.md`
- 小组模拟：`data/processed/world_cup_2026_group_simulation.csv`
- 小组模拟报告：`data/reports/group_simulation_v1.zh-CN.md`

## calibrated_v3_floor_010_T1.2

状态：fair-odds probability model

更新时间：2026-06-10

### 主要改动

- 不直接使用 `v4_elo_ensemble_calibrated_v1` 的概率作为 fair odds。
- 以 `v2_50_50` 为基础：

```text
v2_50_50 = 50% calibrated_v1 + 50% raw_ensemble
```

- 对三项概率设置 `min_prob = 0.10`。
- 每次 floor 后重新 normalize，保证 `home + draw + away = 1`。
- 使用 temperature scaling：`T = 1.2`，让 favorite 概率不要过度极端。
- 保留 `v4_elo_ensemble_calibrated_v1` 作为 winner / favorite 模型，`calibrated_v3_floor_010_T1.2` 作为展示概率和 fair odds 模型。

### 选择原因

候选模型中，`v3_floor_010_T1.2` 最符合当前 fair odds 目标：

- `log_loss` 低于 1.55。
- `brier_score` 低于 0.52。
- `avg_draw_prob` 位于 25%-28% 区间。
- `min_true_class_prob` 高于 0.08。
- 保留了和 v2 相同的较高 top-1 accuracy。

### World Cup Walk-Forward Backtest Summary

回测方法：

```text
训练集 = 该届世界杯开赛前所有历史比赛
样本权重 = recency_weight × tournament_weight
测试集 = 该届 World Cup 正赛 64 场
```

覆盖年份：

- 2010
- 2014
- 2018
- 2022

| metric | value |
|---|---:|
| world_cup_backtest_avg_top1_accuracy | 0.664063 |
| world_cup_backtest_avg_non_draw_pick_accuracy | 0.853604 |
| world_cup_backtest_avg_log_loss | 1.520002 |
| world_cup_backtest_avg_brier | 0.499484 |
| world_cup_backtest_avg_draw_recall | 0.000000 |
| world_cup_backtest_avg_draw_prob | 0.273599 |
| min_true_class_prob | 0.124043 |
| worst_10_avg_log_loss | 1.497170 |

### V3 候选模型对比

详细文件：

- `data/reports/diagnostics/calibrated_v3_summary.csv`
- `data/reports/diagnostics/calibrated_model_diagnostic_report.zh-CN.md`
- `models/calibrated_v3_probability_config.json`

### 已知问题

- `draw_recall` 仍然为 0，因此 draw 仍不适合做最终 pick，只适合作为风险和 fair odds 概率展示。
- `top1_accuracy` 为 66.4%，略高于 62%-66% 的目标上沿，但这是因为所有 v3 候选版本的 top-1 pick 基本相同；概率质量改善主要体现在 Log Loss、Brier 和最低真实类概率。
- 淘汰赛 90 分钟口径仍需单独处理，当前历史训练表缺少 round / extra time / penalty 字段。

## v4_elo_ensemble_calibrated_v1

状态：active

更新时间：2026-06-10

### 主要改动

- 使用 V4 作为主模型：Elo + recent form + goal stats。
- 加入 Elo-only 模型，并与 V4 做等权 ensemble。
- 加入 recency weighting。
- 加入 tournament weighting。
- 加入 probability calibration。
- 将 `draw` 从最终预测结果中移除，改为风险提示。
- `model_prediction` 现在只输出 `home_win` 或 `away_win`。
- 新增 `predicted_winner`、`draw_risk_level`、`draw_risk_flag`。

### 样本权重

最终权重：

```text
sample_weight = recency_weight * tournament_weight
```

Recency weight：

| 比赛距测试/预测时间 | 权重 |
|---|---:|
| 0-4 年 | 1.00 |
| 4-8 年 | 0.70 |
| 8-12 年 | 0.45 |
| 12-20 年 | 0.25 |
| 20 年以上 | 0.10 |

Tournament weight：

| 赛事类型 | 权重 |
|---|---:|
| World Cup | 3.0 |
| Continental Championship | 2.0 |
| World Cup Qualifier | 1.5 |
| Friendly | 0.5 |
| Other | 1.0 |

### 训练与校准

- 训练起始日期：1990-01-01
- 入模要求：双方 ELO 存在，双方赛前近期状态至少各有 5 场。
- Base model train 样本数：21,316
- Calibration 样本数：4,568
- Validation 样本数：4,568
- 入模总样本数：30,452
- Base models：V4 logistic regression + Elo-only logistic regression
- Ensemble：两套模型概率等权平均
- Calibration：基于 ensemble 概率 logits 训练 multinomial logistic calibrator

### Validation Summary

| version | top1_accuracy | non_draw_pick_accuracy | log_loss | brier_score | draw_recall | avg_draw_prob | draw_risk_flags |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw ensemble | 0.5841 | 0.7653 | 1.6889 | 0.5279 | 0.0000 | 0.2283 | 2375 |
| calibrated ensemble | 0.6344 | 0.8285 | 2.2242 | 0.4783 | 0.0176 | 0.2232 | 2287 |

解读：

- Calibration 后 Brier Score 改善，说明整体概率平方误差更稳。
- Calibration 后 Log Loss 变差，说明仍有少数过度自信错误，需要继续优化校准方法。
- Draw recall 仍然很低，因此 draw 继续作为风险提示，而不是最终 pick。

### World Cup Walk-Forward Backtest Summary

回测方法：

```text
训练集 = 该届世界杯开赛前所有历史比赛
样本权重 = recency_weight × tournament_weight
测试集 = 该届 World Cup 正赛 64 场
```

覆盖年份：

- 2010
- 2014
- 2018
- 2022

当前 active 模型平均结果：

| metric | value |
|---|---:|
| world_cup_backtest_avg_top1_accuracy | 0.679688 |
| world_cup_backtest_avg_non_draw_pick_accuracy | 0.883522 |
| world_cup_backtest_avg_log_loss | 2.115673 |
| world_cup_backtest_avg_brier | 0.422372 |
| world_cup_backtest_avg_draw_recall | 0.019231 |
| world_cup_backtest_avg_draw_prob | 0.254578 |

对比观察：

- active 校准模型的 Brier Score 明显优于 raw ensemble、V4 和 Elo-only。
- active 校准模型的 top-1 / non-draw pick accuracy 也更高。
- active 校准模型的 Log Loss 明显更差，说明少数错误样本存在过度自信问题。
- 因此版本选择不能只看 Log Loss 或只看 Accuracy；当前版本更适合先作为“概率 + 风险提示”底座，下一版应重点改善校准后的 Log Loss。

详细文件：

- `data/reports/backtests/world_cup_backtest_average_summary.csv`
- `data/reports/backtests/world_cup_backtest_summary.csv`
- `data/reports/backtests/world_cup_backtest_report.zh-CN.md`

### 2026 Baseline 输出 Summary

- 输出比赛数：104
- 已写入预测概率的小组赛：72
- 淘汰赛占位符：32，暂不预测
- `model_prediction` 分布：
  - `home_win`：58
  - `away_win`：14
- `draw_risk_level` 分布：
  - `high`：32
  - `medium`：9
  - `low`：31
- 平均概率：
  - `home_win_prob`：0.578754
  - `draw_prob`：0.256658
  - `away_win_prob`：0.164589

### 输出文件

- `models/match_result_v4_elo_ensemble_calibrated.joblib`
- `data/processed/world_cup_2026_baseline.csv`
- `data/reports/match_result_model_v1.zh-CN.md`
- `data/processed/world_cup_2026_group_simulation.csv`
- `data/reports/group_simulation_v1.zh-CN.md`

### 已知问题

- Calibration 的 Log Loss 变差，需要尝试更稳的校准方法，例如 temperature scaling、Dirichlet calibration 或按 outcome 单独校准。
- API-Football 数据目前只抓到 2022 World Cup，尚未并入模型训练。
- 小组模拟脚本当前为纯 Python 20,000 次模拟，速度偏慢，后续可以向量化。

### 下一步建议

- 做 calibration backtest，而不是只看 validation。
- 做 recency/tournament weighting 的敏感性测试。
- 优化小组模拟性能。
- 如果 API-Football 权限升级或接入其他数据源，再加入 2026 阵容、伤病、球员状态等特征。

## match_result_logreg_v1

状态：archived

更新时间：2026-06-09

### 主要内容

- 第一版可运行胜平负模型。
- 使用多分类 logistic regression。
- 使用 ELO、近期状态、H2H、真实主场/中立场等特征。
- 后续加入过真实主场修正和主客交换对称增强。
- `draw` 曾作为三分类之一参与最终 `model_prediction`，但几乎不会成为最高概率。

### 结果摘要

- 历史世界杯 backtest 显示，draw recall 长期接近 0。
- 模型能输出 `draw_prob`，但不适合把 `draw` 当作最终 pick。
- 高胜率样本存在过度自信风险，因此后续升级为 ensemble + calibration。

### 输出文件

- `models/match_result_logistic_regression.joblib`

### 淘汰原因

- 未使用 recency weighting。
- 未使用 tournament weighting。
- 未使用 probability calibration。
- 未采用 V4 + Elo-only ensemble。
- draw 处理方式不符合当前产品目标。
