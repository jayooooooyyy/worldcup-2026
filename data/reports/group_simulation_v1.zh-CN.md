# 2026 世界杯小组赛 Monte Carlo 模拟报告

- 模拟次数：20000
- 输入：`world_cup_2026_predictions_final.csv` 中的 calibrated_v3 单场胜平负概率
- 比分生成：从 1990 年以来历史国家队比赛中，按胜/平/负结果抽取相同方向的历史比分
- 小组排名规则近似：积分、净胜球、进球数、随机微小扰动
- 晋级规则：每组前二直接晋级，12 个小组第三中排名最好的 8 队晋级

## 各组出线概率

### Group A
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Mexico | 5.2616 | 0.4274 | 0.2828 | 0.1937 | 0.8591 | 0.1409 |
| Czechia | 4.3855 | 0.2654 | 0.2903 | 0.2785 | 0.7567 | 0.2433 |
| South Korea | 4.2374 | 0.2410 | 0.2882 | 0.2722 | 0.7206 | 0.2794 |
| South Africa | 2.3720 | 0.0662 | 0.1388 | 0.2555 | 0.3600 | 0.6400 |

### Group B
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Switzerland | 6.2613 | 0.5630 | 0.2877 | 0.1101 | 0.9402 | 0.0598 |
| Canada | 5.2133 | 0.3159 | 0.4093 | 0.1969 | 0.8761 | 0.1239 |
| Bosnia and Herzegovina | 3.2197 | 0.0862 | 0.2041 | 0.4353 | 0.5683 | 0.4317 |
| Qatar | 1.8837 | 0.0349 | 0.0989 | 0.2577 | 0.2736 | 0.7265 |

### Group C
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | 5.7421 | 0.4956 | 0.2779 | 0.1623 | 0.9035 | 0.0965 |
| Morocco | 4.2092 | 0.2056 | 0.3069 | 0.3167 | 0.7399 | 0.2601 |
| Scotland | 4.3120 | 0.2455 | 0.2984 | 0.2785 | 0.7350 | 0.2650 |
| Haiti | 2.1453 | 0.0534 | 0.1168 | 0.2425 | 0.3180 | 0.6821 |

### Group D
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Turkey | 4.9736 | 0.4014 | 0.2685 | 0.1976 | 0.8190 | 0.1810 |
| Paraguay | 4.0176 | 0.2326 | 0.2627 | 0.2651 | 0.6835 | 0.3165 |
| United States | 3.6470 | 0.1890 | 0.2448 | 0.2668 | 0.6180 | 0.3820 |
| Australia | 3.5044 | 0.1770 | 0.2240 | 0.2705 | 0.5826 | 0.4174 |

### Group E
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Germany | 5.6311 | 0.4222 | 0.3560 | 0.1585 | 0.9012 | 0.0988 |
| Ecuador | 5.6461 | 0.4390 | 0.3322 | 0.1618 | 0.8969 | 0.1031 |
| Ivory Coast | 2.9833 | 0.0881 | 0.1868 | 0.3736 | 0.4991 | 0.5009 |
| Curaçao | 2.2719 | 0.0507 | 0.1250 | 0.3062 | 0.3569 | 0.6431 |

### Group F
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Netherlands | 5.9873 | 0.5518 | 0.2601 | 0.1293 | 0.9146 | 0.0854 |
| Japan | 4.6571 | 0.2641 | 0.3623 | 0.2398 | 0.7965 | 0.2035 |
| Tunisia | 2.9808 | 0.1072 | 0.1993 | 0.3085 | 0.4929 | 0.5071 |
| Sweden | 2.7642 | 0.0767 | 0.1784 | 0.3224 | 0.4533 | 0.5467 |

### Group G
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Belgium | 5.9782 | 0.5604 | 0.2515 | 0.1285 | 0.9127 | 0.0873 |
| Iran | 4.3976 | 0.2352 | 0.3386 | 0.2567 | 0.7556 | 0.2444 |
| New Zealand | 3.0031 | 0.1041 | 0.2059 | 0.3118 | 0.5060 | 0.4940 |
| Egypt | 2.9800 | 0.1003 | 0.2041 | 0.3029 | 0.4878 | 0.5122 |

### Group H
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Spain | 6.5574 | 0.6250 | 0.2437 | 0.0955 | 0.9479 | 0.0521 |
| Uruguay | 4.7834 | 0.2480 | 0.4181 | 0.2238 | 0.8212 | 0.1788 |
| Saudi Arabia | 2.6686 | 0.0674 | 0.1736 | 0.3357 | 0.4300 | 0.5700 |
| Cape Verde | 2.5930 | 0.0595 | 0.1646 | 0.3450 | 0.4207 | 0.5793 |

### Group I
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| France | 5.7924 | 0.4830 | 0.3078 | 0.1499 | 0.9098 | 0.0902 |
| Norway | 5.1703 | 0.3570 | 0.3427 | 0.2056 | 0.8522 | 0.1478 |
| Senegal | 3.5637 | 0.1187 | 0.2483 | 0.4062 | 0.6381 | 0.3619 |
| Iraq | 1.9381 | 0.0413 | 0.1011 | 0.2382 | 0.2757 | 0.7243 |

### Group J
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Argentina | 6.5395 | 0.6650 | 0.2130 | 0.0877 | 0.9502 | 0.0498 |
| Austria | 3.9383 | 0.1543 | 0.3417 | 0.2968 | 0.6922 | 0.3078 |
| Algeria | 3.1987 | 0.1040 | 0.2507 | 0.3065 | 0.5392 | 0.4608 |
| Jordan | 2.7441 | 0.0768 | 0.1946 | 0.3091 | 0.4574 | 0.5426 |

### Group K
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| Portugal | 5.4036 | 0.3990 | 0.3480 | 0.1767 | 0.8823 | 0.1177 |
| Colombia | 5.5060 | 0.4398 | 0.3116 | 0.1718 | 0.8823 | 0.1177 |
| Uzbekistan | 2.9971 | 0.0979 | 0.1941 | 0.3387 | 0.4968 | 0.5032 |
| Democratic Republic of Congo | 2.4880 | 0.0633 | 0.1464 | 0.3127 | 0.3947 | 0.6053 |

### Group L
| team | avg_points | prob_group_1st | prob_group_2nd | prob_group_3rd | prob_advance | prob_eliminated |
| --- | --- | --- | --- | --- | --- | --- |
| England | 6.1050 | 0.5541 | 0.2639 | 0.1325 | 0.9268 | 0.0732 |
| Croatia | 4.6932 | 0.2536 | 0.3609 | 0.2648 | 0.8098 | 0.1902 |
| Panama | 3.6237 | 0.1457 | 0.2600 | 0.3377 | 0.6260 | 0.3740 |
| Ghana | 2.1052 | 0.0466 | 0.1153 | 0.2649 | 0.3194 | 0.6806 |
