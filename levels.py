from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    retests: int
    recency: int
    strength: float
    freshness: str
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean().bfill().ffill()


def _pivot_mask(series: pd.Series, left: int, right: int, mode: str) -> pd.Series:
    vals = series.to_numpy(dtype=float)
    mask = np.zeros(len(vals), dtype=bool)
    for i in range(left, len(vals) - right):
        window = vals[i - left : i + right + 1]
        if not np.isfinite(window).all():
            continue
        if mode == "high":
            mask[i] = vals[i] == np.max(window) and np.sum(window == vals[i]) == 1
        else:
            mask[i] = vals[i] == np.min(window) and np.sum(window == vals[i]) == 1
    return pd.Series(mask, index=series.index)


def _count_retests(work: pd.DataFrame, start_idx: int, low: float, high: float, skip: int = 2) -> int:
    future = work.iloc[min(start_idx + skip + 1, len(work)) :]
    if future.empty:
        return 0
    overlap = (future["high"] >= low) & (future["low"] <= high)
    # Count distinct visits rather than every candle sitting in the zone.
    groups = overlap & ~overlap.shift(1, fill_value=False)
    return int(groups.sum())


def _has_liquidity_sweep(work: pd.DataFrame, start_idx: int, low: float, high: float, kind: str) -> bool:
    future = work.iloc[start_idx + 1 :]
    if future.empty:
        return False
    if kind == "resistance":
        sweep = (future["high"] > high) & (future["close"] < high)
    else:
        sweep = (future["low"] < low) & (future["close"] > low)
    return bool(sweep.any())


def _has_break_retest(work: pd.DataFrame, start_idx: int, low: float, high: float, kind: str) -> bool:
    future = work.iloc[start_idx + 1 :].reset_index(drop=True)
    if len(future) < 4:
        return False
    if kind == "resistance":
        breaks = future.index[future["close"] > high].tolist()
        for i in breaks:
            later = future.iloc[i + 1 : i + 8]
            if not later.empty and ((later["low"] <= high) & (later["close"] >= low)).any():
                return True
    else:
        breaks = future.index[future["close"] < low].tolist()
        for i in breaks:
            later = future.iloc[i + 1 : i + 8]
            if not later.empty and ((later["high"] >= low) & (later["close"] <= high)).any():
                return True
    return False


def _has_impulsive_departure(work: pd.DataFrame, pivot_idx: int, price: float, atr: float, kind: str) -> bool:
    ahead = work.iloc[pivot_idx + 1 : pivot_idx + 5]
    if ahead.empty or not np.isfinite(atr) or atr <= 0:
        return False
    if kind == "support":
        return bool((ahead["close"] >= price + atr * 1.15).any())
    return bool((ahead["close"] <= price - atr * 1.15).any())


def _freshness(retests: int) -> str:
    if retests == 0:
        return "fresh"
    if retests <= 2:
        return "tested"
    return "mature"


