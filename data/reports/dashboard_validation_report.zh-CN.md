# Dashboard 输出校验报告

## Summary

- 总赛程：104 场
- 小组赛：72 场
- 已知球队预测：72 场
- 淘汰赛 placeholder：32 场
- 概率加总为 100%：True
- Fair odds = 1 / probability：True
- Favorite 来自 winner model：True
- Winner model 版本一致：True
- Probability model note 一致：True
- Placeholder 单独处理：True

## 模型口径

- Winner model：`v4_elo_ensemble_calibrated_v1`
- Probability model：`calibrated_v3_floor_010_T1.2`
- Draw 不作为 final pick，只作为 risk signal。

## 异常行

没有发现异常行。
