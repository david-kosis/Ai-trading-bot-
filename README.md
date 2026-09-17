# AI Trading Bot — Binance Spot

Paper-first, rules-driven crypto gap/breakout trading-bot project for Binance Spot.

Pipeline:
scan -> rules -> risk -> execute -> manage -> notify -> log -> dashboard

## Binance integration

The broker adapter now uses the Binance Spot REST API. Binance provides REST market-data and trading endpoints, signed API requests, and a Spot Testnet for development/testing. See the official Binance API documentation: https://developers.binance.com/en/docs/introduction

Paper mode uses the Binance Spot Testnet endpoint. Live production execution is blocked unless BOTH `BROKER_MODE=live` and `LIVE_TRADING_ENABLED=true` are explicitly enabled.

## Install on Windows

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `.env`:

```text
BROKER_MODE=paper
LIVE_TRADING_ENABLED=false
BINANCE_API_KEY=your_testnet_key
BINANCE_API_SECRET=your_testnet_secret
BINANCE_TESTNET=true
```

Never commit `.env` or API secrets.

## Run

Scanner:

```powershell
python -m bot.main --mode scan
```

Trading-cycle process:

```powershell
python -m bot.main --mode trade
```

Dashboard:

```powershell
streamlit run dashboard/app.py
```

## Crypto strategy conversion

The old S&P 500/premarket assumptions were removed. The scanner now builds a liquid USDT Spot universe from Binance exchange information and 24-hour volume, then checks daily candles for configurable open-vs-previous-close gaps.

Because crypto trades 24/7, there is no U.S.-stock premarket or fixed 09:35–11:30 ET session. Intraday rules therefore need to be interpreted using crypto daily and 5-minute candles. The current project provides the Binance connection, market-data scanner, risk sizing, order adapter, account/position access, logging, and notification plumbing.

The current `trade` cycle intentionally remains execution-gated: it records candidates but does not automatically enter every scanner candidate. A complete production strategy still needs the real-time rule evaluator and robust stop/partial-profit/trailing-order manager to be completed and paper-tested.

## Safety

- Default is Binance Spot Testnet/paper mode.
- Do not enable live trading while developing.
- Use API keys with only the permissions the bot needs; never share the secret.
- Binance enforces request/rate limits; production code must handle throttling, timeouts, reconnects, and unknown order status safely.
- This software is technical infrastructure, not a profitability guarantee or financial advice.

The strategy is configured in `config/rules.json`.
