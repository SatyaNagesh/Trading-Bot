# COMP3 STRATEGY V2 — Holdout-5 Confirmation (Phase 12-14)

- **Grade:** `D STILL CONCENTRATION-FRAGILE` — top-5 share>=30% or sign flip on leave-one-out
- **Paper-trading gate (Phase 15):** DO NOT PAPER TRADE — gate closed
- **Corpus lock:** OK locked=13a1eeb11cac628b711b146efff1c0b89548c695ef8884c63790e12dbcba7833 actual=13a1eeb11cac628b711b146efff1c0b89548c695ef8884c63790e12dbcba7833
- **Score:** COMP3_REVERSAL_BREADTH_DISP
- **D1_CAP8 (PRIMARY) @25bps:** net 67.8948% exp 6.0719bps MDD -38.9431% top5 0.2179

### Phase 15 gates
```
{
 "positive_net_expectancy": true,
 "sufficient_sample": true,
 "acceptable_drawdown": true,
 "acceptable_concentration": false,
 "positive_under_realistic_costs": true,
 "temporal_robustness": true,
 "no_leakage": true
}
```

### D1_CAP8 (PRIMARY (diversified D1, cap C=8%))
```
{
 "25": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 12.97,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 68.7396,
  "net_cum_pct": 67.8948,
  "avg_net_bps": 6.0719,
  "median_net_bps": 6.3185,
  "expectancy_bps": 6.0719,
  "win_rate": 0.5279,
  "profit_factor": 1.1623,
  "max_drawdown_pct": -38.9431,
  "sharpe": 0.8712,
  "sortino": 1.3294,
  "worst_day_bps": -636.8493,
  "best_day_bps": 640.0474
 },
 "50": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 12.97,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 68.7396,
  "net_cum_pct": 67.05,
  "avg_net_bps": 6.0193,
  "median_net_bps": 6.3185,
  "expectancy_bps": 6.0193,
  "win_rate": 0.5279,
  "profit_factor": 1.1607,
  "max_drawdown_pct": -38.9431,
  "sharpe": 0.8633,
  "sortino": 1.3177,
  "worst_day_bps": -636.8493,
  "best_day_bps": 640.0474
 },
 "100": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 12.97,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 68.7396,
  "net_cum_pct": 65.3604,
  "avg_net_bps": 5.9139,
  "median_net_bps": 6.3185,
  "expectancy_bps": 5.9139,
  "win_rate": 0.5279,
  "profit_factor": 1.1574,
  "max_drawdown_pct": -38.9431,
  "sharpe": 0.847,
  "sortino": 1.2901,
  "worst_day_bps": -636.8493,
  "best_day_bps": 640.0474
 }
}
```
### D2_QUINTILE (control (quintile EW = V1 quintile))
```
{
 "25": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 8.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 48.4813,
  "net_cum_pct": 47.7348,
  "avg_net_bps": 5.1436,
  "median_net_bps": -0.2441,
  "expectancy_bps": 5.1436,
  "win_rate": 0.4963,
  "profit_factor": 1.1017,
  "max_drawdown_pct": -51.1686,
  "sharpe": 0.5681,
  "sortino": 0.8745,
  "worst_day_bps": -806.1963,
  "best_day_bps": 812.7939
 },
 "50": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 8.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 48.4813,
  "net_cum_pct": 46.9884,
  "avg_net_bps": 5.0909,
  "median_net_bps": -0.2441,
  "expectancy_bps": 5.0909,
  "win_rate": 0.4963,
  "profit_factor": 1.1005,
  "max_drawdown_pct": -51.1686,
  "sharpe": 0.5621,
  "sortino": 0.8652,
  "worst_day_bps": -806.1963,
  "best_day_bps": 812.7939
 },
 "100": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 8.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 48.4813,
  "net_cum_pct": 45.4955,
  "avg_net_bps": 4.9855,
  "median_net_bps": -0.2441,
  "expectancy_bps": 4.9855,
  "win_rate": 0.4963,
  "profit_factor": 1.0982,
  "max_drawdown_pct": -51.1686,
  "sharpe": 0.5499,
  "sortino": 0.8452,
  "worst_day_bps": -806.1963,
  "best_day_bps": 812.7939
 }
}
```
### V1_DECILE (V1 benchmark (decile EW, concentrated))
```
{
 "25": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 4.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 51.4471,
  "net_cum_pct": 50.6867,
  "avg_net_bps": 6.6764,
  "median_net_bps": 14.8687,
  "expectancy_bps": 6.6764,
  "win_rate": 0.5416,
  "profit_factor": 1.0884,
  "max_drawdown_pct": -59.5783,
  "sharpe": 0.4885,
  "sortino": 0.6977,
  "worst_day_bps": -1212.9859,
  "best_day_bps": 1316.4521
 },
 "50": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 4.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 51.4471,
  "net_cum_pct": 49.9263,
  "avg_net_bps": 6.6237,
  "median_net_bps": 14.8687,
  "expectancy_bps": 6.6237,
  "win_rate": 0.5416,
  "profit_factor": 1.0876,
  "max_drawdown_pct": -59.5783,
  "sharpe": 0.4846,
  "sortino": 0.6924,
  "worst_day_bps": -1212.9859,
  "best_day_bps": 1316.4521
 },
 "100": {
  "status": "OK",
  "active_days": 949,
  "avg_positions_side": 4.0,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 51.4471,
  "net_cum_pct": 48.4055,
  "avg_net_bps": 6.5184,
  "median_net_bps": 14.8687,
  "expectancy_bps": 6.5184,
  "win_rate": 0.5416,
  "profit_factor": 1.0861,
  "max_drawdown_pct": -59.5783,
  "sharpe": 0.4767,
  "sortino": 0.6812,
  "worst_day_bps": -1212.9859,
  "best_day_bps": 1316.4521
 }
}
```
### concentration / tail / regimes / sectors
```
{
 "concentration": {
  "D1_CAP8": {
   "top1_share": 0.2015,
   "top3_share": 0.2159,
   "top5_share": 0.2179,
   "top10_share": 0.6279,
   "herfindahl_gross": 0.1158,
   "max_single_weight": 0.0833,
   "pct_days_concentrated": 0.0,
   "leave_one_out_sign_flips": [
    "HATSUN_NS",
    "LAURUSLABS_NS",
    "GODREJAGRO_NS",
    "NIACL_NS",
    "ASTERDM_NS",
    "BANDHANBNK_NS",
    "FINEORG_NS",
    "CREDITACC_NS",
    "RVNL_NS",
    "KPITTECH_NS",
    "HOMEFIRST_NS",
    "CRAFTSMAN_NS",
    "DEVYANI_NS",
    "DELHIVERY_NS"
   ],
   "leave_one_out": {
    "HATSUN_NS": -0.0593,
    "LAURUSLABS_NS": -0.145,
    "GODREJAGRO_NS": -0.1558,
    "NIACL_NS": -0.1347,
    "ASTERDM_NS": -0.127,
    "BANDHANBNK_NS": -0.1538,
    "FINEORG_NS": -0.1657,
    "CREDITACC_NS": -0.1798,
    "RVNL_NS": -0.2538,
    "KPITTECH_NS": -0.2525,
    "HOMEFIRST_NS": -0.1712,
    "CRAFTSMAN_NS": -0.2015,
    "DEVYANI_NS": -0.1034,
    "DELHIVERY_NS": -0.0378
   },
   "concentration_fragile": true,
   "top5_pass": true
  },
  "D2_QUINTILE": {
   "top1_share": 0.3511,
   "top3_share": 0.3492,
   "top5_share": 0.3137,
   "top10_share": 0.2557,
   "herfindahl_gross": 0.189,
   "max_single_weight": 0.125,
   "pct_days_concentrated": 0.9694,
   "leave_one_out_sign_flips": [
    "HATSUN_NS",
    "LAURUSLABS_NS",
    "GODREJAGRO_NS",
    "NIACL_NS",
    "ASTERDM_NS",
    "BANDHANBNK_NS",
    "FINEORG_NS",
    "CREDITACC_NS",
    "RVNL_NS",
    "KPITTECH_NS",
    "HOMEFIRST_NS",
    "CRAFTSMAN_NS",
    "DEVYANI_NS",
    "DELHIVERY_NS"
   ],
   "leave_one_out": {
    "HATSUN_NS": -0.0323,
    "LAURUSLABS_NS": -0.1551,
    "GODREJAGRO_NS": -0.1765,
    "NIACL_NS": -0.1457,
    "ASTERDM_NS": -0.1953,
    "BANDHANBNK_NS": -0.2141,
    "FINEORG_NS": -0.2339,
    "CREDITACC_NS": -0.269,
    "RVNL_NS": -0.3535,
    "KPITTECH_NS": -0.3517,
    "HOMEFIRST_NS": -0.1822,
    "CRAFTSMAN_NS": -0.2455,
    "DEVYANI_NS": -0.1866,
    "DELHIVERY_NS": -0.1859
   },
   "concentration_fragile": true,
   "top5_pass": false
  },
  "V1_DECILE": {
   "top1_share": 0.4948,
   "top3_share": 0.5553,
   "top5_share": 0.0307,
   "top10_share": 0.2753,
   "herfindahl_gross": 0.4905,
   "max_single_weight": 0.25,
   "pct_days_concentrated": 1.0,
   "leave_one_out_sign_flips": [
    "HATSUN_NS",
    "LAURUSLABS_NS",
    "GODREJAGRO_NS",
    "NIACL_NS",
    "ASTERDM_NS",
    "BANDHANBNK_NS",
    "FINEORG_NS",
    "CREDITACC_NS",
    "RVNL_NS",
    "KPITTECH_NS",
    "HOMEFIRST_NS",
    "CRAFTSMAN_NS",
    "DEVYANI_NS",
    "DELHIVERY_NS"
   ],
   "leave_one_out": {
    "HATSUN_NS": -0.0413,
    "LAURUSLABS_NS": -0.1021,
    "GODREJAGRO_NS": -0.0785,
    "NIACL_NS": -0.0001,
    "ASTERDM_NS": -0.054,
    "BANDHANBNK_NS": -0.0724,
    "FINEORG_NS": -0.1063,
    "CREDITACC_NS": -0.1643,
    "RVNL_NS": -0.2612,
    "KPITTECH_NS": -0.2547,
    "HOMEFIRST_NS": -0.1841,
    "CRAFTSMAN_NS": -0.2934,
    "DEVYANI_NS": -0.2641,
    "DELHIVERY_NS": -0.1656
   },
   "concentration_fragile": true,
   "top5_pass": true
  }
 },
 "tail": {
  "D1_CAP8": {
   "full": {
    "n": 949,
    "net_cum_pct": 67.8948,
    "worst_day_bps": -636.8493
   },
   "winsorized_1pct": {
    "n": 949,
    "net_cum_pct": 60.9407,
    "worst_day_bps": -292.7202
   },
   "drop_1pct": {
    "n": 929,
    "net_cum_pct": 62.1653,
    "worst_day_bps": -284.5322
   },
   "drop_5pct": {
    "n": 853,
    "net_cum_pct": 56.7331,
    "worst_day_bps": -165.1134
   }
  },
  "D2_QUINTILE": {
   "full": {
    "n": 949,
    "net_cum_pct": 47.7348,
    "worst_day_bps": -806.1963
   },
   "winsorized_1pct": {
    "n": 949,
    "net_cum_pct": 46.1579,
    "worst_day_bps": -374.7038
   },
   "drop_1pct": {
    "n": 929,
    "net_cum_pct": 44.2319,
    "worst_day_bps": -373.5517
   },
   "drop_5pct": {
    "n": 853,
    "net_cum_pct": 40.0235,
    "worst_day_bps": -207.3096
   }
  },
  "V1_DECILE": {
   "full": {
    "n": 949,
    "net_cum_pct": 50.6867,
    "worst_day_bps": -1212.9859
   },
   "winsorized_1pct": {
    "n": 949,
    "net_cum_pct": 51
```

### Walk-forward (half-year tiles, D1_CAP8): {"n_half_years": 26, "n_positive_half_years": 15, "half_year_net_pct": [-7.3026, 7.8991, -6.4995, -1.6817, -6.0622, 0.1891, -2.2749, 1.224, -2.5402, -6.8773, -2.7138, -11.0165, 8.8048, 5.659, 10.6522, 7.3597, 4.9448, 7.4098, 9.8793, 22.946, -5.4057, 11.1139, 5.5625, 1.1888, -1.6186, 8.6755]}

One locked evaluation on untouched holdout-5. Negative/uncertain results reported as-is; no reruns. Holdout-4 (+115%) is NOT used as confirmation.