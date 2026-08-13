import numpy as np
import pandas as pd

from app.levels import detect_levels, merge_timeframes


def synthetic(n=520, seed=7):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    base = 100 + np.sin(np.arange(n)/13)*5 + np.sin(np.arange(n)/43)*8
    noise = rng.normal(0, .5, n)
    close = base + noise
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(.2, 1.2, n)
    low = np.minimum(open_, close) - rng.uniform(.2, 1.2, n)
    return pd.DataFrame({"timestamp":t,"open":open_,"high":high,"low":low,"close":close,"volume":rng.integers(100,1000,n)})


def test_multitimeframe_detector_returns_ranked_levels():
    one_h = synthetic()
    four_h = one_h.set_index("timestamp").resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna().reset_index()
    daily = one_h.set_index("timestamp").resample("1d").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna().reset_index()
    by_tf = {"1d": detect_levels(daily,"1d"), "4h": detect_levels(four_h,"4h"), "1h": detect_levels(one_h,"1h")}
    merged = merge_timeframes(by_tf, float(one_h.close.iloc[-1]))
    assert not merged.empty
    assert {"zone","score","timeframes","distance_pct"}.issubset(merged.columns)
    assert len(merged) <= 10
