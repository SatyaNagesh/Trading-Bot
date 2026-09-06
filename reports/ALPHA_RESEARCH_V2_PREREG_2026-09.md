# Alpha Research V2 — Pre-registration (frozen 2026-09-06)

- **Frozen commit:** `2026-09-06T13:43:41.603398+05:30`
- **Features:** 43 | **Hypotheses tested:** 168 (feature x horizon pairs)
- **Selection gate:** BH-FDR q<=0.10 across all hypotheses on development-VALIDATION + sign replication + |IC_final| >= 0.4 x |IC_validation| on development-FINAL-OOS.
- **Costs:** 25.0 bps/side primary, 50.0 stress, 15.0 sensitivity.
- **Confirmation:** ANY future confirmation requires a GENUINELY UNTOUCHED corpus (holdout_3 or later); the frozen 60-symbol holdout is consumed and NOT confirmatory; holdout_2 is reserved for V1 transform confirmation and NOT reused here. DO NOT CLAIM CONFIRMATION; classify as PROMISING-NEEDS-NEW-HOLDOUT.

## Family A — rel_strength
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| A1_rs_mkt_10 | cumret(10d) - index_cumret(10d) | 10 | 10-day return of the symbol minus equal-weight universe return; standard relative strength. | [1, 3, 5, 10, 20] |
| A2_rs_mkt_20 | cumret(20d) - index_cumret(20d) | 20 | 20-day relative strength vs market. | [1, 3, 5, 10, 20] |
| A3_rs_mkt_60 | cumret(60d) - index_cumret(60d) | 60 | 60-day (medium-term) relative strength vs market. | [1, 3, 5, 10, 20] |
| A4_rs_sector_20 | cumret(20d) - sector_mean_cumret(20d) | 20 | 20-day return relative to same-sector equal-weight mean (>=3 members). | [1, 3, 5, 10, 20] |
| A5_rs_accel_10 | A1(t) - A1(t-5) | 15 | Acceleration of 10-day relative strength (change over prior 5 days). | [1, 3, 5, 10, 20] |
| A6_rs_voladj_20 | (cumret(20d) - index_cumret(20d)) / rv20 | 20 | Volatility-adjusted relative strength (Sharpe-style RS). | [1, 3, 5, 10, 20] |

## Family B — xs_momentum
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| B1_mom_5 | date_percentile_rank(cumret(5d)) | 5 | Cross-sectional percentile rank of 5d historical return at date t. | [1, 3, 5, 10, 20] |
| B2_mom_10 | date_percentile_rank(cumret(10d)) | 10 | Cross-sectional percentile rank of 10d historical return at date t. | [1, 3, 5, 10, 20] |
| B3_mom_20 | date_percentile_rank(cumret(20d)) | 20 | Cross-sectional percentile rank of 20d historical return at date t. | [1, 3, 5, 10, 20] |
| B4_mom_60 | date_percentile_rank(cumret(60d)) | 60 | Cross-sectional percentile rank of 60d historical return at date t. | [1, 3, 5, 10, 20] |
| B5_mom_voladj_20 | date_percentile_rank(cumret(20d)/rv20) | 20 | Cross-sectional rank of volatility-adjusted 20d momentum. | [1, 3, 5, 10, 20] |

## Family C — reversal
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| C1_rev_ret1 | ret(1d) = close_t/close_{t-1} - 1 | 1 | 1-day return; canonical short-term reversal candidate (expected negative). | [1, 3, 5] |
| C2_rev_ret2 | close_t/close_{t-2} - 1 | 2 | 2-day return; reversal at slightly longer horizon. | [1, 3, 5] |
| C3_rev_abn_mkt1 | ret(1d) - index_ret(1d) | 1 | Abnormal 1-day return vs market; idiosyncratic move reversal. | [1, 3, 5] |
| C4_rev_dist_mean20 | close_t/SMA(close,20) - 1 | 20 | Distance from 20-day mean; mean-reversion distance gauge. | [1, 3, 5] |
| C5_rev_volshock | ret(1d) x (rv20 / rolling_median(rv20,252)) | 252 | Overnight/1-day move compounded by a volatility-shock multiplier; does an extreme move on a shock day revert? | [1, 3, 5] |

## Family D — gap
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| D1_gap_overnight | open_t/close_{t-1} - 1 | 1 | Overnight return (close->open). | [1, 3] |
| D2_gap_intraday | close_t/open_t - 1 | 1 | Intraday return (open->close); isolates where any gap effect lives. | [1, 3] |
| D3_gap_mag_atr | abs(open_t - close_{t-1}) / ATR(14) | 14 | Gap magnitude scaled by recent true-range; big-gap fill hypothesis. | [1, 3] |
| D4_gap_dir_trend | sign(open_t - close_{t-1}) x sign(close_{t-1}-close_{t-6}) | 6 | Gap direction vs prior 5-day trend aligned(+1)/against(-1)/zero. | [1, 3] |
| D5_gap_vol_conf | D1_gap_overnight x volume_t/SMA(volume,20) | 20 | Overnight gap with volume confirmation. | [1, 3] |

