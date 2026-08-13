from __future__ import annotations

import pandas as pd

CRYPTO_EXCHANGES = ["binance", "bybit", "okx", "kraken", "coinbase"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    if "datetime" in out.columns and "timestamp" not in out.columns:
        out = out.rename(columns={"datetime": "timestamp"})
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {', '.join(missing)}")
    out = out[required].dropna(subset=["timestamp", "open", "high", "low", "close"])
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna().drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def fetch_crypto(exchange_id: str, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    try:
        import ccxt
    except ImportError as exc:
        raise RuntimeError("CCXT is not installed. Run: pip install -r requirements.txt") from exc

    if exchange_id not in ccxt.exchanges:
        raise ValueError(f"Unknown CCXT exchange: {exchange_id}")
    exchange_cls = getattr(ccxt, exchange_id)
    exchange = exchange_cls({"enableRateLimit": True})
    exchange.load_markets()
    if symbol not in exchange.markets:
        raise ValueError(f"{symbol} was not found on {exchange_id}")
    if not exchange.has.get("fetchOHLCV"):
        raise ValueError(f"{exchange_id} does not expose OHLCV through CCXT")
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    if not raw:
        raise ValueError("No OHLCV data returned")
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return _normalize(df)


def _flatten_yahoo_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.columns, pd.MultiIndex):
        return df
    # Single-symbol yfinance downloads can still return a MultiIndex.
    level0 = [str(c[0]) for c in df.columns]
    df = df.copy()
    df.columns = level0
    return df


def fetch_yahoo(symbol: str, interval: str, period: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance is not installed. Run: pip install -r requirements.txt") from exc

    df = yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        prepost=False,
        multi_level_index=False,
    )
    if df is None or df.empty:
        raise ValueError(f"No market data returned for Yahoo symbol {symbol}")
    df = _flatten_yahoo_columns(df).reset_index()
    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "timestamp"})
    elif "Date" in df.columns:
        df = df.rename(columns={"Date": "timestamp"})
    return _normalize(df)


def resample_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    work = df_1h.set_index("timestamp")
    out = work.resample("4h", origin="start_day").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open", "high", "low", "close"])
    return _normalize(out.reset_index())


def load_market_data(provider: str, symbol: str, exchange: str | None = None) -> dict[str, pd.DataFrame]:
    provider = provider.lower()
    if provider == "crypto":
        if not exchange:
            exchange = "binance"
        return {
            "1d": fetch_crypto(exchange, symbol, "1d", 400),
            "4h": fetch_crypto(exchange, symbol, "4h", 500),
            "1h": fetch_crypto(exchange, symbol, "1h", 700),
        }
    if provider == "yahoo":
        # yfinance supports 1h, not 4h; derive 4h bars from 1h data.
        one_hour = fetch_yahoo(symbol, "1h", "60d")
        daily = fetch_yahoo(symbol, "1d", "2y")
        return {"1d": daily, "4h": resample_4h(one_hour), "1h": one_hour}
    raise ValueError("Provider must be 'crypto' or 'yahoo'")
