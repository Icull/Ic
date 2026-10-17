# MARC Multi-Market Scanner

Telegram scanner prototype for Indonesian and global equities, crypto watchlist momentum, and intraday commodity levels.

## Scheduled reports (Asia/Jakarta)

- **09:00 WIB Monday-Friday:** Top 10 Indonesian + global stock candidates for the next available session, ranked by recent momentum, relative volume, trend, and volatility.
- **21:00 WIB daily:** Top 10 crypto candidates from the configured watchlist and commodity intraday levels with indicative support/resistance and a 1–5 hour directional watch.
- Manual runs: Actions → MARC Multi-Market Scanner → Run workflow; choose `all`, `stocks`, `evening`, `crypto`, or `commodities`.

## Setup

1. Add repository secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` under Settings → Secrets and variables → Actions.
2. Run the workflow manually with `all` and confirm a Telegram message arrives.
3. Scheduled reports use GitHub Actions' timezone-aware schedules. Runs may still be delayed by GitHub.
4. Update `universe.csv`, `global_stocks.csv`, `crypto_universe.csv`, and `commodity_universe.csv` to maintain watchlists.

## Methodology and limitations

- **Stocks:** starter watchlist only (45 Indonesian tickers plus global large-cap names), not a full exchange-wide scan. Price history is sourced via Yahoo Finance/yfinance; global tickers are not converted to a common currency.
- **Crypto:** ranks a configured list, not every coin or exchange. Yahoo data may not reflect the tradable pair, spread, depth, or real-time exchange activity. Hype score is a heuristic, not a probability.
- **Commodities:** uses Yahoo Finance futures symbols and recent 15-minute bars. Support/resistance are recent swing ranges, and LONG/SHORT WATCH/WAIT is a technical bias only, not a trading instruction. Futures contracts, rollover, trading hours, spreads, and provider delays matter.
- **Exchange calendars:** the stock workflow runs weekdays; it does not yet skip all holidays for every global exchange. Review each exchange's holiday calendar and the data date in the report.
- **Data freshness:** Yahoo Finance may be delayed, incomplete, or rate-limited. Verify quotes and levels on your broker/exchange before acting.
- **Risk:** scores are not calibrated forecasts and no trade setup is guaranteed. This tool does not include a full news feed, backtesting, transaction costs, or personalized investment advice. Use position sizing and predefined risk controls.

## Indicators

Stocks: EMA20/EMA50, 1/5/20-day return, RSI, previous-volume relative to 20-day average, recent range.
Crypto: 24-hour and 7-day momentum, RSI, and relative volume.
Commodities: 15-minute EMA9/EMA21, RSI, recent 20-bar support/resistance and distance to those levels.
