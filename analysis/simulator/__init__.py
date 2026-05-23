"""Backtest simulator — Phase 1.

See docs/architecture/BACKTEST_SIMULATOR.md for the design spec. The
simulator runs hypothetical capital through historical earnings calls,
applies the allocator's decision rules quarter-by-quarter, and produces a
portfolio time series compared against passive ETF baselines (SPY, QQQ,
TMFC).
"""
