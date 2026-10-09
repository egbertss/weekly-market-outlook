# =====================================================================
# WEEKLY MARKET OUTLOOK, ONE-CELL COLAB VERSION
# Paste this whole file into one Colab code cell, fill in SETTINGS, run.
# Generated from the repo by build_colab.py. Do not edit the code below
# SETTINGS by hand, change the repo and rebuild instead.
# =====================================================================

# ---------------------------- SETTINGS -------------------------------
# API keys. Blank = that block is skipped. Never publish a file with keys in it.
FRED_API_KEY   = ""   # free: fredaccount.stlouisfed.org. US macro release dates
FMP_API_KEY    = ""   # optional: financialmodelingprep.com. US + Europe calendar with forecasts
TE_API_KEY     = ""   # optional, paid: Trading Economics
QUIVER_API_KEY = ""   # optional, paid: quiverquant.com. Not needed: Congress trades come free from Senate and House sites
SEC_CONTACT    = ""   # "Your Name you@email.com". Free, SEC requires it for filings

SETTINGS = {
    "note": {
        "client_name": "Valued client",
        "adviser": "Your name",
        "firm": "Your firm",
        "note_date": "",              # blank = latest trading day, or "2026-10-09"
        "world_benchmark": "MSCI World (URTH)",
        "public": False,              # True for LinkedIn: no client name or firm
    },
    "view": {
        "our_view": [],               # your own opinion, one string per bullet
        "next_week": [],              # anything the calendar misses
    },
    "equities": {
        "S&P 500": "^GSPC", "Euro Stoxx 50": "^STOXX50E", "FTSE MIB": "FTSEMIB.MI",
        "DAX": "^GDAXI", "CAC 40": "^FCHI", "MSCI World (URTH)": "URTH",
    },
    "other": {
        "EUR/USD": "EURUSD=X", "Gold": "GC=F", "Brent": "BZ=F",
        "US Treasuries 7-10y (IEF)": "IEF", "US IG credit (LQD)": "LQD", "US high yield (HYG)": "HYG",
    },
    "events": {
        "enabled": True,
        "europe_rates": True,
        "countries": ["united states", "euro area", "germany", "france", "italy"],
        "earnings_watchlist": {
            "ASML": "ASML.AS", "SAP": "SAP.DE", "LVMH": "MC.PA", "Nestle": "NESN.SW",
            "Intesa Sanpaolo": "ISP.MI", "UniCredit": "UCG.MI", "Eni": "ENI.MI",
            "Apple": "AAPL", "Microsoft": "MSFT", "Nvidia": "NVDA", "Alphabet": "GOOGL",
            "Amazon": "AMZN", "Meta": "META", "JPMorgan": "JPM", "Goldman Sachs": "GS",
        },
        "show_13f": True,             # big-fund positions from SEC 13F, needs SEC_CONTACT
        "funds_13f": {                # name: SEC CIK. The note shows the name EDGAR returns, so you can check each CIK
            "Berkshire Hathaway": 1067983, "Bridgewater Associates": 1350694, "Pershing Square": 1336528,
            "Soros Fund Management": 1029160, "Tiger Global": 1167483, "Renaissance Technologies": 1037389,
            "Duquesne Family Office": 1536411, "Appaloosa": 1656456, "Third Point": 1040273,
        },
        "news": True,                 # free headlines from public RSS feeds (Fed, ECB, CNBC)
        "sec_watchlist": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "JPM", "GS"],
        # Dates the APIs miss: ECB and FOMC decisions (copy from ecb.europa.eu and federalreserve.gov)
        "manual_events": [
            # {"date": "2026-10-29", "country": "Euro area", "event": "ECB monetary policy decision"},
        ],
    },
}
MAKE_PDF = True    # PDF as the main output (first run installs a browser, about 1 minute)

# ---- delivery (optional): fill in email and/or Telegram, then set SEND = True ----
SEND = False
# Email through your own mailbox. Use an APP PASSWORD, never your normal password.
#   iCloud: host smtp.mail.me.com, port 587, app password from account.apple.com > Sign-In and Security
#   Gmail:  host smtp.gmail.com,   port 465, app password from myaccount.google.com/apppasswords
SMTP_HOST     = ""
SMTP_PORT     = "587"
SMTP_USER     = ""      # your full email address
SMTP_PASSWORD = ""      # the app password
EMAIL_TO      = ""      # where to send it, comma separated for several
# Telegram: message @BotFather, send /newbot, copy the token. Then send any message to your new bot.
# Leave TELEGRAM_CHAT_ID blank on the first run: the output prints your chat id.
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID   = ""
# -------------------------- END SETTINGS -----------------------------

import os, sys, subprocess, types
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yfinance", "pypdf", "lxml"] + (["playwright"] if MAKE_PDF else []), check=False)
if MAKE_PDF:
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], check=False)
for _k, _v in {"FRED_API_KEY": FRED_API_KEY, "FMP_API_KEY": FMP_API_KEY,
               "TE_API_KEY": TE_API_KEY, "QUIVER_API_KEY": QUIVER_API_KEY,
               "SMTP_HOST": SMTP_HOST, "SMTP_PORT": SMTP_PORT, "SMTP_USER": SMTP_USER,
               "SMTP_PASSWORD": SMTP_PASSWORD, "EMAIL_TO": EMAIL_TO,
               "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN, "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID}.items():
    os.environ[_k] = _v
SETTINGS["events"]["sec_user_agent"] = SEC_CONTACT
os.chdir("/content") if os.path.isdir("/content") else None

# ======================= events.py =======================
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
_ev = types.SimpleNamespace(macro_calendar=macro_calendar, earnings=earnings, sec_filings=sec_filings, politician_trades=politician_trades, demo_events=demo_events)

# ======================= europe.py =======================
import io
import sys

import pandas as pd
import requests

BASE = "https://data-api.ecb.europa.eu/service/data/"
DAILY = {
    "Euro area AAA 2Y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    "Euro area AAA 10Y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
    "ECB deposit facility rate": "FM/B.U2.EUR.4F.KR.DFR.LEV",
}
MONTHLY = {   # month-end, published with a lag
    "Italy 10Y (monthly avg)": "IRS/M.IT.L.L40.CI.0000.EUR.N.Z",
    "Germany 10Y (monthly avg)": "IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
}


