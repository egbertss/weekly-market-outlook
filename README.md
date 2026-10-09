# Weekly Market Outlook

Sample output: [docs/sample.pdf](docs/sample.pdf)

Generates a client-ready weekly market note as a single self-contained HTML file (optionally PDF) from public data: FRED (rates, credit spreads, inflation breakevens, VIX) and Yahoo Finance (equities, FX, gold, oil, bond ETFs).

The note contains four charts (equities rebased, yield curve, credit spreads, one-week performance), two data tables and short rule-based commentary.

## Quick start

```bash
pip install -r requirements.txt
python outlook.py --demo      # offline, synthetic data, tagged DEMO
python outlook.py             # live data, writes reports/weekly_outlook_<date>.html
python outlook.py --pdf       # also writes a PDF (pip install -r requirements-pdf.txt, then: playwright install chromium)
python outlook.py --pdf --send   # and emails / Telegrams it (settings from env vars, see below)
```

Requires Python 3.11+.

## Run in Google Colab (no install)

Paste `colab/weekly_outlook_colab.py` into one Colab cell, fill in the SETTINGS block at the top (names, watchlists, optional API keys) and run it. It installs what it needs, builds the note, shows it and downloads it. The file is generated from the repo code with `python build_colab.py`.

## Configuration

Edit `config.toml`: client name, adviser, firm, note date, the "our view" and "next week" bullet points, and the ticker maps for equities and other assets.

## Week ahead and filings

Four optional blocks, all set in the `[events]` section of `config.toml`:

- Macro calendar: next week's key releases. It uses the first key it finds: `TE_API_KEY` (Trading Economics, paid), `FMP_API_KEY` (Financial Modeling Prep) or `FRED_API_KEY` (free, US release dates only, no forecasts). Add ECB meetings and other dates by hand under `manual_events`.
- Earnings: next report dates for a watchlist, via Yahoo Finance.
- SEC EDGAR: 8-K, 10-Q and 10-K filings from the last 7 days for the watchlist, plus a count of Form 4 insider trades. Set `sec_user_agent` to your name and email, which EDGAR requires.
- US Congress trades: free from the official STOCK Act sources. Senate trades are read line by line from efdsearch.senate.gov. House reports come from disclosures-clerk.house.gov, with tickers read from the PDF where it has text. Disclosures lag trades by up to 45 days. A paid `QUIVER_API_KEY` replaces both if set.

- Big funds (13F): for Berkshire, Bridgewater, Pershing Square, Scion, Renaissance and others, the latest 13F-HR from SEC EDGAR with top holdings, biggest adds and cuts, new positions and exits versus the previous quarter. Free, uses the same `sec_user_agent`. US long positions only, at quarter end, filed up to 45 days later.

A block with no key or no data is simply left out. In GitHub, add the keys under Settings, Secrets and variables, Actions.

## Headlines

Free headlines from public RSS feeds (Federal Reserve, ECB, CNBC, MarketWatch, Yahoo Finance), last 7 days, with links to the publishers. Change the list with `news_feeds` in `config.toml`.

## Europe

- DAX and CAC 40 sit next to the Euro Stoxx 50 and FTSE MIB in the equity charts and tables.
- A "Euro area rates" table comes from the ECB Data Portal (free, no key): AAA 2Y and 10Y yields, the 2s10s slope, the deposit facility rate, and the Italy and Germany 10Y yields with the BTP-Bund spread. The two country yields are month-end figures and lag, which the table shows in its "As of" column.
- The earnings watchlist includes ASML, SAP, LVMH, Nestle, Intesa Sanpaolo, UniCredit and Eni. The macro calendar covers the euro area, Germany, France and Italy.

## Publishing publicly

Set `public = true` under `[note]` in `config.toml`. The note then drops the client name and firm. Keep the disclaimer in place, and do not publish the `--demo` output.

## Automation: every Sunday, by email or Telegram

`.github/workflows/weekly.yml` runs every Sunday at 07:00 UTC. It builds the PDF, sends it, and keeps a copy in `reports/`. To use it on your own fork:

1. Fork this repo.
2. Go to Settings, Secrets and variables, Actions, and add the secrets you need:

| Secret | What | Needed for |
|---|---|---|
| `FRED_API_KEY` | free, fredaccount.stlouisfed.org/apikey | US macro calendar |
| `SEC_CONTACT` | "Your Name you@email.com" | SEC filings, 13F |
| `FMP_API_KEY`, `TE_API_KEY`, `QUIVER_API_KEY` | optional | richer calendar, Congress trades via Quiver |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO` | your mailbox and an app password | email delivery |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | from @BotFather | Telegram delivery |

3. Open the Actions tab, pick "Weekly outlook" and press "Run workflow" to test.

Email settings: iCloud uses `smtp.mail.me.com` and port `587`, with an app-specific password from account.apple.com. Gmail uses `smtp.gmail.com` and port `465`, with an app password from myaccount.google.com/apppasswords. Never use your normal password.

Telegram: message @BotFather, send `/newbot`, and copy the token. Send any message to your new bot. Run once without `TELEGRAM_CHAT_ID` and the log prints your chat id.

To stop committing PDFs to the repo, add a repository variable `COMMIT_REPORTS` = `false`.

Keys only ever live in GitHub Secrets. Nothing secret is stored in the code.

## Tests

```bash
pip install pytest
pytest
```

## Data terms

Data comes from public sources, each under its own terms. Yahoo Finance data through `yfinance` is meant for personal use. Check the terms before you redistribute notes commercially.

## Limitations

- Commentary is rule-based: it describes what moved, not why.
- FRED series publish with a lag; Yahoo data may be delayed.
- `--demo` output is synthetic and must never be shown as real.
- For illustration only. Not investment advice.

MIT licence.
