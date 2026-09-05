"""Alpha discovery - panel construction.

Builds the analysis panel from the cleansed daily parquet store:

  index:  (symbol, timestamp)  [tz-aware Asia/Kolkata]
  cols:   per-symbol causal features (alpha_features)
          forward-return labels  fwd_ret_{1,3,5,10,20}  (strictly future)
          cross-sectional + market-context features (causal to date t)
          market regime label/signal (causal)
          split (TRAIN / VALIDATION / FINAL-OOS)

Labels are the ONLY future-referencing columns and are never used as features.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from packages.analytics.regime_observer import RegimeObserver
from packages.research.alpha_features import compute_symbol_features, _trailing_pctile

TZ = "Asia/Kolkata"
FORWARD_HORIZONS = [1, 3, 5, 10, 20]
INDEX_MEMBERS = "exclude_first_listing"  # fixed membership (48 full-history symbols)


def store_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "historical"


def load_splits(path: Path | None = None) -> dict:
    with (path or store_root() / "splits.json").open() as fh:
        raw = json.load(fh)
    out = {}
    for name, bounds in raw.items():
        out[name] = {
            "start": pd.Timestamp(bounds["start"], tz=TZ),
            "end": pd.Timestamp(bounds["end"], tz=TZ),
        }
    return out


def symbols_with_full_history() -> tuple[list[str], list[str]]:
    d1d = store_root() / "d1d"
    all_syms = sorted(p.stem for p in d1d.glob("*.parquet"))
    # find the first-listed (short-history) symbol by earliest start date
    starts = {}
    for s in all_syms:
        df = pd.read_parquet(d1d / f"{s}.parquet")
        starts[s] = df.index.min()
    first_listing = max(starts, key=starts.get)  # latest start = short-history symbol
    full = [s for s in all_syms if s != first_listing]
    return all_syms, full


def build_index(frame_close: pd.DataFrame) -> pd.Series:
    """Equal-weight universe index level from per-symbol close prices.

    ``frame_close`` is a DataFrame of close prices indexed by date, one column
    per symbol. Returns (daily index return series, index level series).
    """
    idx_ret = frame_close.pct_change().mean(axis=1)
    idx_level = (1.0 + idx_ret.fillna(0.0)).cumprod()
    return idx_ret, idx_level


def market_regime(index_level: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Causal market regime label + signed signal from RegimeObserver (PPD=1)."""
    obs = RegimeObserver(lookback=21, periods_per_day=1)
    labels = []
    seen: list[float] = []
    for i in range(len(index_level)):
        seen.append(float(index_level.iloc[i]))
        labels.append(obs.observe(seen, index_level.index[i]).value)
    lab = pd.Series(labels, index=index_level.index)
    sig = lab.map(
        lambda r: 1.0
        if r in ("trending", "breakout", "low_volatility")
        else (-1.0 if r in ("high_volatility", "volatile", "crisis") else 0.0)
    )
    return lab, sig.astype(float)


def build_panel(verbose: bool = True) -> pd.DataFrame:
    splits = load_splits()
    d1d = store_root() / "d1d"
    syms_all, syms_full = symbols_with_full_history()

    frames = []
    for s in syms_all:
        df = pd.read_parquet(d1d / f"{s}.parquet")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        feat = compute_symbol_features(df)
        feat["close"] = df["close"]
        # strictly-future labels: fwd_ret_h = close_{t+h}/close_t - 1
        c = df["close"]
        for h in FORWARD_HORIZONS:
            feat[f"fwd_ret_{h}"] = c.shift(-h) / c - 1.0
        f = feat.reset_index()
        f["symbol"] = s
        if "index" in f.columns:
            f = f.rename(columns={"index": "date"})
        elif "ts" in f.columns:
            f = f.rename(columns={"ts": "date"})
        frames.append(f)

    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"], utc=True).dt.tz_convert(TZ)
    panel = panel.set_index(["symbol", "date"]).sort_index()

    # --- market context (fixed-membership equal-weight index) ---
    ret_pivot = panel["close"].unstack("symbol")
    idx_ret, idx_level = build_index(ret_pivot[syms_full])
    mkt_factor = pd.DataFrame(index=idx_level.index)
    mkt_factor["mkt_ret_5d"] = idx_level.pct_change(5)
    mkt_factor["mkt_vol_20"] = idx_ret.rolling(20).std()
    lab, sig = market_regime(idx_level)
    mkt_factor["mkt_regime_label"] = lab
    mkt_factor["mkt_regime_signal"] = sig
    # causal regime buckets for conditioning (trend direction vs volatility percentile)
    mkt_factor["mkt_ret_20d"] = idx_level.pct_change(20)
    mkt_factor["mkt_vol_pctile_252"] = _trailing_pctile(mkt_factor["mkt_vol_20"], 252)
    trend = mkt_factor["mkt_ret_20d"].fillna(0.0)
    dir_bucket = np.where(trend > 0.02, "up",
                          np.where(trend < -0.02, "down", "sideways"))
    vol_bucket = np.where(mkt_factor["mkt_vol_pctile_252"].fillna(0.5) <= 0.34, "low_vol",
                          np.where(mkt_factor["mkt_vol_pctile_252"].fillna(0.5) <= 0.67, "med_vol", "high_vol"))
    mkt_factor["regime_bucket"] = [
        f"{d}|{v}" for d, v in zip(dir_bucket, vol_bucket)]
    panel = panel.join(mkt_factor, on="date")

    # --- cross-sectional features (at date t, universe data <= t) ---
    gap = panel["close"] / panel["close"].groupby("symbol").transform(
        lambda x: x.rolling(20).mean()) - 1.0
    xs = panel.groupby("date")[["mom_roc20"]].transform("rank", pct=True)
    xs = xs.rename(columns={"mom_roc20": "xs_mom_rank20"})
    gmean = gap.groupby("date").transform("mean")
    gstd = gap.groupby("date").transform("std")
    xs["xs_rel_str20"] = (gap - gmean) / gstd.replace(0, np.nan)
    panel = pd.concat([panel, xs], axis=1)

    # minimum cross-sectional coverage guard
    n_dates = panel.groupby("date").size()
    good_dates = n_dates[n_dates >= 20].index
    panel.loc[~panel.index.get_level_values("date").isin(good_dates),
              ["xs_mom_rank20", "xs_rel_str20"]] = np.nan

    # --- split assignment (order-sensitive) ---
    dt = panel.index.get_level_values("date")
    split_series = pd.Series("", index=panel.index, dtype=object)
    for split, b in splits.items():
        split_series.loc[(dt >= b["start"]) & (dt < b["end"])] = split
    panel["split"] = split_series

    if verbose:
        print(f"panel: {len(panel)} rows, {len(syms_all)} symbols, "
              f"dates {panel.index.get_level_values('date').min()} .. "
              f"{panel.index.get_level_values('date').max()}")
        print(panel["split"].value_counts().to_dict())
    return panel


if __name__ == "__main__":
    p = build_panel()
    print(p.columns.tolist())