def _get(key, start):
    r = requests.get(BASE + key, params={"format": "csvdata", "startPeriod": start}, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    s = pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"])).dropna()
    return s.sort_index()


def _bp(s, days):
    past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return None if past.empty else (s.iloc[-1] - past.iloc[-1]) * 100


def euro_rates(start="2025-01-01"):
    out, ser = [], {}
    for name, key in {**DAILY, **MONTHLY}.items():
        try:
            ser[name] = _get(key, start)
        except Exception as ex:
            print(f"[warn] ECB {name}: {ex}", file=sys.stderr)
    today = pd.Timestamp.today().normalize()
    if "ECB deposit facility rate" in ser and len(ser["ECB deposit facility rate"]):
        d = ser["ECB deposit facility rate"]
        ser["ECB deposit facility rate"] = pd.concat([d, pd.Series([d.iloc[-1]], index=[today])]) if d.index[-1] < today else d
    def _asof(name, s):
        return s.index[-1].strftime("%b %Y") if name in MONTHLY or "monthly" in name else s.index[-1].date().isoformat()
    for name, s in ser.items():
        if len(s):
            out.append({"name": name, "asof": _asof(name, s), "level": float(s.iloc[-1]),
                        "w": _bp(s, 7) if name in DAILY else None, "m": _bp(s, 30) if name in DAILY else _bp(s, 31)})
    a, b = ser.get("Euro area AAA 2Y"), ser.get("Euro area AAA 10Y")
    if a is not None and b is not None and len(a) and len(b):
        sl = (b - a).dropna()
        out.append({"name": "Euro area AAA 2s10s slope", "asof": sl.index[-1].date().isoformat(), "level": float(sl.iloc[-1]),
                    "w": _bp(sl, 7), "m": _bp(sl, 30)})
    it, de = ser.get("Italy 10Y (monthly avg)"), ser.get("Germany 10Y (monthly avg)")
    if it is not None and de is not None:
        sp = (it - de).dropna()
        if len(sp):
            out.append({"name": "BTP-Bund spread (monthly avg)", "asof": sp.index[-1].strftime("%b %Y"), "level": float(sp.iloc[-1]) * 100,
                        "w": None, "m": _bp(sp, 31), "bp": True})
    return out


def demo_rates():
    return [{"name": "DEMO Euro area AAA 10Y", "asof": "2026-10-09", "level": 2.5, "w": 3.0, "m": -5.0},
            {"name": "DEMO BTP-Bund spread (monthly)", "asof": "2026-09-30", "level": 85.0, "w": None, "m": -4.0, "bp": True}]
_eu = types.SimpleNamespace(euro_rates=euro_rates, demo_rates=demo_rates)

# ======================= funds.py ========================
import sys
import time
import re
import xml.etree.ElementTree as ET

import requests

DEFAULT_FUNDS = {   # labels are only fallbacks: the table shows the name EDGAR returns
    "Berkshire Hathaway": 1067983,
    "Bridgewater Associates": 1350694,
    "Pershing Square": 1336528,
    "Soros Fund Management": 1029160,
    "Tiger Global": 1167483,
    "Renaissance Technologies": 1037389,
    "Duquesne Family Office": 1536411,
    "Appaloosa": 1656456,
    "Third Point": 1040273,
}


def _fwarn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def _fget(url, ua, as_json=True):
    time.sleep(0.15)                      # SEC fair-access limit is 10 requests per second
    r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    return r.json() if as_json else r.text


def _holdings(cik, acc, ua):
    """{cusip: (issuer, value_usd, shares)} for one filing, options excluded."""
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    items = _fget(folder + "/index.json", ua)["directory"]["item"]
    xmls = [i["name"] for i in items if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
    if not xmls:
        raise ValueError("no information table in filing")
    root = ET.fromstring(_fget(f"{folder}/{xmls[0]}", ua, as_json=False))
    for el in root.iter():                # drop namespaces, they vary by filer
        el.tag = el.tag.split("}")[-1]
    out, names = {}, {}
    for row in root.iter("infoTable"):
        if (row.findtext("putCall") or "").strip():
            continue
        cusip = (row.findtext("cusip") or "").strip().upper()
        name = re.sub(r"[.,]", "", (row.findtext("nameOfIssuer") or "").strip()).title()
        key = cusip[:6] or name            # first 6 CUSIP characters = issuer: share classes combine, renames don't split
        val = float(row.findtext("value") or 0)
        sh = float(row.findtext("shrsOrPrnAmt/sshPrnamt") or 0)
        a = out.get(key, (0.0, 0.0))
        out[key] = (a[0] + val, a[1] + sh)
        names.setdefault(key, name)
    # Since 2023 values are in dollars. Some filers still report thousands: implied prices under $1 give it away.
    px = sorted(v / sh for v, sh in out.values() if sh > 0 and v > 0)
    if px and px[len(px) // 2] < 1:
        out = {k: (v * 1000, sh) for k, (v, sh) in out.items()}
    return out, names


def _bn(x):
    return f"${x / 1e9:.1f}bn" if abs(x) >= 1e9 else f"${x / 1e6:.0f}m"


def fund_moves(funds, ua, top_n=3):
    if not ua:
        _fwarn("sec_user_agent not set, skipping 13F fund positions.")
        return []
    rows = []
    for label, cik in funds.items():
        try:
            sub = _fget(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", ua)
            rec = sub["filings"]["recent"]
            f13 = [(acc, fd, rd) for f, acc, fd, rd in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec["reportDate"])
                   if f == "13F-HR"][:2]
            if not f13:
                _fwarn(f"13F {label}: no 13F-HR filings found")
                continue
            now, nm = _holdings(cik, f13[0][0], ua)
            prev, pnm = _holdings(cik, f13[1][0], ua) if len(f13) > 1 else ({}, {})
            nm = {**pnm, **nm}                     # latest name wins
            total = sum(v for v, _ in now.values()) or 1
            top = [(nm[k], v) for k, v in sorted(now.items(), key=lambda x: -x[1][0])[:top_n]]
            flows = []                               # dollar value bought (+) or sold (-), at quarter-end price
            for n, (v, sh) in now.items():
                if n in prev and sh > 0 and prev[n][1] > 0:
                    flows.append((nm[n], (sh - prev[n][1]) * v / sh, sh / prev[n][1] - 1))
            adds = [x for x in sorted(flows, key=lambda x: -x[1]) if x[1] > 0][:top_n]
            cuts = [x for x in sorted(flows, key=lambda x: x[1]) if x[1] < 0][:top_n]
            new = sorted([(nm[n], v) for n, (v, _) in now.items() if n not in prev], key=lambda x: -x[1])[:top_n] if prev else []
            exits = sorted([(nm[n], v) for n, (v, _) in prev.items() if n not in now], key=lambda x: -x[1])[:top_n]
            rows.append({
                "fund": sub.get("name", label).title(), "quarter": f13[0][2], "filed": f13[0][1],
                "total_bn": total / 1e9, "n": len(now),
                "top": ", ".join(f"{n} {v / total:.0%}" for n, (v, _) in top),
                "adds": ", ".join(f"{n} +{_bn(d)} ({p:+.0%} shares)" if p < 10 else f"{n} +{_bn(d)} (from a small stake)" for n, d, p in adds) or "none",
                "cuts": ", ".join(f"{n} -{_bn(-d)} ({p:+.0%} shares)" for n, d, p in cuts) or "none",
                "new": ", ".join(f"{n} {_bn(v)}" for n, v in new) or "none",
                "exits": ", ".join(n for n, _ in exits) or "none",
            })
        except Exception as ex:
            _fwarn(f"13F {label}: {ex}")
    if rows:
        latest = max(r["quarter"] for r in rows)
        for r in rows:
            r["stale"] = r["quarter"] < latest
    rows.sort(key=lambda r: (r["stale"], -r["total_bn"]))
    return rows


def demo_funds():
    return [{"fund": "DEMO Capital", "quarter": "2026-06-30", "filed": "2026-08-14", "total_bn": 12.3, "n": 40,
             "top": "Demo A 20%, Demo B 15%", "adds": "Demo C +40%", "cuts": "Demo D -30%", "new": "Demo E", "exits": "Demo F"}]
_fu = types.SimpleNamespace(fund_moves=fund_moves, demo_funds=demo_funds, DEFAULT_FUNDS=DEFAULT_FUNDS)

# ======================= politics.py =====================
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

UA = {"User-Agent": "Mozilla/5.0 (weekly-market-outlook; research use)"}


def _pwarn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


# ---------------- Senate ----------------
def _iso(d):
    try:
        return datetime.strptime(str(d).strip(), "%m/%d/%Y").date().isoformat()
    except Exception:
        return str(d)


def _asset(a):
    a = re.sub(r"\s+", " ", str(a))
    a = re.sub(r"Rate/Coupon:\s*([\d.]+)%?", r"bond \1%", a)
    a = re.sub(r"Matur\w*:\s*([\d/]+)", r"due \1", a)
    return a[:70]


def senate_trades(since, limit=40):
    base = "https://efdsearch.senate.gov"
    s = requests.Session()
    s.headers.update(UA)
    try:
        home = s.get(base + "/search/home/", timeout=30).text
        tok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', home).group(1)
        s.post(base + "/search/home/", data={"prohibition_agreement": "1", "csrfmiddlewaretoken": tok},
               headers={"Referer": base + "/search/home/"}, timeout=30)
        csrf = s.cookies.get("csrftoken") or s.cookies.get("csrf")
        d0 = datetime.fromisoformat(since).strftime("%m/%d/%Y 00:00:00")
        r = s.post(base + "/search/report/data/", headers={"Referer": base + "/search/", "X-CSRFToken": csrf or ""},
                   data={"start": "0", "length": "100", "report_types": "[11]", "filer_types": "[]",
                         "submitted_start_date": d0, "submitted_end_date": "", "candidate_state": "",
                         "senator_state": "", "office_id": "", "first_name": "", "last_name": "",
                         "csrfmiddlewaretoken": csrf or ""}, timeout=30)
        r.raise_for_status()
        reports = r.json().get("data", [])
    except Exception as ex:
        _pwarn(f"Senate disclosures failed: {ex}")
        return []
    rows = []
    import pandas as pd
    for rep in reports:
        try:
            first, last, link_html, filed = rep[0], rep[1], rep[3], rep[4]
            who = f"Sen. {first.title()} {last.title()}"
            href = re.search(r'href="([^"]+)"', link_html).group(1)
            if "/paper/" in href:
                rows.append({"reported": _iso(filed), "traded": "", "who": who, "ticker": "", "side": "paper filing",
                             "size": "", "url": base + href})
                continue
            page = s.get(base + href, timeout=30).text
            for t in pd.read_html(io.StringIO(page)):
                cols = {c.lower(): c for c in t.columns.astype(str)}
                if "ticker" not in cols:
                    continue
                for _, x in t.iterrows():
                    tk = str(x[cols["ticker"]]).strip()
                    rows.append({"reported": _iso(filed), "traded": _iso(x.get(cols.get("transaction date", ""), "")),
                                 "who": who, "ticker": "" if tk in ("--", "nan") else tk,
                                 "side": str(x.get(cols.get("type", ""), "")), "size": str(x.get(cols.get("amount", ""), "")),
                                 "asset": _asset(x.get(cols.get("asset name", ""), "")),
                                 "url": base + href})
        except Exception as ex:
            _pwarn(f"Senate report skipped: {ex}")
        if len(rows) >= limit:
            break
    return rows[:limit]


# ---------------- House ----------------
def house_filings(since, limit=25, read_pdfs=True):
    d_since = date.fromisoformat(since)
    roots = []
    for yr in sorted({d_since.year, date.today().year}):
        try:
            z = requests.get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{yr}FD.zip",
                             headers=UA, timeout=60)
            z.raise_for_status()
            zf = zipfile.ZipFile(io.BytesIO(z.content))
            xml_name = [n for n in zf.namelist() if n.lower().endswith(".xml")][0]
            roots.append((yr, ET.fromstring(zf.read(xml_name))))
        except Exception as ex:
            _pwarn(f"House disclosures {yr} failed: {ex}")
    if not roots:
        return []
    out = []
    for yr, root in roots:
      for m in root.iter("Member"):
          if (m.findtext("FilingType") or "").strip() != "P":
              continue
          try:
              filed = datetime.strptime(m.findtext("FilingDate").strip(), "%m/%d/%Y").date()
          except Exception:
              continue
          if filed < d_since:
              continue
          doc = (m.findtext("DocID") or "").strip()
          out.append({"reported": filed.isoformat(),
                      "who": f"Rep. {(m.findtext('First') or '').strip()} {(m.findtext('Last') or '').strip()} ({(m.findtext('StateDst') or '').strip()})",
                      "url": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{yr}/{doc}.pdf", "tickers": ""})
    out.sort(key=lambda x: x["reported"], reverse=True)
    out = out[:limit]
    if read_pdfs:
        try:
            from pypdf import PdfReader
        except ImportError:
            _pwarn("pypdf not installed, House tickers not read (pip install pypdf).")
            return out
        for f in out:
            try:
                pdf = requests.get(f["url"], headers=UA, timeout=30).content
                txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
                tk = sorted(set(re.findall(r"\(([A-Z][A-Z.]{0,5})\)", txt)) - {"SP", "JT", "DC", "ST", "OP", "NA"})
                f["tickers"] = ", ".join(tk[:12]) if tk else "not readable, open PDF"
            except Exception as ex:
                f["tickers"] = "not readable, open PDF"
                _pwarn(f"House PDF {f['url']}: {ex}")
    return out


def demo_politics():
    return ([{"reported": "2026-10-08", "traded": "2026-09-20", "who": "DEMO Senator", "ticker": "DEMO",
              "side": "Purchase", "size": "$1,001 - $15,000", "url": ""}],
            [{"reported": "2026-10-07", "who": "DEMO Rep (XX01)", "tickers": "DEMO", "url": ""}])
_po = types.SimpleNamespace(senate_trades=senate_trades, house_filings=house_filings, demo_politics=demo_politics)

# ======================= news.py =========================
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

DEFAULT_FEEDS = {
    "Federal Reserve": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
    "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
}
# routine items that are not market news
EXCLUDE = ["approval of application", "announces approval", "enforcement action", "termination of enforcement",
           "comment period", "nobel", "my husband", "my wife", "my brother", "my sister", "my parents"]


def _nwarn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def _date(txt):
    if not txt:
        return None
    try:
        d = parsedate_to_datetime(txt)
    except Exception:
        try:
            d = datetime.fromisoformat(txt.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def headlines(feeds=None, days=7, per_feed=5, exclude=None):
    excl = [x.lower() for x in (exclude if exclude is not None else EXCLUDE)]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for src, url in (feeds or DEFAULT_FEEDS).items():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (weekly-market-outlook)"}, timeout=20)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for el in root.iter():
                el.tag = el.tag.split("}")[-1]
            items = []
            for it in list(root.iter("item")) + list(root.iter("entry")):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                if not link:
                    l = it.find("link")
                    link = l.get("href", "") if l is not None else ""
                d = _date(it.findtext("pubDate") or it.findtext("published") or it.findtext("updated") or it.findtext("date"))
                if title and (d is None or d >= since) and not any(x in title.lower() for x in excl):
                    items.append({"source": src, "title": title, "url": link, "date": d.date().isoformat() if d else ""})
            out += items[:per_feed]
        except Exception as ex:
            _nwarn(f"news feed {src}: {ex}")
    return out


def demo_news():
    return [{"source": "DEMO", "title": "DEMO headline", "url": "", "date": "2026-10-09"}]
_nw = types.SimpleNamespace(headlines=headlines, demo_news=demo_news)

# ======================= notify.py =======================
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

import requests


def _ntwarn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def send_email(subject, text, attachment):
    host, user, pwd, to = (os.environ.get(k, "") for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"))
    if not (host and user and pwd and to):
        return False
    port = int(os.environ.get("SMTP_PORT") or 465)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    p = Path(attachment)
    sub = "pdf" if p.suffix == ".pdf" else "html"
    msg.add_attachment(p.read_bytes(), maintype="application" if sub == "pdf" else "text", subtype=sub, filename=p.name)
    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=60) as s:
                s.login(user, pwd); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=60) as s:
                s.starttls(context=ctx); s.login(user, pwd); s.send_message(msg)
        print("Email sent to", to)
        return True
    except Exception as ex:
        _ntwarn(f"email failed: {ex}")
        return False


def telegram_chat_ids(token):
    """Helper: after you send any message to your bot, this lists the chat ids it can see."""
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
    return sorted({(u.get("message") or u.get("channel_post") or {}).get("chat", {}).get("id") for u in r.get("result", [])} - {None})


def send_telegram(caption, attachment):
    token, chats = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token:
        return False
    if not chats:
        try:
            ids = telegram_chat_ids(token)
            _ntwarn(f"TELEGRAM_CHAT_ID not set. Chats seen by your bot: {ids or 'none, send the bot a message first'}")
        except Exception as ex:
            _ntwarn(f"telegram lookup failed: {ex}")
        return False
    ok = True
    for chat in [c.strip() for c in chats.split(",") if c.strip()]:
        try:
            with open(attachment, "rb") as f:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                                  data={"chat_id": chat, "caption": caption[:1000]}, files={"document": f}, timeout=60)
            r.raise_for_status()
            print("Telegram sent to", chat)
        except Exception as ex:
            ok = False
            _ntwarn(f"telegram to {chat} failed: {ex}")
    return ok


def deliver(subject, text, attachment):
    sent = []
    if send_email(subject, text, attachment):
        sent.append("email")
    if send_telegram(subject + "\n\n" + text, attachment):
        sent.append("telegram")
    if not sent:
        print("Nothing sent: no email or Telegram settings found.")
    return sent
_nt = types.SimpleNamespace(deliver=deliver, telegram_chat_ids=telegram_chat_ids)

# ======================= outlook.py ======================
import io, base64, sys
from pathlib import Path
ARGS = types.SimpleNamespace(demo=False, out='reports', pdf=MAKE_PDF, send=SEND, config=None)
_cfg = SETTINGS
CLIENT_NAME = _cfg["note"]["client_name"]
ADVISER = _cfg["note"]["adviser"]
FIRM = _cfg["note"]["firm"]
NOTE_DATE = _cfg["note"].get("note_date") or None
OUR_VIEW = _cfg.get("view", {}).get("our_view", [])
NEXT_WEEK = _cfg.get("view", {}).get("next_week", [])
EQUITIES = _cfg["equities"]
OTHER = _cfg["other"]
WORLD = _cfg["note"]["world_benchmark"]
EV = _cfg.get("events", {})
import os as _os
if _os.environ.get("SEC_CONTACT"):
    EV["sec_user_agent"] = _os.environ["SEC_CONTACT"]

# ---- data ----
# 1. Imports, helpers and data download
from datetime import date
import numpy as np
import pandas as pd
import requests
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def warn(msg):
    print(f"[warn] {msg}", file=sys.stderr)

FRED_IDS = {"DGS3MO": "3M", "DGS2": "2Y", "DGS5": "5Y", "DGS10": "10Y", "DGS30": "30Y",
            "BAMLC0A0CM": "IG OAS", "BAMLH0A0HYM2": "HY OAS",
            "DFF": "Fed funds", "T10YIE": "10Y breakeven", "VIXCLS": "VIX"}

def fetch_fred(ids, start):
    """Each FRED series as its own Series (values in percent), via the public CSV endpoint."""
    out = {}
    for sid in ids:
        try:
            r = requests.get("https://fred.stlouisfed.org/graph/fredgraph.csv",
                             params={"id": sid, "cosd": start}, timeout=20)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").values,
                          index=pd.to_datetime(df.iloc[:, 0])).dropna()
            if len(s):
                out[sid] = s
        except Exception as e:
            warn(f"FRED {sid} failed: {e}")
    return out

def fetch_prices(tickers, start):
    """Daily closes, one column per label."""
    import yfinance as yf
    raw = yf.download(list(tickers.values()), start=start, auto_adjust=True, progress=False)["Close"]
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(list(tickers.values())[0])
    inv = {v: k for k, v in tickers.items()}
    raw = raw.rename(columns=inv).ffill()
    raw = raw[[k for k in tickers if k in raw.columns]]
    return raw.dropna(how="all")

def at(s, d):
    """Last value on or before date d."""
    s = s.dropna()
    s = s[s.index <= pd.Timestamp(d)]
    return float(s.iloc[-1]) if len(s) else np.nan

START = (pd.Timestamp.today().normalize() - pd.DateOffset(years=1, months=2)).strftime("%Y-%m-%d")
ALL_TICKERS = {**EQUITIES, **OTHER}
if ARGS.demo:
    from demo import make_demo
    prices, fred = make_demo(ALL_TICKERS, FRED_IDS, START)
else:
    prices = fetch_prices(ALL_TICKERS, START)
    fred = fetch_fred(FRED_IDS, START)
print("Prices:", prices.shape, "| latest", prices.index.max().date())
print("FRED series loaded:", sorted(fred))


# ---- numbers ----
# 2. Numbers: weekly, monthly and year-to-date changes
ASOF = pd.Timestamp(NOTE_DATE) if NOTE_DATE else prices.index.max().normalize()
D1W, D1M = ASOF - pd.Timedelta(days=7), ASOF - pd.DateOffset(months=1)
DYTD = pd.Timestamp(ASOF.year - 1, 12, 31)

def pct(s, d0):
    a, b = at(s, d0), at(s, ASOF)
    return (b / a - 1) * 100 if a and not np.isnan(a) and not np.isnan(b) else np.nan

perf = pd.DataFrame({
    "Last": {k: at(prices[k], ASOF) for k in prices.columns},
    "1W %": {k: pct(prices[k], D1W) for k in prices.columns},
    "1M %": {k: pct(prices[k], D1M) for k in prices.columns},
    "YTD %": {k: pct(prices[k], DYTD) for k in prices.columns},
})

def lvl(sid, d=None):
    return at(fred[sid], d or ASOF) if sid in fred else np.nan

def chg_bp(sid, d0):
    a, b = lvl(sid, d0), lvl(sid)
    return (b - a) * 100

rows = {}
for sid in ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"]:
    if sid in fred:
        rows[f"US Treasury {FRED_IDS[sid]}"] = (lvl(sid), chg_bp(sid, D1W), chg_bp(sid, D1M), chg_bp(sid, DYTD), "%")
if "DGS2" in fred and "DGS10" in fred:
    sl = lambda d: (lvl("DGS10", d) - lvl("DGS2", d)) * 100
    rows["Curve 2s10s (bp)"] = (sl(ASOF), sl(ASOF) - sl(D1W), sl(ASOF) - sl(D1M), sl(ASOF) - sl(DYTD), "bp")
for sid, name in [("BAMLC0A0CM", "US IG spread (bp)"), ("BAMLH0A0HYM2", "US HY spread (bp)")]:
    if sid in fred:
        rows[name] = (lvl(sid) * 100, chg_bp(sid, D1W), chg_bp(sid, D1M), chg_bp(sid, DYTD), "bp")
if "T10YIE" in fred:
    rows["10Y breakeven inflation"] = (lvl("T10YIE"), chg_bp("T10YIE", D1W), chg_bp("T10YIE", D1M), chg_bp("T10YIE", DYTD), "%")
if "VIXCLS" in fred:
    v = lambda d: lvl("VIXCLS", d)
    rows["VIX"] = (v(ASOF), v(ASOF) - v(D1W), v(ASOF) - v(D1M), v(ASOF) - v(DYTD), "pts")
rates = pd.DataFrame(rows, index=["Level", "1W chg", "1M chg", "YTD chg", "unit"]).T

fred_asof = max((s.index.max() for s in fred.values()), default=None)
print("Note date:", ASOF.date(), "| FRED data to:", fred_asof.date() if fred_asof is not None else "n/a")
print(perf.round(2))


# ---- commentary ----
# 3. Commentary: rule based, describes moves, does not explain causes
def move(name, x, unit="%", small=0.3):
    if np.isnan(x):
        return None
    if abs(x) < small:
        return f"{name} was little changed ({x:+.1f}{unit})"
    return f"{name} {'rose' if x > 0 else 'fell'} {abs(x):.1f}{unit}"

def cap(t):
    return t[:1].upper() + t[1:]

def join(items):
    items = [i for i in items if i]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]

def p1w(k):
    return perf.loc[k, "1W %"] if k in perf.index else np.nan

def percentile(sid, mult=1.0):
    s = fred[sid][fred[sid].index > ASOF - pd.DateOffset(years=1)]
    return float((s <= lvl(sid)).mean() * 100) if len(s) > 20 else np.nan

def band(p):
    return "near the tight end" if p <= 20 else "near the wide end" if p >= 80 else "in the middle of the range"

takeaways = []

# Equities
eq = [k for k in EQUITIES if k in perf.index and not np.isnan(p1w(k))]
if eq:
    parts = []
    if WORLD in eq:
        parts.append(move("The MSCI World (" + WORLD.split("(")[-1].rstrip(")") + ")", p1w(WORLD), "%", 0.3) + " over the week.")
    others = [k for k in eq if k != WORLD]
    if others:
        parts.append(cap(join([move(k, p1w(k)) for k in others])) + ".")
        best, worst = max(others, key=p1w), min(others, key=p1w)
        if best != worst:
            parts.append(f"{best} led and {worst} lagged.")
    ytd = perf.loc[WORLD, "YTD %"] if WORLD in perf.index else np.nan
    if not np.isnan(ytd):
        parts.append(f"The MSCI World is {ytd:+.1f}% year to date.")
    takeaways.append(("Equities", " ".join(parts)))

# Rates
if "DGS10" in fred:
    _c = chg_bp('DGS10', D1W)
    t = [f"The US 10-year Treasury yield was unchanged at {lvl('DGS10'):.2f}%." if abs(_c) < 0.5 else
         f"The US 10-year Treasury yield {'rose' if _c > 0 else 'fell'} {abs(_c):.0f}bp to {lvl('DGS10'):.2f}%."]
    if "DGS2" in fred:
        t.append(f"The 2-year ended at {lvl('DGS2'):.2f}% ({chg_bp('DGS2', D1W):+.0f}bp).")
        slope = (lvl("DGS10") - lvl("DGS2")) * 100
        shape = "inverted" if slope < 0 else "flat" if slope < 25 else "moderately positive" if slope < 75 else "steep"
        t.append(f"The 2s10s slope is {slope:+.0f}bp, which is {shape}.")
    if "DFF" in fred:
        t.append(f"The effective Fed funds rate is {lvl('DFF'):.2f}%.")
    if "T10YIE" in fred:
        t.append(f"Ten-year breakeven inflation is {lvl('T10YIE'):.2f}% ({chg_bp('T10YIE', D1W):+.0f}bp on the week).")
    takeaways.append(("Rates", " ".join(t)))

# Credit
cr = []
for sid, nm in [("BAMLC0A0CM", "Investment grade"), ("BAMLH0A0HYM2", "High yield")]:
    if sid in fred:
        d, p = chg_bp(sid, D1W), percentile(sid)
        way = "tightened" if d < -0.5 else "widened" if d > 0.5 else "were unchanged"
        s = (f"{nm} spreads {way}" + (f" by {abs(d):.0f}bp to" if abs(d) > 0.5 else " at") + f" {lvl(sid) * 100:.0f}bp")
        if not np.isnan(p):
            s += f", {band(p)} of the past year"
        cr.append(s + ".")
if cr:
    takeaways.append(("Credit", " ".join(cr)))

# FX, commodities, volatility
xa = []
for k, nm in [("EUR/USD", "EUR/USD"), ("Gold", "Gold"), ("Brent", "Brent crude")]:
    if k in perf.index and not np.isnan(p1w(k)):
        xa.append(move(nm, p1w(k)) + (f" to {perf.loc[k, 'Last']:,.2f}" if k != "Gold" else f" to {perf.loc[k, 'Last']:,.0f}"))
txt = (join(xa) + ".") if xa else ""
if "VIXCLS" in fred:
    vx = lvl("VIXCLS")
    mood = "a low" if vx < 15 else "a normal" if vx < 20 else "an elevated" if vx < 30 else "a high"
    txt += f" The VIX is at {vx:.1f}, {mood} level."
if txt.strip():
    takeaways.append(("FX, commodities and volatility", cap(txt.strip())))

for h, t in takeaways:
    print(f"{h}: {t}\n")


# ---- charts ----
# 4. Charts (one axis per chart, thin lines, recessive grid, direct labels plus legend)
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
BLUES = ["#b9d3f2", "#7fb0e8", "#2a78d6", "#14447f"]      # one hue, light to dark = older to newer
CAT = [BLUE, ORANGE, AQUA, YELLOW]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False,
})

