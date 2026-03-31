# Investment Agent

Personal investment analysis and portfolio management toolkit.

## What This Is
A Claude-powered investment analysis system built around a
thesis-driven, concentrated portfolio management philosophy.
Includes historical backtesting scripts and a web application
(in development) for ongoing portfolio monitoring.

## Scripts

| Script | Purpose |
|--------|---------|
| backtest.py | Tax-aware mechanistic backtest — three cap scenarios (15/20/25%) vs buy-and-hold and SPY |
| backtest_extra.py | Extended scenarios — no-ENPH portfolio and ENPH 40/50% conviction caps |
| backtest_scenarios56.py | Substitution scenarios (NVDA/MSFT/SPY replacing ENPH) and variable cap test |
| backtest_scenarios7.py | NVDA conviction depth, ENPH+NVDA split, and full cap stress test sweep |

## How to Run
```bash
pip install -r requirements.txt
python3 backtest.py
```

First run fetches price data from Yahoo Finance (~2 minutes)
and saves to price_cache.json. Subsequent runs use the cache.

## Requirements
- Python 3.8+
- yfinance
- pandas
- numpy

## Environment Variables
Copy .env.example to .env and fill in values before running
the web application. Never commit .env to GitHub.

## Web Application
Built with React + Node.js + PostgreSQL + Clerk + Anthropic API.
Hosted on Railway. See /client and /server directories.
