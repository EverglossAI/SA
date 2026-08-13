# SA Key Levels

Static GitHub Pages frontend + FastAPI backend for automatic Daily / 4H / 1H key-level analysis.

## What changed in v3

- GitHub Pages-compatible frontend lives in `docs/`.
- FastAPI backend lives in `backend/` and is deployable to Render via `render.yaml`.
- CORS is configured for `https://everglossai.github.io` and local testing.
- Level engine now scores fresh/untested zones and tags equal highs/lows, supply/demand departures, liquidity sweeps, and break-and-retests.
- Crypto data uses CCXT. Stocks, indices, FX, and many futures symbols use yfinance. 4H Yahoo candles are derived from 1H candles.

## Local backend test

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
pytest -q
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/api/health`.

## Local frontend test

In another terminal:

```bash
python -m http.server 5500 --directory docs
```

Open `http://127.0.0.1:5500`, enter `BTC/USDT`, and click **Analyse market**. On localhost the frontend automatically targets `http://127.0.0.1:8000`.

## Deploy backend to Render

1. Push this repository to GitHub.
2. In Render choose **New > Blueprint** and select this repository.
3. Render reads `render.yaml` and creates the `sa-key-levels-api` service.
4. Wait for `/api/health` to return JSON with `"ok": true`.
5. Copy the public Render URL, e.g. `https://sa-key-levels-api-xxxx.onrender.com`.
6. Put that URL in `docs/config.js`:

```js
window.KEY_LEVELS_API_BASE = "https://sa-key-levels-api-xxxx.onrender.com";
```

Commit and push the change.

## Deploy frontend to GitHub Pages

Repository **Settings > Pages**:

- Source: **Deploy from a branch**
- Branch: **main**
- Folder: **/docs**

After GitHub publishes it, open `https://everglossai.github.io/SA/`.

## Production smoke test

1. Open the Render backend `/api/health` URL and confirm `ok: true`.
2. Open the GitHub Pages site.
3. Analyse `BTC/USDT` on Binance.
4. Confirm Daily, 4H, and 1H tabs render candles.
5. Confirm the result table shows `Freshness` and `Signals`.
6. Try `SPY` in Stocks / FX / Futures mode.
7. Open browser DevTools > Network. `/api/analyse` should be a 200 request to the Render domain, not GitHub Pages.

## Notes

This is a research tool, not trading advice. Public market-data providers can rate-limit or temporarily fail. Render free services may cold-start after inactivity.