def to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()

def spread_labels(ys, gap):
    """Nudge end-of-line labels apart so they never overlap."""
    order = np.argsort(ys)
    out = np.array(ys, dtype=float)
    for i in range(1, len(order)):
        a, b = order[i - 1], order[i]
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    return out

charts = {}

# Chart 1: equities rebased to 100, last six months
eqcols = [k for k in EQUITIES if k in prices.columns]
if eqcols:
    start6 = ASOF - pd.DateOffset(months=6)
    px = prices.loc[(prices.index >= start6) & (prices.index <= ASOF), eqcols].ffill().dropna(how="all")
    reb = px / px.bfill().iloc[0] * 100
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ends = [float(reb[c].dropna().iloc[-1]) for c in eqcols]
    lab = spread_labels(ends, (max(ends) - min(ends) + 1) * 0.08)
    for i, c in enumerate(eqcols):
        ax.plot(reb.index, reb[c], color=CAT[i % 4], lw=2, label=c)
        ax.text(1.01, lab[i], f"{c} {ends[i]:.0f}", transform=ax.get_yaxis_transform(), color=INK,
                fontsize=9, va="center", clip_on=False)
    ax.set_title("Equities, rebased to 100 (six months)", loc="left", fontsize=11, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=len(eqcols), fontsize=9, labelcolor=INK)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(reb.index[0], reb.index[-1])
    charts["equities"] = to_b64(fig)

