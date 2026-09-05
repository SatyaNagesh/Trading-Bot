"""Chronological TRAIN / VALIDATION / FINAL-OOS data splitting.

Enforces strict chronological causality: TRAIN < VALIDATION < FINAL-OOS with
no overlap, so strategy development can only ever see TRAIN (+ VALIDATION for
selection sanity) and FINAL-OOS stays a completely untouched test period.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


SPLIT_NAMES = ["train", "validation", "final_oos"]


def make_splits(start: str, train_end: str, val_end: str, oos_end: str) -> dict[str, Any]:
    boundaries = {
        "train": (start, train_end),
        "validation": (train_end, val_end),
        "final_oos": (val_end, oos_end),
    }
    splits = {name: {"start": s, "end": e} for name, (s, e) in boundaries.items()}
    _guard_nominal(splits)
    return splits


def _guard_nominal(splits: dict[str, dict]) -> None:
    order = ["train", "validation", "final_oos"]
    bounds = [splits[k]["start"] for k in order] + [splits[order[-1]]["end"]]
    for a, b in zip(bounds, bounds[1:]):
        if a >= b:
            raise ValueError(f"non-increasing split boundaries: {bounds}")


def split_frame(
    df: pd.DataFrame, splits: dict[str, dict[str, str]]
) -> dict[str, pd.DataFrame]:
    frames = {}
    for name, bounds in splits.items():
        mask = (df.index >= bounds["start"]) & (df.index < bounds["end"])
        frames[name] = df[mask].copy()
    return frames


def guard_no_overlap(frames: dict[str, pd.DataFrame]) -> dict[str, dict]:
    conflicts = {}
    for name, frame in frames.items():
        others = [n for n in SPLIT_NAMES if n != name]
        for other in others:
            overlap = frame.index.intersection(frames[other].index)
            if len(overlap):
                conflicts.setdefault(name, {})[other] = int(len(overlap))
    return conflicts


def save_splits(splits: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(splits, indent=2, default=str))


def load_splits(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())