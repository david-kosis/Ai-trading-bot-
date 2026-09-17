# Quant Gap Breakout Bot

Paper-first, rules-driven S&P 500 gap/breakout trading-bot project.

Pipeline:
scan -> rules -> risk -> execute -> manage -> notify -> log -> dashboard

The default broker adapter is Interactive Brokers (IBKR).

IMPORTANT:
- Default mode is paper.
- Live trading requires BOTH BROKER_MODE=live and LIVE_TRADING_ENABLED=true.
- Test extensively in the IBKR paper account before considering live use.
- This project does not guarantee profitability.

## Install

py -3.12 -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
copy .env.example .env

Run:
python -m bot.main --mode scan
python -m bot.main --mode trade

Dashboard:
streamlit run dashboard/app.py

The strategy is configured in config/rules.json.

The phrase "price above today's high" is implemented as price breaking above
the previously completed intraday high. A literal current-high comparison
would be impossible because the current price cannot exceed the current bar's
high.

The included data/sp500.csv is an initial sample universe. Replace it with a
maintained full S&P 500 constituent list before using the scanner for the full
index universe.

See the included scripts/ directory for Windows scheduling.
