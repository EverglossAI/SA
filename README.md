# Key Levels — Multi-Timeframe Web App

A local-first browser app that automatically downloads market candles and identifies ranked support/resistance zones across **Daily, 4H and 1H**.

## Markets

- **Crypto:** CCXT exchanges including Binance, Bybit, OKX, Kraken and Coinbase.
- **Stocks / indices / FX / futures:** Yahoo-compatible symbols through `yfinance` (examples: `SPY`, `AAPL`, `^GSPC`, `EURUSD=X`, `ES=F`).

For Yahoo symbols, 4H candles are built by resampling the downloaded 1H candles.

## Features

- Automatic OHLCV download
- Daily / 4H / 1H pivot detection
- ATR-adjusted support/resistance zones
- Touch and recency scoring
- Cross-timeframe clustering and confluence bonus
- Ranked levels table
- Nearest support / resistance
- Interactive annotated candlestick charts
- FastAPI backend + responsive HTML/CSS/JS frontend

## Run

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
python run_web.py
```

Open **http://127.0.0.1:8000**.

## API

- `GET /api/health`
- `GET /api/config`
- `POST /api/analyse`

Example request:

```json
{
  "provider": "crypto",
  "exchange": "binance",
  "symbol": "BTC/USDT"
}
```

Or:

```json
{
  "provider": "yahoo",
  "symbol": "SPY"
}
```

## Notes

The browser chart currently loads Plotly.js from a CDN. The market analysis itself runs locally. Market-data requests go to the selected upstream provider.

This project is for research and educational use; detected levels are algorithmic estimates, not trading advice.

## Docker

```bash
docker build -t key-levels .
docker run --rm -p 8000:8000 key-levels
```

Then open **http://127.0.0.1:8000**.

## Project structure

```text
key-levels/
├── app/
│   └── levels.py           # level detection + timeframe merging
├── webapp/
│   ├── main.py             # FastAPI API + static frontend server
│   ├── services/data.py    # CCXT / Yahoo market-data adapters
│   └── static/
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── tests/test_levels.py
├── run_web.py
├── Dockerfile
└── requirements.txt
```