# Chart 2: US Treasury curve, four dates (one hue, darker = more recent)
curve_ids = [s for s in ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"] if s in fred]
if len(curve_ids) >= 4:
    snaps = [("Start of year", DYTD), ("1 month ago", D1M), ("1 week ago", D1W), ("Latest", ASOF)]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    xs = np.arange(len(curve_ids))
    for (nm, d), col, lw in zip(snaps, BLUES, [1.6, 1.6, 1.8, 2.6]):
        ys = [lvl(s, d) for s in curve_ids]
        ax.plot(xs, ys, color=col, lw=lw, marker="o", ms=4, label=nm)
    ax.set_xticks(xs)
    ax.set_xticklabels([FRED_IDS[s] for s in curve_ids])
    ax.set_ylabel("Yield, %")
    ax.set_title("US Treasury yield curve", loc="left", fontsize=11, color=INK)
    ax.legend(loc="best", fontsize=9, labelcolor=INK)
    charts["curve"] = to_b64(fig)

# Chart 3: credit spreads, two panels (different scales, so never one shared axis)
sp = [(sid, nm, c) for sid, nm, c in [("BAMLC0A0CM", "Investment grade spread (bp)", BLUE),
                                      ("BAMLH0A0HYM2", "High yield spread (bp)", ORANGE)] if sid in fred]
if sp:
    fig, axes = plt.subplots(1, len(sp), figsize=(8, 3.2), squeeze=False)
    for ax, (sid, nm, col) in zip(axes[0], sp):
        s = fred[sid][(fred[sid].index > ASOF - pd.DateOffset(years=1)) & (fred[sid].index <= ASOF)] * 100
        ax.plot(s.index, s.values, color=col, lw=2)
        ax.axhline(float(s.median()), color=MUTED, lw=1, ls=(0, (4, 3)), alpha=0.7)
        ax.annotate(f"{s.iloc[-1]:.0f}", (s.index[-1], s.iloc[-1]), xytext=(4, 6), textcoords="offset points",
                    color=INK, fontsize=9)
        ax.plot([s.index[-1]], [s.iloc[-1]], "o", color=col, ms=6, mec=SURFACE, mew=2)
        ax.set_title(nm, loc="left", fontsize=10, color=INK)
        ax.text(0.01, 0.03, "dashed = 1y median", transform=ax.transAxes, fontsize=8, color=MUTED)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    charts["credit"] = to_b64(fig)

# Chart 4: one-week performance, sorted, two-hue diverging (blue up, orange down)
w = perf["1W %"].dropna().sort_values()
if len(w):
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(w) + 1.2))
    cols = [BLUE if v >= 0 else ORANGE for v in w.values]
    ax.barh(w.index, w.values, color=cols, height=0.55)
    ax.axvline(0, color=MUTED, lw=1)
    pad = (w.abs().max() or 1) * 0.02
    for i, v in enumerate(w.values):
        ax.text(v + (pad if v >= 0 else -pad), i, f"{v:+.1f}%", va="center", ha="left" if v >= 0 else "right",
                fontsize=9, color=INK)
    lim = (w.abs().max() or 1) * 1.25
    ax.set_xlim(-lim, lim)
    ax.grid(axis="y", visible=False)
    ax.set_title("One-week performance (blue up, orange down)", loc="left", fontsize=11, color=INK)
    charts["weekly"] = to_b64(fig)

