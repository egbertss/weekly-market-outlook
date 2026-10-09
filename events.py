"""Forward-looking and filings data: macro calendar, earnings, SEC filings, politician trades.

Every fetcher returns a list of dicts and never raises. On failure it returns []
and the caller shows nothing for that block. Keys are read from environment variables.
"""
import os
import sys
from datetime import date, datetime, timedelta

import requests


def _warn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def _te(start, end, countries, min_importance):
    key = os.environ.get("TE_API_KEY")
    if not key:
        return None
    c = ",".join(x.replace(" ", "%20") for x in countries)
    r = requests.get(f"https://api.tradingeconomics.com/calendar/country/{c}/{start}/{end}",
                     params={"c": key, "f": "json", "importance": min_importance}, timeout=30)
    r.raise_for_status()
    return [{"when": str(e.get("Date", ""))[:16].replace("T", " "), "country": e.get("Country", ""),
             "event": e.get("Event", ""), "previous": e.get("Previous"), "forecast": e.get("Forecast") or e.get("TEForecast")}
            for e in r.json() if int(e.get("Importance") or 0) >= min_importance]


def _fmp(start, end, countries):
    """Financial Modeling Prep economic calendar. FMP_API_KEY (free signup; check your plan includes this endpoint)."""
    key = os.environ.get("FMP_API_KEY")
    if not key:
        return None
    data, err = None, ""
    for url in ["https://financialmodelingprep.com/stable/economic-calendar",
                "https://financialmodelingprep.com/api/v3/economic_calendar"]:
        try:
            r = requests.get(url, params={"from": start, "to": end, "apikey": key}, timeout=30)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, list) and j:
                data = j
                break
            err = str(j)[:200]
        except Exception as ex:
            err = str(ex)
    if data is None:
        raise ValueError(err or "empty response")
    iso = {"united states": "US", "euro area": "EU", "germany": "DE", "france": "FR", "italy": "IT",
           "united kingdom": "GB", "japan": "JP", "china": "CN", "switzerland": "CH"}
    want = {iso.get(c.lower(), c.upper()) for c in countries}
    return [{"when": str(e.get("date", ""))[:16], "country": e.get("country", ""), "event": e.get("event", ""),
             "previous": e.get("previous"), "forecast": e.get("estimate")}
            for e in data if str(e.get("impact", "")).lower() == "high" and e.get("country") in want]


FRED_KEY_RELEASES = ["Consumer Price Index", "Employment Situation", "Gross Domestic Product",
                     "Personal Income and Outlays", "Producer Price Index", "Advance Monthly Sales for Retail",
                     "Job Openings and Labor Turnover", "Industrial Production", "Surveys of Consumers"]
FRED_EXCLUDE = ["research", "fomc press release", "regional"]   # daily or duplicate releases


