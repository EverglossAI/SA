from __future__ import annotations

from dataclasses import dataclass, asdict
import math
import numpy as np
import pandas as pd


@dataclass
class Level:
    price: float
    low: float
    high: float
    timeframe: str
    kind: str
    touches: int
    recency: int
    strength: float

    def to_dict(self):
        return asdict(self)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean().bfill()


def _pivot_mask(series: pd.Series, left: int, right: int, mode: str) -> pd.Series:
    vals = series.to_numpy()
    mask = np.zeros(len(vals), dtype=bool)
    for i in range(left, len(vals) - right):
        window = vals[i-left:i+right+1]
        if mode == "high":
            mask[i] = vals[i] == np.nanmax(window) and np.sum(window == vals[i]) == 1
        else:
            mask[i] = vals[i] == np.nanmin(window) and np.sum(window == vals[i]) == 1
    return pd.Series(mask, index=series.index)


def detect_levels(df: pd.DataFrame, timeframe: str) -> list[Level]:
    cfg = {
        "1d": {"left": 3, "right": 3, "atr_mult": 0.45, "base": 5.0},
        "4h": {"left": 4, "right": 4, "atr_mult": 0.38, "base": 3.0},
        "1h": {"left": 5, "right": 5, "atr_mult": 0.32, "base": 1.0},
    }[timeframe]

    work = df.copy()
    work["atr"] = _atr(work)
    high_pivots = _pivot_mask(work["high"], cfg["left"], cfg["right"], "high")
    low_pivots = _pivot_mask(work["low"], cfg["left"], cfg["right"], "low")

    candidates: list[tuple[int, float, str, float]] = []
    for idx in work.index[high_pivots]:
        candidates.append((idx, float(work.at[idx, "high"]), "resistance", float(work.at[idx, "atr"])))
    for idx in work.index[low_pivots]:
        candidates.append((idx, float(work.at[idx, "low"]), "support", float(work.at[idx, "atr"])))

    if not candidates:
        return []

    # Cluster nearby pivot prices within an ATR-derived tolerance.
    candidates.sort(key=lambda x: x[1])
    clusters: list[list[tuple[int, float, str, float]]] = []
    for c in candidates:
        if not clusters:
            clusters.append([c])
            continue
        cluster_prices = [x[1] for x in clusters[-1]]
        cluster_atrs = [x[3] for x in clusters[-1]]
        center = float(np.median(cluster_prices))
        tol = max(float(np.median(cluster_atrs)) * cfg["atr_mult"], center * 0.0015)
        if abs(c[1] - center) <= tol:
            clusters[-1].append(c)
        else:
            clusters.append([c])

    out: list[Level] = []
    n = len(work)
    for cluster in clusters:
        prices = np.array([x[1] for x in cluster], dtype=float)
        atrs = np.array([x[3] for x in cluster], dtype=float)
        idxs = [x[0] for x in cluster]
        kinds = [x[2] for x in cluster]
        price = float(np.median(prices))
        zone_half = max(float(np.median(atrs)) * 0.22, price * 0.0007)
        touches = len(cluster)
        last_idx = max(idxs)
        recency = n - 1 - last_idx
        kind = "resistance" if kinds.count("resistance") >= kinds.count("support") else "support"

        recency_bonus = max(0.0, 2.0 - recency / max(n * 0.25, 1))
        touch_bonus = min(4.0, 1.25 * math.log2(touches + 1))
        strength = cfg["base"] + touch_bonus + recency_bonus
        out.append(Level(price, price-zone_half, price+zone_half, timeframe, kind, touches, recency, strength))

    # Keep the most structurally important zones, not every pivot.
    out.sort(key=lambda x: x.strength, reverse=True)
    return out[:12]


def merge_timeframes(levels_by_tf: dict[str, list[Level]], current_price: float) -> pd.DataFrame:
    all_levels = [lvl for levels in levels_by_tf.values() for lvl in levels]
    all_levels.sort(key=lambda x: x.price)
    if not all_levels:
        return pd.DataFrame(columns=["zone", "mid", "type", "timeframes", "touches", "score", "distance_pct"])

    merged: list[list[Level]] = []
    for lvl in all_levels:
        if not merged:
            merged.append([lvl])
            continue
        grp = merged[-1]
        center = np.average([x.price for x in grp], weights=[max(x.strength, 0.1) for x in grp])
        tol = max(center * 0.0025, max(x.high - x.low for x in grp + [lvl]))
        if abs(lvl.price - center) <= tol:
            grp.append(lvl)
        else:
            merged.append([lvl])

    rows = []
    for grp in merged:
        weights = np.array([max(x.strength, 0.1) for x in grp])
        mids = np.array([x.price for x in grp])
        mid = float(np.average(mids, weights=weights))
        low = min(x.low for x in grp)
        high = max(x.high for x in grp)
        tfs = sorted(set(x.timeframe for x in grp), key=lambda x: {"1d":0,"4h":1,"1h":2}[x])
        tf_bonus = {1: 0, 2: 3, 3: 5}[len(tfs)]
        score = sum(x.strength for x in grp) + tf_bonus
        touches = sum(x.touches for x in grp)
        kinds = [x.kind for x in grp]
        kind = "resistance" if mid >= current_price else "support"
        if kinds.count("support") == kinds.count("resistance"):
            kind = "resistance" if mid >= current_price else "support"
        rows.append({
            "zone": f"{low:,.4f} – {high:,.4f}",
            "low": low,
            "high": high,
            "mid": mid,
            "type": kind,
            "timeframes": " + ".join(t.upper() for t in tfs),
            "touches": touches,
            "score": round(score, 2),
            "distance_pct": round((mid/current_price - 1) * 100, 2),
        })

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    # Prefer high-confluence levels while retaining nearby actionable zones.
    result["rank_metric"] = result["score"] - result["distance_pct"].abs() * 0.08
    result = result.sort_values("rank_metric", ascending=False).head(10).drop(columns=["rank_metric"]).reset_index(drop=True)
    return result
