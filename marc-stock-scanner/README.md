# MARC Daily Stock Scanner

Prototype scanner that ranks a configured list of BEI stocks using daily momentum and volume indicators, then sends a Telegram report through GitHub Actions.

## Important scope notes

- The starter universe.csv is a curated starter list, not the full BEI universe. Expand and maintain it before describing results as market-wide Top 10.
- Yahoo Finance symbols for Indonesian listings typically use the .JK suffix. Yahoo data may be delayed, missing, or subject to provider terms/limits.
- The score is a simple technical ranking, not a calibrated probability that a stock will rise. It does not include a complete news feed, corporate actions, broker flow, fundamentals, or transaction costs.
- For research and education, not personalized investment advice.

## Setup

1. Create a Telegram bot using Telegram's official BotFather. Never commit the bot token.
2. Open the bot chat and send it a message (or add it to the destination group/channel).
3. In GitHub, open Settings → Secrets and variables → Actions → New repository secret and add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
4. Go to Actions → MARC Daily Stock Scanner → Run workflow to test manually.
5. Scheduled runs are set for weekdays at 09:00 Asia/Jakarta. GitHub may delay scheduled starts, and this schedule does not itself know BEI holidays.
6. Confirm that the data date is the latest completed trading session before relying on the report.

## Scoring logic

The first version uses close vs EMA20/EMA50, 5-day and 20-day momentum, RSI, daily return, and volume vs its 20-day average. It ranks candidates by score, then 5-day return and relative volume.

## Roadmap

- Validate data coverage and expand the ticker master to the full current BEI-listed universe.
- Add an exchange holiday calendar and a clear closed-market/no-fresh-data message.
- Backtest rankings using point-in-time data, avoiding look-ahead bias; report hit rate, benchmark-relative returns, drawdown, and turnover.
- Add company news and corporate-action catalysts with source links.
- Add retries, Telegram delivery status, and failure alerting.
