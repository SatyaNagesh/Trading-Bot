# COMP3 Diversification Research — Development Study (Phases 4-11)

Pre-registered in `reports/COMP3_DIVERSIFICATION_PREREG_2026-09.md`.

### D1 cap selection (dev-TRAIN): **C = 8%** — top5<30% AND expectancy>0 (12.5% endpoint excluded). C=12.5% endpoint (=D2 quintile) is reported but excluded from selection (Amendment 1).

| Cap | m/side | train exp bps | train top5 | train net% | val exp bps | val top5 | val net% |
|---|---|---|---|---|---|---|---|
| 5% | 20 | 8.5888 | 0.3658 | 37.6354 | 7.1531 | 1.2294 | 3.8969 |
| 6% | 17 | 9.3588 | 0.5936 | 41.3094 | 11.1733 | 1.4074 | 6.1914 |
| 8% | 13 | 8.6601 | 0.103 | 36.6876 | 16.4837 | 0.9403 | 9.2632 |
| 10% | 10 | 5.1534 | 0.3915 | 18.5047 | 19.9786 | 0.9392 | 11.2464 |
| 12% (excluded) | 8 | 5.37 | 0.2766 | 18.7336 | 27.1206 | 0.6186 | 15.4361 |

### Constructions @25bp (full dev)

| Name | net% | exp bps | PF | MDD% | Sharpe | top5 | HHI | sign flips |
|---|---|---|---|---|---|---|---|---|
| V1_DECILE_EQ | 50.358 | 10.549 | 1.1562 | -30.4116 | 0.8754 | 0.5751 | 0.1267 | 0 |
| D2 | 46.8502 | 9.1795 | 1.1902 | -12.2359 | 1.0466 | 0.259 | 0.0612 | 0 |
| D1_CAP5 | 53.3619 | 9.4779 | 1.3581 | -11.5944 | 1.8306 | 0.3647 | 0.0291 | 0 |
| D1_CAP6 | 59.9952 | 10.4693 | 1.3543 | -11.5212 | 1.8054 | 0.5614 | 0.0333 | 0 |
| D1_CAP8 | 60.7598 | 10.7285 | 1.3021 | -11.414 | 1.5791 | 0.4504 | 0.0481 | 0 |
| D1_CAP10 | 41.8476 | 8.2388 | 1.1955 | -14.3782 | 1.0548 | 0.5622 | 0.0552 | 0 |
| D1_CAP12 | 46.8502 | 9.1795 | 1.1902 | -12.2359 | 1.0466 | 0.259 | 0.0612 | 0 |

See `reports/comp3_diversification_results.json` for full metrics incl. 50/100bp cost stress, regimes, sectors, walk-forward and tail. Holdout-5 was not touched.