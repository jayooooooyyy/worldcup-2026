# FIFA 世界杯预测项目说明

这个项目的第一步，是把世界杯赛程表、国家队 ELO rating、历史国家队比赛结果合并成一张“比赛级别”的 baseline 数据表，用于后续预测每场比赛的胜平负概率。

## 当前产物

- `scripts/build_baseline_data.py`：数据构建脚本，负责读取三份原始数据、统一球队名称、生成特征并输出 baseline。
- `scripts/build_training_data.py`：历史比赛训练数据构建脚本，负责为每场历史比赛生成赛前特征和真实结果标签。
- `scripts/train_match_result_model.py`：第一版胜平负模型训练脚本，负责训练模型并把预测概率写回世界杯 baseline。
- `scripts/backtest_world_cup_model.py`：世界杯历史回测脚本，按 2010、2014、2018、2022 四届做时间切分回测。
- `scripts/feature_ablation_backtest.py`：特征消融回测脚本，对比 Elo only、recent form、H2H、goal stats、true home/close match 等版本。
- `scripts/simulate_group_stage.py`：小组赛 Monte Carlo 模拟脚本，用单场概率生成小组排名和晋级概率。
- `scripts/fetch_api_football_data.py`：API-Football 数据抓取脚本，通过环境变量 `API_FOOTBALL_KEY` 读取 key。
- `data/processed/world_cup_2026_baseline.csv`：合并后的 baseline 数据表。
- `data/processed/international_match_training.csv`：历史比赛训练数据表，用于训练胜平负预测模型。
- `models/match_result_v4_elo_ensemble_calibrated.joblib`：V4 + Elo-only ensemble + calibration 模型文件。
- `data/reports/world_cup_2026_baseline_quality.md`：英文数据质量报告。
- `data/reports/world_cup_2026_baseline_quality.zh-CN.md`：中文数据质量报告。
- `data/reports/world_cup_2026_field_dictionary.zh-CN.md`：中文字段说明。
- `data/reports/international_match_training_quality.zh-CN.md`：历史比赛训练数据质量报告。
- `data/reports/match_result_model_v1.zh-CN.md`：第一版胜平负模型报告。
- `data/reports/model_version_history.zh-CN.md`：模型版本历史，记录每个版本的改动、结果 summary 和输出文件。
- `data/reports/model_version_summary.csv`：模型版本摘要表，方便程序读取或快速对比。
- `data/reports/backtests/world_cup_backtest_report.zh-CN.md`：世界杯历史回测报告。
- `data/reports/ablations/feature_ablation_report.zh-CN.md`：特征消融回测报告。
- `data/processed/world_cup_2026_group_simulation.csv`：小组赛模拟后的球队出线概率。
- `data/reports/group_simulation_v1.zh-CN.md`：小组赛模拟报告。
- `data/external/api_football/`：API-Football 抓取的外部数据。
- `data/reports/api_football_fetch_report.zh-CN.md`：API-Football 抓取报告。

## Baseline 数据粒度

baseline 表的粒度是：

```text
一行 = 2026 世界杯赛程中的一场比赛
```

当前表中共有 104 场比赛：

- 72 场小组赛：双方球队已知，可以直接生成 ELO、近期状态、历史交锋等特征。
- 32 场淘汰赛：赛程里仍是 `1A`、`2B`、`W73` 这类占位符，真实球队要等小组赛结果或模拟结果出来后才能确定。

淘汰赛占位符不会被删除，而是保留在 baseline 表中，并通过 `home_is_placeholder`、`away_is_placeholder` 标记出来。这样后续做小组赛出线模拟时，可以继续把真实球队填回这些赛程行。

## 当前特征模块

baseline 表目前包含以下几类信息：

- 赛程信息：唯一比赛 ID、比赛日期、时间、UTC 时间、城市、轮次、小组。
- 球队信息：标准化后的主队/客队名称、是否为淘汰赛占位符。
- ELO 特征：比赛日前双方最新 ELO、ELO 差值、ELO 更新时间。
- 近期状态：双方在比赛日前最近 10 场国家队比赛的胜平负、场均积分、场均进球、场均失球。
- 历史交锋：双方历史交锋次数、胜平负比例、场均进球、最近一次交锋日期。

## 已处理的名称标准化

不同数据源里的国家队名称并不完全一致，因此构建脚本做了统一处理：

- `USA` -> `United States`
- `Czech Republic` -> `Czechia`
- `DR Congo` -> `Democratic Republic of Congo`
- `Bosnia & Herzegovina` -> `Bosnia and Herzegovina`
- ELO 文件中的不间断空格会统一替换为普通空格。

## 如何重新生成数据

在项目根目录运行：

```bash
python3 scripts/build_baseline_data.py
python3 scripts/build_training_data.py
python3 scripts/train_match_result_model.py
python3 scripts/backtest_world_cup_model.py
python3 scripts/feature_ablation_backtest.py
python3 scripts/simulate_group_stage.py
```

脚本会重新生成世界杯 baseline、历史训练数据和模型预测：

- `data/processed/world_cup_2026_baseline.csv`
- `data/reports/world_cup_2026_baseline_quality.md`
- `data/processed/international_match_training.csv`
- `data/reports/international_match_training_quality.zh-CN.md`
- `models/match_result_v4_elo_ensemble_calibrated.joblib`
- `data/reports/match_result_model_v1.zh-CN.md`
- `data/reports/backtests/world_cup_backtest_report.zh-CN.md`
- `data/reports/ablations/feature_ablation_report.zh-CN.md`
- `data/processed/world_cup_2026_group_simulation.csv`
- `data/reports/group_simulation_v1.zh-CN.md`

API-Football 数据需要单独设置环境变量后运行：

```bash
API_FOOTBALL_KEY=你的_key python3 scripts/fetch_api_football_data.py
```

当前 Free plan 只能访问部分历史 season。2026 World Cup 数据、世界杯 injuries 数据目前不可用，需要更高权限或其他数据源。

## 后续建议

1. 先做一个基础胜平负模型，用 ELO 差值、近期状态、历史交锋作为核心特征。
2. 输出模型概率：主胜概率、平局概率、客胜概率，以及对应的 fair odds。
3. 做小组赛模拟，把淘汰赛里的 `1A`、`W73` 等占位符动态替换成真实球队分布。
4. 加入 Polymarket 映射层，例如 market slug、condition ID、outcome label、实时价格。
5. 用模型概率和 Polymarket 价格比较，计算 edge，筛选可能有交易价值的市场。