print("Charts built:", list(charts))


# ---- note ----
# 5. Build the note as one HTML file
import html as _h

def fmt_table(df, cols, formats, caption):
    head = "".join(f"<th>{_h.escape(c)}</th>" for c in ["", *cols])
    body = ""
    for idx, r in df.iterrows():
        cells = "".join(f"<td>{formats[c](r)}</td>" for c in cols)
        body += f"<tr><th scope='row'>{_h.escape(str(idx))}</th>{cells}</tr>"
    return f"<table><caption>{caption}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"

def sgn(x, d=1, unit=""):
    return "n/a" if pd.isna(x) else f"{x:+.{d}f}{unit}"

mkt_html = fmt_table(
    perf, ["Last", "1W %", "1M %", "YTD %"],
    {"Last": lambda r: "n/a" if pd.isna(r["Last"]) else (f"{r['Last']:.4f}" if r.name.count("/") == 1 and len(r.name) == 7 else f"{r['Last']:,.2f}"),
     "1W %": lambda r: sgn(r["1W %"], 1, "%"), "1M %": lambda r: sgn(r["1M %"], 1, "%"),
     "YTD %": lambda r: sgn(r["YTD %"], 1, "%")}, "Markets")

def lvl_fmt(r):
    if pd.isna(r["Level"]):
        return "n/a"
    return f"{r['Level']:.2f}%" if r["unit"] == "%" else f"{r['Level']:.0f}" if r["unit"] == "bp" else f"{r['Level']:.1f}"

