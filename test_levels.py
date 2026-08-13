import numpy as np
import pandas as pd

from backend.levels import Level, detect_levels, merge_timeframes


def sample_df(n=220, seed=7):
    rng = np.random.default_rng(seed)
    x = np.arange(n)
    base = 100 + 4*np.sin(x/11) + 0.012*x
    close = base + rng.normal(0, 0.25, n)
    open_ = close + rng.normal(0, 0.18, n)
    high = np.maximum(open_, close) + rng.uniform(0.2, 0.65, n)
    low = np.minimum(open_, close) - rng.uniform(0.2, 0.65, n)
    return pd.DataFrame({
        'timestamp': pd.date_range('2025-01-01', periods=n, freq='h', tz='UTC'),
        'open': open_, 'high': high, 'low': low, 'close': close, 'volume': 1000.0,
    })


def test_detect_levels_returns_enriched_levels():
    levels = detect_levels(sample_df(), '1h')
    assert levels
    assert all(l.freshness in {'fresh', 'tested', 'mature'} for l in levels)
    assert all(isinstance(l.signals, list) for l in levels)
    assert all(l.strength > 0 for l in levels)


def test_merge_preserves_signals_and_timeframe_confluence():
    levels = {
        '1d': [Level(100, 99.8, 100.2, '1d', 'resistance', 2, 0, 3, 9.0, 'fresh', ['equal highs'])],
        '4h': [Level(100.1, 99.9, 100.3, '4h', 'resistance', 1, 1, 2, 6.0, 'tested', ['liquidity sweep'])],
        '1h': [],
    }
    merged = merge_timeframes(levels, 95.0)
    assert len(merged) == 1
    row = merged.iloc[0]
    assert row['timeframes'] == '1D + 4H'
    assert 'equal highs' in row['signals']
    assert 'liquidity sweep' in row['signals']
    assert row['score'] > 15
