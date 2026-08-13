from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.levels import detect_levels, merge_timeframes
from webapp.services.data import CRYPTO_EXCHANGES, load_market_data

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Key Levels", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyseRequest(BaseModel):
    provider: Literal["crypto", "yahoo"] = "crypto"
    symbol: str = Field(min_length=1, max_length=40)
    exchange: str | None = None


def frame_to_records(df: pd.DataFrame, max_rows: int = 260) -> list[dict]:
    view = df.tail(max_rows).copy()
    records = []
    for row in view.itertuples(index=False):
        records.append({
            "time": pd.Timestamp(row.timestamp).isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume) if pd.notna(row.volume) else 0.0,
        })
    return records


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "key-levels"}


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
        merged_records = []
        for row in merged.to_dict(orient="records"):
            merged_records.append({
                "zone": row["zone"],
                "low": float(row["low"]),
                "high": float(row["high"]),
                "mid": float(row["mid"]),
                "type": row["type"],
                "timeframes": row["timeframes"],
                "touches": int(row["touches"]),
                "score": float(row["score"]),
                "distance_pct": float(row["distance_pct"]),
            })
        return {
            "symbol": symbol,
            "provider": req.provider,
            "exchange": req.exchange if req.provider == "crypto" else None,
            "current_price": current_price,
            "levels": merged_records,
            "charts": {tf: frame_to_records(df) for tf, df in data.items()},
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