def chg_fmt(col):
    return lambda r: sgn(r[col], 0 if r["unit"] in ("%", "bp") else 1, "bp" if r["unit"] in ("%", "bp") else "")

rates_html = fmt_table(rates, ["Level", "1W chg", "1M chg", "YTD chg"],
                       {"Level": lvl_fmt, "1W chg": chg_fmt("1W chg"), "1M chg": chg_fmt("1M chg"),
                        "YTD chg": chg_fmt("YTD chg")}, "Rates, credit and volatility") if len(rates) else ""

def img(key, alt):
    return f"<img alt='{alt}' src='data:image/png;base64,{charts[key]}'>" if key in charts else ""

def bullets(items):
    return "<ul>" + "".join(f"<li>{_h.escape(i)}</li>" for i in items) + "</ul>" if items else ""

take_html = "".join(f"<h3>{_h.escape(h)}</h3><p>{_h.escape(t)}</p>" for h, t in takeaways)
view_html = f"<h2>Our view</h2>{bullets(OUR_VIEW)}" if OUR_VIEW else ""
next_html = f"<h2>Next week</h2>{bullets(NEXT_WEEK)}" if NEXT_WEEK else ""
fred_note = f"US rates and credit data from FRED to {fred_asof.date()}." if fred_asof is not None else ""

