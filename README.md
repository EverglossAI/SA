# SA Key Levels — GitHub Pages only

A browser-only multi-timeframe key-level analysis app. No Python backend and no separate server are required.

## Data sources

- Crypto: Binance public market-data API (1D, 4H, 1H)
- Stocks / FX / futures: Twelve Data API using a user-supplied API key stored in browser localStorage

The Twelve Data key is never committed to the repository. Because GitHub Pages is static hosting, there is no safe server-side secret store in this architecture.

## Deploy

1. Put `index.html`, `app.js`, `styles.css`, and `.nojekyll` in your repository root (or `docs/`).
2. In GitHub: Settings → Pages.
3. Choose `Deploy from a branch`.
4. Select `main` and `/ (root)` if these files are in the repository root, or `/docs` if you place them in `docs/`.
5. Save and wait for the Pages build to finish.

## Test

### Crypto

Open the Pages site, leave `Crypto` selected, enter `BTC/USDT`, and click **Analyse market**. No API key is required.

### Stocks / FX / futures

Select `Stocks / FX / Futures`, paste your Twelve Data API key, enter a symbol such as `SPY`, `AAPL`, or `EUR/USD`, and click **Analyse market**.

## What the detector scores

- Daily, 4H, and 1H pivots
- ATR-based zones
- repeated touches
- fresh / tested / mature zones
- equal highs / equal lows
- supply / demand departures
- liquidity sweeps
- break & retest patterns
- multi-timeframe confluence
- higher-timeframe weighting

## Security note

A GitHub Pages site cannot keep an API key secret because all HTML/JavaScript is delivered to the visitor. This app therefore stores the optional Twelve Data key only in the user's own browser. Do not hard-code a private API key into `app.js`.
