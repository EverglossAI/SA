from __future__ import annotations

import os
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.data import CRYPTO_EXCHANGES, load_market_data
from backend.levels import detect_levels, merge_timeframes


def _origins() -> list[str]:
    defaults = [
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "https://everglossai.github.io",
    ]
    extra = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]
    return sorted(set(defaults + extra))


app = FastAPI(title="SA Key Levels API", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AnalyseRequest(BaseModel):
    provider: Literal["crypto", "yahoo"] = "crypto"
    symbol: str = Field(min_length=1, max_length=40)
    exchange: str | None = None


def frame_to_records(df: pd.DataFrame, max_rows: int = 260) -> list[dict]:
    records: list[dict] = []
    for row in df.tail(max_rows).itertuples(index=False):
        records.append(
            {
                "time": pd.Timestamp(row.timestamp).isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume) if pd.notna(row.volume) else 0.0,
            }
        )
    return records


@app.get("/")
def root() -> dict:
    return {"service": "sa-key-levels", "ok": True, "docs": "/docs"}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "sa-key-levels", "version": "3.0.0"}


@app.get("/api/config")
def config() -> dict:
    return {"crypto_exchanges": CRYPTO_EXCHANGES}


@app.post("/api/analyse")
def analyse(req: AnalyseRequest) -> dict:
    symbol = req.symbol.strip().upper()
    try:
        data = load_market_data(req.provider, symbol, req.exchange)
        levels_by_tf = {tf: detect_levels(df, tf) for tf, df in data.items()}
        current_price = float(data["1h"]["close"].iloc[-1])
        merged = merge_timeframes(levels_by_tf, current_price)

        levels: list[dict] = []
        for row in merged.to_dict(orient="records"):
            levels.append(
                {
                    "zone": row["zone"],
                    "low": float(row["low"]),
                    "high": float(row["high"]),
                    "mid": float(row["mid"]),
                    "type": row["type"],
                    "timeframes": row["timeframes"],
                    "touches": int(row["touches"]),
                    "retests": int(row["retests"]),
                    "freshness": row["freshness"],
                    "signals": list(row["signals"]),
                    "score": float(row["score"]),
                    "distance_pct": float(row["distance_pct"]),
                }
            )

        return {
            "symbol": symbol,
            "provider": req.provider,
            "exchange": req.exchange if req.provider == "crypto" else None,
            "current_price": current_price,
            "levels": levels,
            "charts": {tf: frame_to_records(df) for tf, df in data.items()},
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