PUBLIC = _cfg["note"].get("public", False)
PREP = (f"Prepared by {_h.escape(ADVISER)}." if PUBLIC else
        f"Prepared for {_h.escape(CLIENT_NAME)} by {_h.escape(ADVISER)}, {_h.escape(FIRM)}.")
# ---- events ----
# 6. Week ahead: macro calendar, earnings, SEC filings, politician trades
from datetime import timedelta
import os

def _table(caption, head, rows):
    if not rows:
        return ""
    th = "".join(f"<th>{_h.escape(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td style='text-align:left'>{_h.escape(str(c if c is not None else ''))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><caption>{_h.escape(caption)}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

_today = ASOF.date()
_mon = _today + timedelta(days=(7 - _today.weekday()) % 7 or 7)   # next Monday
_fri = _mon + timedelta(days=4)
_back = (_today - timedelta(days=7)).isoformat()
_mac_src = ""
if EV.get("enabled", True):
    if ARGS.demo:
        _mac, _earn, _sec, _pol = _ev.demo_events(_mon)
        _pol, _house = _po.demo_politics()
    else:
        _mac, _mac_src = _ev.macro_calendar(_mon.isoformat(), _fri.isoformat(), EV.get("countries", ["united states", "euro area"]),
                                            manual=EV.get("manual_events", []), fred_keywords=EV.get("fred_releases"))
        _earn = _ev.earnings(EV.get("earnings_watchlist", {}), _mon, _fri)
        _sec = _ev.sec_filings(list(EV.get("sec_watchlist", [])), _back, EV.get("sec_user_agent", ""))
        _pol = _ev.politician_trades(_back, set(EV.get("sec_watchlist", [])) or None) if os.environ.get("QUIVER_API_KEY") else []
        _house = []
        if not _pol and EV.get("congress_official", True):
            _pol = _po.senate_trades(_back)
            _house = _po.house_filings(_back)
else:
    _mac = _earn = _sec = _pol = []
    _house = []
events_html = ""
if _mac or _earn:
    events_html += f"<h2>Week ahead ({_mon.strftime('%d %b')} to {_fri.strftime('%d %b')})</h2>"
    events_html += _table("Key macro releases" + (f" ({_mac_src})" if _mac_src else ""), ["When (UTC)", "Country", "Event", "Previous", "Forecast"],
                          [(r["when"], r["country"], r["event"], r["previous"], r["forecast"]) for r in _mac[:15]])
    events_html += _table("Earnings from the watchlist", ["Date", "Company", "Ticker", "EPS est."],
                          [(r["when"], r["company"], r["ticker"], f"{r['eps_est']:.2f}" if isinstance(r["eps_est"], (int, float)) else "") for r in _earn])
def _link_table(caption, head, rows):
    """Like _table, but the last item of each row is a URL shown as a link."""
    if not rows:
        return ""
    th = "".join(f"<th>{_h.escape(h)}</th>" for h in head)
    body = ""
    for r in rows:
        *cells, url = r
        tds = "".join(f"<td style='text-align:left'>{_h.escape(str(c or ''))}</td>" for c in cells)
        link = f"<a href='{_h.escape(url)}'>filing</a>" if url else ""
        body += f"<tr>{tds}<td style='text-align:left'>{link}</td></tr>"
    return f"<table><caption>{_h.escape(caption)}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

if _sec or _pol or _house:
    events_html += "<h2>Filings and disclosures (last 7 days)</h2>"
    events_html += _table("SEC filings, watchlist", ["Filed", "Ticker", "Form"], [(r["when"], r["ticker"], r["form"]) for r in _sec[:20]])
    events_html += _link_table("US Senate trades reported in the last 7 days (trades can be up to 45 days older)",
                               ["Reported", "Traded", "Senator", "Ticker / asset", "Side", "Size", "Source"],
                               [(r["reported"], r["traded"], r["who"], r["ticker"] or r.get("asset", ""), r["side"], r["size"], r.get("url", "")) for r in _pol])
    events_html += _link_table("US House trade reports filed in the last 7 days",
                               ["Filed", "Member", "Tickers in report", "Source"],
                               [(r["reported"], r["who"], r["tickers"], r["url"]) for r in _house])

# ---- Europe ----
_er = _eu.demo_rates() if ARGS.demo else (_eu.euro_rates() if EV.get("europe_rates", True) else [])
def _f(x, d=0, suf=""):
    return "" if x is None else f"{x:+.{d}f}{suf}"
europe_html = ""
if _er:
    _rows = [(r["name"], r["asof"], f"{r['level']:.0f} bp" if r.get("bp") else f"{r['level']:.2f}%",
              _f(r["w"], 0, " bp"), _f(r["m"], 0, " bp")) for r in _er]
    europe_html = "<h2>Euro area rates</h2>" + _table("ECB Data Portal", ["Series", "As of", "Level", "1W chg", "1M chg"], _rows)

# ---- big funds (13F) ----
_funds_cfg = {k: int(v) for k, v in EV.get("funds_13f", {}).items()} or _fu.DEFAULT_FUNDS
if ARGS.demo:
    _fd = _fu.demo_funds()
elif EV.get("enabled", True) and EV.get("show_13f", True):
    _fd = _fu.fund_moves(_funds_cfg, EV.get("sec_user_agent", ""))
else:
    _fd = []
funds_html = ""
if _fd:
    funds_html = ("<h2>Big funds: latest 13F filings</h2>"
                  "<p class='small'>US-listed long positions at quarter end, filed up to 45 days later. "
                  "Adds and cuts are ranked by the dollar value of shares bought or sold versus the previous quarter, "
                  "at the quarter-end price. Share classes are combined. Options excluded.</p>")
    for r in _fd:
        _stale = " [no newer 13F filed]" if r.get("stale") else ""
        funds_html += "<div class='keep'>" + _table(f"{r['fund']}, quarter to {r['quarter']} (filed {r['filed']}), ${r['total_bn']:.1f}bn in {r['n']} positions{_stale}",
                             ["Item", "Detail"],
                             [("Top holdings", r["top"]), ("Biggest adds", r["adds"]), ("Biggest cuts", r["cuts"]),
                              ("New positions", r["new"]), ("Exits", r["exits"])]) + "</div>"

# ---- news ----
_news = _nw.demo_news() if ARGS.demo else (_nw.headlines(EV.get("news_feeds") or None) if EV.get("news", True) else [])
news_html = ""
if _news:
    news_html = "<h2>Headlines this week</h2><ul>" + "".join(
        f"<li><span class='small'>{_h.escape(n['source'])}, {_h.escape(n['date'])}.</span> "
        + (f"<a href='{_h.escape(n['url'])}'>{_h.escape(n['title'])}</a>" if n["url"] else _h.escape(n["title"])) + "</li>"
        for n in _news) + "</ul><p class='small'>Headlines link to the original publishers.</p>"

_srcs = ["Yahoo Finance (prices, delayed)", "FRED (Federal Reserve Bank of St. Louis)"]
if _er: _srcs.append("ECB Data Portal (euro area rates)")
if _mac and _mac_src and _mac_src != "FRED": _srcs.append(f"{_mac_src} (calendar)")
if _sec or _fd: _srcs.append("SEC EDGAR" + (" (13F)" if _fd else ""))
if _pol and os.environ.get("QUIVER_API_KEY"): _srcs.append("Quiver Quantitative (Congress trades)")
elif _pol or _house: _srcs.append("US Senate eFD and House Clerk disclosures")
if _news: _srcs.append("public RSS feeds (headlines)")
_src_note = ", ".join(_srcs)
NOTE = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weekly market outlook, week ending {ASOF.date()}</title>
<style>
:root {{ color-scheme: light; --bg:#fcfcfb; --ink:#0b0b0b; --muted:#52514e; --line:#e6e5e1; --accent:#2a78d6; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; }}
main {{ max-width:780px; margin:0 auto; padding:32px 16px 48px; }}
h1 {{ font-size:28px; margin:0 0 4px; }} h2 {{ font-size:20px; margin:36px 0 8px; border-top:1px solid var(--line); padding-top:20px; }}
h3 {{ font-size:15px; margin:18px 0 2px; color:var(--accent); text-transform:uppercase; letter-spacing:.04em; }}
.sub {{ color:var(--muted); margin:0 0 8px; }} p {{ margin:4px 0 8px; }}
img {{ width:100%; height:auto; margin:12px 0; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; margin:12px 0; font-variant-numeric:tabular-nums; }}
caption {{ text-align:left; font-weight:600; padding:4px 0; }}
th, td {{ padding:6px 8px; border-bottom:1px solid var(--line); text-align:right; }}
th:first-child, thead th:first-child {{ text-align:left; }} thead th {{ color:var(--muted); font-weight:500; }}
tbody th {{ font-weight:400; }}
.small {{ font-size:12px; color:var(--muted); }}
@media print {{
  @page {{ size:A4; margin:14mm 12mm; }}
  body {{ font-size:12px; background:#fff; }} main {{ padding:0; max-width:none; }}
  h2 {{ font-size:16px; margin:18px 0 6px; padding-top:10px; break-after:avoid; page-break-after:avoid; }}
  h3, caption {{ break-after:avoid; page-break-after:avoid; }}
  table {{ font-size:10.5px; }} thead {{ display:table-header-group; }} tr, img {{ break-inside:avoid; page-break-inside:avoid; }}
  img {{ max-height:118mm; width:auto; max-width:100%; display:block; margin:8px auto; }}
  .keep {{ break-inside:avoid; page-break-inside:avoid; }}
  a {{ color:inherit; text-decoration:none; }}
}}
</style></head><body><main>
<h1>Weekly market outlook</h1>
<p class="sub">Week ending {ASOF.strftime('%d %B %Y')}. {PREP}</p>
<h2>Key takeaways</h2>{take_html}{view_html}{next_html}
<h2>Charts</h2>
{img('equities', 'Equity indices rebased to 100 over six months')}
{img('weekly', 'One-week performance by asset')}
{img('curve', 'US Treasury yield curve at four dates')}
{img('credit', 'US investment grade and high yield credit spreads over one year')}
{europe_html}{events_html}{funds_html}{news_html}
<h2>Data</h2>{mkt_html}{rates_html}
<p class="small">Sources: {_src_note}. {fred_note}
Changes are measured from the last observation on or before the comparison date.</p>
<p class="small"><strong>Important.</strong> This note is generated automatically from public data for information only.
It is not investment advice or an offer to buy or sell any security. Past performance is not a guide to future returns.
Commentary describes recent moves and does not explain their causes. Check the data before sending to clients.</p>
</main></body></html>"""

if ARGS.demo:
    NOTE = NOTE.replace("<h1>Weekly market outlook</h1>", "<h1>Weekly market outlook (DEMO DATA, NOT REAL)</h1>")
outdir = Path(ARGS.out); outdir.mkdir(parents=True, exist_ok=True)
stem = f"weekly_outlook_{ASOF.date()}" + ("_DEMO" if ARGS.demo else "")
fname = outdir / f"{stem}.html"
fname.write_text(NOTE, encoding="utf-8")
print("Saved", fname, f"({len(NOTE) / 1e6:.1f} MB)")

PDF_SCRIPT = r"""
import sys
from playwright.sync_api import sync_playwright
src, dst = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(src)
    pg.pdf(path=dst, format="A4", print_background=True,
           margin={"top": "15mm", "bottom": "15mm", "left": "12mm", "right": "12mm"})
    b.close()
"""
pdf_path = None
if ARGS.pdf:
    import subprocess
    _r = subprocess.run([sys.executable, "-c", PDF_SCRIPT, fname.resolve().as_uri(), str(outdir / f"{stem}.pdf")],
                        capture_output=True, text=True)
    if _r.returncode == 0:
        pdf_path = outdir / f"{stem}.pdf"
        print("Saved", pdf_path)
    else:
        warn("PDF failed (pip install playwright && python -m playwright install --with-deps chromium): "
             + (_r.stderr.strip().splitlines()[-1] if _r.stderr.strip() else "unknown error"))

# ---- deliver ----
SUMMARY = "\n\n".join(f"{h}: {t}" for h, t in takeaways)
if ARGS.send:
    _nt.deliver(f"Weekly market outlook, week ending {ASOF.strftime('%d %B %Y')}",
                SUMMARY + "\n\nFull note attached. Not investment advice.", pdf_path or fname)


# ---- automatic checks ----
print("\n===== CHECKS =====")
_checks = {
    "4 charts embedded":            NOTE.count("data:image/png;base64") >= 4,
    "Real data (not demo)":         not ARGS.demo,
    "Euro area rates (ECB)":        "Euro area rates" in NOTE,
    "Macro calendar":               "Key macro releases" in NOTE,
    "Earnings (week ahead)":        "Earnings from the watchlist" in NOTE,
    "SEC filings":                  "SEC filings, watchlist" in NOTE,
    "Congress trades (Senate)":     "US Senate trades" in NOTE,
    "Congress reports (House)":     "US House trade reports" in NOTE,
    "Headlines (RSS)":              "Headlines this week" in NOTE,
    "PDF built":                    (not MAKE_PDF) or bool(pdf_path),
    "Big funds (13F)":              "Big funds: latest 13F" in NOTE,
}
for _k, _v in _checks.items():
    print(("PASS " if _v else "MISS ") + _k)
print("A MISS can be normal (e.g. no earnings or no Congress filings this week).")
print("Look at the [warn] lines above it: an error there is a real failure.")

# ---- preview and download (Colab) ----
try:
    import IPython
    from google.colab import files as _files
    IPython.display.display(IPython.display.HTML(NOTE))
    _files.download(str(pdf_path or fname))
except ImportError:
    pass
