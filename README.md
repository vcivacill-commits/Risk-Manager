# KuCoin Futures Risk Management Bot

Telegram bot for automatic leverage, stop-loss, and take-profit calculation using ATR-based support/resistance from KuCoin Futures API.

Supports **crypto** (e.g. `BTC`, `ETH`, `SOL`), **metals** (e.g. `XAU`/gold, `SILVER`), and **stock perpetuals** (e.g. `TSLA`, `NVDA`) — all priced from KuCoin Futures, which is the sole market-data source used throughout the bot. Symbols are resolved dynamically against KuCoin's live contract list, so any crypto, metal, or stock perpetual KuCoin lists works automatically without code changes.

## Formula