def detect_levels(df: pd.DataFrame, timeframe: str) -> list[Level]:
    cfg = {
        "1d": {"left": 3, "right": 3, "atr_mult": 0.45, "base": 5.0},
        "4h": {"left": 4, "right": 4, "atr_mult": 0.38, "base": 3.0},
        "1h": {"left": 5, "right": 5, "atr_mult": 0.32, "base": 1.0},
    }[timeframe]

    work = df.reset_index(drop=True).copy()
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

    candidates.sort(key=lambda x: x[1])
    clusters: list[list[tuple[int, float, str, float]]] = []
    for c in candidates:
        if not clusters:
            clusters.append([c])
            continue
        prices = [x[1] for x in clusters[-1]]
        atrs = [x[3] for x in clusters[-1]]
        center = float(np.median(prices))
        tol = max(float(np.median(atrs)) * cfg["atr_mult"], center * 0.0015)
        if abs(c[1] - center) <= tol:
            clusters[-1].append(c)
        else:
            clusters.append([c])

    out: list[Level] = []
    n = len(work)
    for cluster in clusters:
        prices = np.array([x[1] for x in cluster], dtype=float)
        atrs = np.array([x[3] for x in cluster], dtype=float)
        idxs = [int(x[0]) for x in cluster]
        kinds = [x[2] for x in cluster]
        price = float(np.median(prices))
        zone_half = max(float(np.median(atrs)) * 0.22, price * 0.0007)
        low, high = price - zone_half, price + zone_half
        touches = len(cluster)
        last_idx = max(idxs)
        first_idx = min(idxs)
        recency = n - 1 - last_idx
        kind = "resistance" if kinds.count("resistance") >= kinds.count("support") else "support"

        retests = _count_retests(work, last_idx, low, high)
        freshness = _freshness(retests)
        signals: list[str] = []

        if touches >= 2:
            signals.append("equal highs" if kind == "resistance" else "equal lows")
        if _has_impulsive_departure(work, first_idx, price, float(np.median(atrs)), kind):
            signals.append("supply" if kind == "resistance" else "demand")
        if _has_liquidity_sweep(work, first_idx, low, high, kind):
            signals.append("liquidity sweep")
        if _has_break_retest(work, first_idx, low, high, kind):
            signals.append("break & retest")

        recency_bonus = max(0.0, 2.0 - recency / max(n * 0.25, 1))
        touch_bonus = min(4.0, 1.25 * math.log2(touches + 1))
        fresh_bonus = {"fresh": 2.0, "tested": 0.7, "mature": -0.8}[freshness]
        signal_bonus = 0.0
        for signal in signals:
            signal_bonus += {
                "equal highs": 1.0,
                "equal lows": 1.0,
                "supply": 1.4,
                "demand": 1.4,
                "liquidity sweep": 1.8,
                "break & retest": 1.7,
            }[signal]
        strength = cfg["base"] + touch_bonus + recency_bonus + fresh_bonus + signal_bonus
        out.append(
            Level(
                price=price,
                low=low,
                high=high,
                timeframe=timeframe,
                kind=kind,
                touches=touches,
                retests=retests,
                recency=recency,
                strength=max(strength, 0.1),
                freshness=freshness,
                signals=signals,
            )
        )

    out.sort(key=lambda x: x.strength, reverse=True)
    return out[:14]


def merge_timeframes(levels_by_tf: dict[str, list[Level]], current_price: float) -> pd.DataFrame:
    all_levels = [lvl for levels in levels_by_tf.values() for lvl in levels]
    all_levels.sort(key=lambda x: x.price)
    columns = [
        "zone", "low", "high", "mid", "type", "timeframes", "touches", "retests",
        "freshness", "signals", "score", "distance_pct",
    ]
    if not all_levels:
        return pd.DataFrame(columns=columns)

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

    rows: list[dict] = []
    tf_order = {"1d": 0, "4h": 1, "1h": 2}
    freshness_rank = {"fresh": 0, "tested": 1, "mature": 2}
    for grp in merged:
        weights = np.array([max(x.strength, 0.1) for x in grp])
        mids = np.array([x.price for x in grp])
        mid = float(np.average(mids, weights=weights))
        low = min(x.low for x in grp)
        high = max(x.high for x in grp)
        tfs = sorted(set(x.timeframe for x in grp), key=lambda x: tf_order[x])
        tf_bonus = {1: 0.0, 2: 3.0, 3: 5.0}[len(tfs)]
        score = sum(x.strength for x in grp) + tf_bonus
        touches = sum(x.touches for x in grp)
        retests = max(x.retests for x in grp)
        freshest = min((x.freshness for x in grp), key=lambda x: freshness_rank[x])
        signals = sorted(set(s for x in grp for s in x.signals))
        kind = "resistance" if mid >= current_price else "support"
        rows.append(
            {
                "zone": f"{low:,.4f} – {high:,.4f}",
                "low": low,
                "high": high,
                "mid": mid,
                "type": kind,
                "timeframes": " + ".join(t.upper() for t in tfs),
                "touches": touches,
                "retests": retests,
                "freshness": freshest,
                "signals": signals,
                "score": round(score, 2),
                "distance_pct": round((mid / current_price - 1) * 100, 2),
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["rank_metric"] = result["score"] - result["distance_pct"].abs() * 0.08
    return (
        result.sort_values("rank_metric", ascending=False)
        .head(12)
        .drop(columns=["rank_metric"])
        .reset_index(drop=True)
    )
