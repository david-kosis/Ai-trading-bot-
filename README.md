# AI Trading Bot

Paper-first autonomous S&P 500 gap/breakout trading system.

**Pipeline:** scan -> evaluate rules -> size risk -> execute -> manage -> exit -> notify -> report

## Features
- S&P 500 universe scanning for significant gaps (default >= 3%)
- Structured `rules.json` strategy configuration
- Daily + intraday rule evaluation
- IBKR paper/live API adapter with separate scanner/execution client IDs
- Risk-based position sizing and configurable limits
- Stop, partial-profit, breakeven, trailing-stop and forced-exit framework
- Telegram alerts
- SQLite audit/trade logging
- Streamlit quant-terminal dashboard
- Windows automation scripts

## Safety
The default configuration is **paper trading**. Live trading requires both `BROKER_MODE=live` and `LIVE_TRADING_ENABLED=true`. Never commit API credentials or `.env` files.

This software is not financial advice and does not guarantee profitability.