def _fred(start, end, keywords=None):
    """US official release dates from FRED. FRED_API_KEY (free). Dates only: no times, no forecasts."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    r = requests.get("https://api.stlouisfed.org/fred/releases/dates",
                     params={"api_key": key, "file_type": "json", "realtime_start": start, "realtime_end": end,
                             "include_release_dates_with_no_data": "true", "limit": 1000, "sort_order": "asc"}, timeout=30)
    r.raise_for_status()
    kw = [k.lower() for k in (keywords or FRED_KEY_RELEASES)]
    seen, rows = set(), []
    for e in r.json().get("release_dates", []):
        name, d = e.get("release_name", ""), e.get("date", "")
        if start <= d <= end and any(k in name.lower() for k in kw) \
                and not any(x in name.lower() for x in FRED_EXCLUDE) and (d, name) not in seen:
            seen.add((d, name))
            rows.append({"when": d, "country": "United States", "event": name, "previous": None, "forecast": None})
    return rows


def macro_calendar(start, end, countries, min_importance=3, manual=None, fred_keywords=None):
    """Tries Trading Economics, then FMP, then FRED (US only), using whichever key is set.
    `manual` rows from config.toml (e.g. ECB meetings) are always added."""
    rows, src = [], ""
    for name, fn in [("Trading Economics", lambda: _te(start, end, countries, min_importance)),
                     ("FMP", lambda: _fmp(start, end, countries)),
                     ("FRED", lambda: _fred(start, end, fred_keywords))]:
        try:
            got = fn()
        except Exception as ex:
            _warn(f"macro calendar via {name} failed: {ex}")
            continue
        if got is not None:
            rows, src = got, name
            break
    else:
        _warn("no calendar key set (TE_API_KEY, FMP_API_KEY or FRED_API_KEY), using manual entries only.")
    for m in manual or []:
        if start <= str(m.get("date", "")) <= end:
            rows.append({"when": m["date"], "country": m.get("country", ""), "event": m.get("event", ""),
                         "previous": None, "forecast": None})
    rows.sort(key=lambda x: x["when"])
    return rows, src


def earnings(tickers, start, end):
    """Next earnings date per ticker via yfinance, kept if it falls in [start, end]."""
    import yfinance as yf
    rows = []
    for name, t in tickers.items():
        try:
            cal = yf.Ticker(t).calendar
            dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else []
            for d in dates:
                d = d if isinstance(d, date) else datetime.fromisoformat(str(d)).date()
                if start <= d <= end:
                    rows.append({"when": d.isoformat(), "company": name, "ticker": t,
                                 "eps_est": cal.get("Earnings Average")})
        except Exception as ex:
            _warn(f"earnings {t}: {ex}")
    rows.sort(key=lambda x: x["when"])
    return rows


def sec_filings(tickers, since, user_agent, forms=("8-K", "10-Q", "10-K", "4")):
    """Recent SEC EDGAR filings for a watchlist. EDGAR requires a descriptive User-Agent with contact."""
    if not user_agent:
        _warn("sec_user_agent not set in config.toml, skipping SEC filings.")
        return []
    h = {"User-Agent": user_agent}
    rows = []
    try:
        m = requests.get("https://www.sec.gov/files/company_tickers.json", headers=h, timeout=30).json()
        cik = {v["ticker"].upper(): int(v["cik_str"]) for v in m.values()}
    except Exception as ex:
        _warn(f"SEC ticker map failed: {ex}")
        return []
    for t in tickers:
        c = cik.get(t.upper())
        if not c:
            continue
        try:
            j = requests.get(f"https://data.sec.gov/submissions/CIK{c:010d}.json", headers=h, timeout=30).json()
            rec = j["filings"]["recent"]
            n4 = 0
            for f, d, acc, doc in zip(rec["form"], rec["filingDate"], rec["accessionNumber"], rec["primaryDocument"]):
                if f not in forms or d < since:
                    continue
                if f == "4":
                    n4 += 1
                    continue
                rows.append({"when": d, "ticker": t, "form": f,
                             "url": f"https://www.sec.gov/Archives/edgar/data/{c}/{acc.replace('-', '')}/{doc}"})
            if n4:
                rows.append({"when": "last 7 days", "ticker": t, "form": f"{n4} x Form 4 (insider trades)", "url": ""})
        except Exception as ex:
            _warn(f"SEC {t}: {ex}")
    rows.sort(key=lambda x: (x["when"] != "last 7 days", x["when"], x["ticker"]), reverse=True)
    return rows


def politician_trades(since, tickers=None, limit=12):
    """US Congress trades via Quiver Quantitative. Needs QUIVER_API_KEY. Disclosures lag trades by up to 45 days."""
    key = os.environ.get("QUIVER_API_KEY")
    if not key:
        _warn("QUIVER_API_KEY not set, skipping politician trades.")
        return []
    try:
        r = requests.get("https://api.quiverquant.com/beta/live/congresstrading",
                         headers={"Authorization": f"Bearer {key}", "Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        rows = []
        for e in r.json():
            d = str(e.get("ReportDate", ""))[:10]
            if d < since or (tickers and e.get("Ticker") not in tickers):
                continue
            rows.append({"reported": d, "traded": str(e.get("TransactionDate", ""))[:10],
                         "who": e.get("Representative", ""), "ticker": e.get("Ticker", ""),
                         "side": e.get("Transaction", ""), "size": e.get("Range", "")})
        rows.sort(key=lambda x: x["reported"], reverse=True)
        return rows[:limit]
    except Exception as ex:
        _warn(f"politician trades failed: {ex}")
        return []


def demo_events(start):
    """Synthetic placeholders so the layout can be tested offline. Clearly fake."""
    d = start
    return (
        [{"when": f"{d} 13:30", "country": "United States", "event": "DEMO CPI YoY", "previous": "2.9%", "forecast": "2.8%"}],
        [{"when": d.isoformat(), "company": "DEMO Corp", "ticker": "DEMO", "eps_est": 1.23}],
        [{"when": d.isoformat(), "ticker": "DEMO", "form": "8-K", "url": ""}],
        [{"reported": d.isoformat(), "traded": d.isoformat(), "who": "DEMO Member", "ticker": "DEMO", "side": "Purchase", "size": "$1,001 - $15,000"}],
    )
