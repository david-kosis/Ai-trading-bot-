@echo off
cd /d C:\quant_gap_bot
call .venv\Scripts\activate.bat
python -m bot.main --mode trade
