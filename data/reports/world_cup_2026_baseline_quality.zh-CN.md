# 2026 世界杯 Baseline 数据质量报告

## 总览

- 赛程表原始行数：104
- Baseline 输出行数：104
- 已知双方球队的比赛：72
- 含淘汰赛占位符的比赛：32
- ELO 原始数据行数：6678
- 历史比赛原始数据行数：51607
- 已知球队比赛中 ELO 缺失数量：0

结论：当前 baseline 表可以作为第一版预测模型的数据底座。小组赛已知球队的 ELO 全部匹配成功，历史交锋和近期状态也已成功生成。淘汰赛阶段因为赛程中仍然是占位符，所以相关球队特征暂时留空，这是预期行为。

## 数据源

当前使用了三份数据：

- 世界杯赛程表：`/Users/jay/Desktop/FIFA/DATA/赛程表.csv`
- 国家队 ELO rating：`/Users/jay/Desktop/FIFA/DATA/elo ratings 1872-2025.csv`
- 历史国家队比赛结果：`/Users/jay/Desktop/FIFA/DATA/International results from 1872 to 2026 daily update 20260608/all_matches.csv`

## 合并逻辑

baseline 表以世界杯赛程表为主表，保留赛程中的每一场比赛。

对每场比赛：

- 根据主队、客队名称匹配 ELO 表。
- 取比赛日期之前，该球队最新的一条 ELO 记录。
- 根据历史比赛表计算双方最近 10 场状态。
- 根据历史比赛表计算双方过往交锋记录。
- 如果球队名是 `1A`、`2B`、`W73` 等淘汰赛占位符，则保留该行，但球队相关特征留空。

## 名称标准化

不同数据源中有些国家队名称写法不同，已在脚本中统一：

- `USA` -> `United States`
- `Czech Republic` -> `Czechia`
- `DR Congo` -> `Democratic Republic of Congo`
- `Bosnia & Herzegovina` -> `Bosnia and Herzegovina`
- ELO 数据中存在不间断空格，已统一替换为普通空格。

标准化之后：

- ELO 表中没有未匹配的已知球队。
- 历史比赛表中没有未匹配的已知球队。

## 日期质量

ELO 文件中的日期格式并不完全一致：

- 早期记录类似 `1872-11-30`
- 后期记录类似 `12/13/2025`

构建脚本已加入混合日期格式解析，避免后期 ELO 被解析为空。

## 淘汰赛占位符

当前赛程表中有 32 场比赛包含占位符，例如：

- `1A`
- `2B`
- `3A/B/C/D/F`
- `W73`
- `L101`

这些并不是数据错误，而是世界杯赛程在赛前的正常表达方式。它们需要等到小组赛结果确定，或者通过模拟小组赛晋级路径后，才能替换成真实球队。

baseline 表中用以下字段标记：

- `home_is_placeholder`
- `away_is_placeholder`

## 当前可用性判断

当前 baseline 数据适合用于：

- 小组赛单场胜平负概率预测。
- 初步模型训练或规则模型打分。
- ELO 差值分析。
- 球队近期状态分析。
- 历史交锋分析。
- 后续接入 Polymarket 市场数据的基础表。

当前 baseline 数据暂时不适合直接用于：

- 精确预测淘汰赛具体对阵。
- 直接计算冠军、晋级四强等路径型市场概率。
- 未经过模拟的 Polymarket 长期市场定价。

这些能力需要在下一步加入小组赛积分模拟和淘汰赛路径模拟。

## 建议的下一步

1. 先基于 72 场小组赛已知对阵，做第一版胜平负概率模型。
2. 给 baseline 增加模型输出字段，例如 `home_win_prob`、`draw_prob`、`away_win_prob`。
3. 加入 implied odds / fair odds 计算。
4. 建立 Polymarket 市场映射表，把比赛、球队、市场 outcome 对齐。
5. 做小组赛和淘汰赛 Monte Carlo 模拟，用于路径型市场。