## Family E — breakout
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| E1_dist_high20 | close_t/rolling_max(high,20) - 1 | 20 | Distance below recent 20d high (<=0); breakout proximity. | [1, 3, 5, 10, 20] |
| E2_dist_low20 | close_t/rolling_min(low,20) - 1 | 20 | Distance above recent 20d low (>=0); breakdown proximity. | [1, 3, 5, 10, 20] |
| E3_break_mag20 | rolling_max(high,20)/rolling_max(high,60) - 1 | 60 | Magnitude of the recent 20d excursion vs prior 60d span. | [1, 3, 5, 10, 20] |
| E4_break_vol_exp | (close_t >= rolling_max(high,20).shift(1)) x volume_t/SMA(volume,20) | 20 | New-20d-high day indicator weighted by relative volume (volume-confirmed breakout). | [1, 3, 5, 10, 20] |
| E5_break_cont5 | rolling_mean(break_new20, 5) | 20 | Fraction of last 5 days that printed a new 20d high (breakout frequency). | [1, 3, 5, 10, 20] |

## Family F — volume_price
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| F1_vol_rel20 | volume_t/SMA(volume,20) | 20 | Relative volume; spike/quiet gauge. | [1, 3, 5] |
| F2_vol_accel | SMA(volume,5)/SMA(volume,25) - 1 | 25 | Short volume acceleration (distinct from the failed vol_trend_10v50). | [1, 3, 5] |
| F3_px_vol_int | cumret(20d) x volume_t/SMA(volume,20) | 20 | Price x volume interaction at date t (trend x participation). | [1, 3, 5] |
| F4_abn_vol_ret | sign(ret(1d)) x volume_t/SMA(volume,20) | 20 | Abnormal volume paired with the sign of today's return. | [1, 3, 5] |
| F5_vol_conf_mom | B3_mom_20 x volume_t/SMA(volume,20) | 20 | Volume-confirmed cross-sectional momentum (rank x relative volume). | [1, 3, 5] |

## Family G — breadth_dispersion
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| G1_breadth_rise | fraction(symbols with ret(1d) > 0) | 1 | Cross-sectional fraction of risers at date t. | [1, 3, 5] |
| G2_breadth_ma20 | fraction(close_t > SMA(close,20)) | 20 | Fraction of symbols above their 20-day mean. | [1, 3, 5] |
| G3_breadth_ma50 | fraction(close_t > SMA(close,50)) | 50 | Fraction of symbols above their 50-day mean. | [1, 3, 5] |
| G4_xs_ret_disp | cross-sectional std(ret(1d)) | 1 | Cross-sectional return dispersion (breadth of moves). | [1, 3, 5] |
| G5_xs_vol_disp | cross-sectional std(log1p(rv20)) | 20 | Cross-sectional realized-volatility dispersion. | [1, 3, 5] |
| G6_breadth_mom5 | G1(t) - G1(t-5) | 5 | Breadth momentum: change in the rise-fraction over 5 days. | [1, 3, 5] |

## Family H — vol_structure
| key | formula | lookback | interpretation | horizons |
|---|---|---|---|---|
| H1_vol_exp5 | rv20_t/rv20_{t-5} - 1 | 25 | Volatility expansion rate over 5 days. | [1, 3, 5, 10, 20] |
| H2_vol_cont20 | rv20_t/rv20_{t-20} - 1 | 40 | Volatility change over 20 days (negative = contraction). | [1, 3, 5, 10, 20] |
| H3_rv_ratio_10_60 | rv10/rv60 - 1 | 60 | Short/long realized-vol ratio (vol term-structure tilt). | [1, 3, 5, 10, 20] |
| H4_vol_shock | rv20/rolling_median(rv20,252) - 1 | 252 | Realized-vol shock vs trailing median. | [1, 3, 5, 10, 20] |
| H5_vol_vs_mkt | log1p(rv20) - date_mean(log1p(rv20)) | 20 | Idiosyncratic (market-demeaned) log volatility level. | [1, 3, 5, 10, 20] |
| H6_xs_vol_rank | date_percentile_rank(rv20) | 20 | Cross-sectional rank of realized volatility. | [1, 3, 5, 10, 20] |

## Exclusion rules
- warm-up NaNs (lookback not yet satisfied) are excluded per feature
- cross-sectional ranks are computed only on dates with >= MIN_CS valid symbols
- sector-relative features require >= MIN_SECTOR same-sector members at t
- forward labels are the frozen fwd_ret_{h} (strictly future) fields
- split filters are applied AFTER feature computation (full-history lookbacks)

> Definition freeze: formulas and horizons were written BEFORE any evaluation. They will not be changed after holdout results are seen.