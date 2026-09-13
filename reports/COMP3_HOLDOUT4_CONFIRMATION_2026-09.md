# COMP3 holdout-4 Confirmation (Phase 12M)

- **Grade:** `E CONCENTRATION-FRAGILE` — top-5 share>=50% or sign flip on leave-one-out
- **Corpus lock:** OK locked=8154a050868f15e4f336520c3e2c49c89f0a781412cb9c0a1b2ad43bff673e11 actual=8154a050868f15e4f336520c3e2c49c89f0a781412cb9c0a1b2ad43bff673e11
- **Score:** COMP3_REVERSAL_BREADTH_DISP

### quintile_eq (primary)
```
{
 "25": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 116.2352,
  "net_cum_pct": 115.1408,
  "avg_net_bps": 9.1482,
  "median_net_bps": 7.5523,
  "expectancy_bps": 9.1482,
  "win_rate": 0.5209,
  "profit_factor": 1.1906,
  "max_drawdown_pct": -20.4711,
  "sharpe": 1.072,
  "sortino": 1.7422,
  "worst_day_bps": -472.7803,
  "best_day_bps": 479.3673
 },
 "50": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 116.2352,
  "net_cum_pct": 114.0464,
  "avg_net_bps": 9.0945,
  "median_net_bps": 7.5523,
  "expectancy_bps": 9.0945,
  "win_rate": 0.5209,
  "profit_factor": 1.1893,
  "max_drawdown_pct": -20.4711,
  "sharpe": 1.065,
  "sortino": 1.7293,
  "worst_day_bps": -472.7803,
  "best_day_bps": 479.3673
 },
 "100": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 116.2352,
  "net_cum_pct": 111.8576,
  "avg_net_bps": 8.9871,
  "median_net_bps": 7.5523,
  "expectancy_bps": 8.9871,
  "win_rate": 0.5209,
  "profit_factor": 1.1866,
  "max_drawdown_pct": -20.4711,
  "sharpe": 1.0507,
  "sortino": 1.6996,
  "worst_day_bps": -472.7803,
  "best_day_bps": 479.3673
 }
}
```
### decile_eq (comparison)
```
{
 "25": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 364.714,
  "net_cum_pct": 362.3797,
  "avg_net_bps": 18.5234,
  "median_net_bps": 15.6398,
  "expectancy_bps": 18.5234,
  "win_rate": 0.5424,
  "profit_factor": 1.2671,
  "max_drawdown_pct": -22.7608,
  "sharpe": 1.4449,
  "sortino": 2.4281,
  "worst_day_bps": -917.4973,
  "best_day_bps": 803.19
 },
 "50": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 364.714,
  "net_cum_pct": 360.0454,
  "avg_net_bps": 18.4697,
  "median_net_bps": 15.6398,
  "expectancy_bps": 18.4697,
  "win_rate": 0.5424,
  "profit_factor": 1.2662,
  "max_drawdown_pct": -22.7608,
  "sharpe": 1.4405,
  "sortino": 2.4217,
  "worst_day_bps": -917.4973,
  "best_day_bps": 803.19
 },
 "100": {
  "status": "OK",
  "active_days": 931,
  "avg_turnover": 0.0021,
  "gross_cum_pct": 364.714,
  "net_cum_pct": 355.3769,
  "avg_net_bps": 18.3623,
  "median_net_bps": 15.6398,
  "expectancy_bps": 18.3623,
  "win_rate": 0.5424,
  "profit_factor": 1.2642,
  "max_drawdown_pct": -22.7608,
  "sharpe": 1.4313,
  "sortino": 2.4059,
  "worst_day_bps": -917.4973,
  "best_day_bps": 803.19
 }
}
```
### concentration / tail / uncertainty
```
{
 "concentration": {
  "base_net_cum_pct": 115.1408,
  "top5_share_abs": 0.3864,
  "top5": {
   "IDEA_NS": 0.24468,
   "NATIONALUM_NS": 0.19287,
   "APOLLOTYRE_NS": 0.15118,
   "BASF_NS": -0.14607,
   "HINDCOPPER_NS": -0.11355
  },
  "top10": {
   "IDEA_NS": 0.24468,
   "NATIONALUM_NS": 0.19287,
   "APOLLOTYRE_NS": 0.15118,
   "BASF_NS": -0.14607,
   "HINDCOPPER_NS": -0.11355,
   "MFSL_NS": 0.10615,
   "CHAMBLFERT_NS": 0.10599,
   "SUNTV_NS": 0.10091,
   "LTTS_NS": -0.09698,
   "IPCALAB_NS": 0.09642
  },
  "leave_one_out_sign_flips": [
   "CHOLAHLDNG_NS",
   "ADANIENSOL_NS",
   "SYNGENE_NS"
  ],
  "leave_one_out": {
   "CHOLAHLDNG_NS": -0.0062,
   "ADANIENSOL_NS": -0.0272,
   "SYNGENE_NS": -0.0055,
   "LTTS_NS": 0.083,
   "AMBER_NS": 0.0537,
   "HAL_NS": 0.0666,
   "DALBHARAT_NS": 0.127,
   "POWERINDIA_NS": 0.1142,
   "POLICYBZR_NS": 0.3678,
   "STARHEALTH_NS": 0.3709,
   "JIOFIN_NS": 0.3733
  },
  "concentration_fragile": true
 },
 "tail": {
  "full": {
   "n": 931,
   "net_cum_pct": 115.1408,
   "worst_day_bps": -472.7803,
   "share_of_full": 10000.0
  },
  "winsorized_1pct": {
   "n": 931,
   "net_cum_pct": 118.5965,
   "worst_day_bps": -307.6607,
   "share_of_full": 10300.1
  },
  "drop_1pct": {
   "n": 911,
   "net_cum_pct": 113.1696,
   "worst_day_bps": -299.2467,
   "share_of_full": 9828.8
  },
  "drop_5pct": {
   "n": 837,
   "net_cum_pct": 103.1409,
   "worst_day_bps": -214.6789,
   "share_of_full": 8957.8
  }
 },
 "uncertainty": {
  "n_days": 931,
  "autocorr_lag1": -0.050741292493878834,
  "n_eff": 1030,
  "block_size": 47,
  "sims": 5000,
  "ci95_expectancy_bps": [
   0.6482,
   17.6061
  ]
 }
}
```

Single locked evaluation. Negative results are reported as-is; no reruns.