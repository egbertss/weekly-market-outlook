"""Builds colab/weekly_outlook_colab.py: one cell, no zip, no config file. Run: python build_colab.py"""
import re
from pathlib import Path

HEAD = r'''# =====================================================================
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
'''

TAIL = r'''

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
'''

def body(path, drop_imports=False):
    s = Path(path).read_text(encoding="utf-8")
    s = re.sub(r'^""".*?"""\n', "", s, count=1, flags=re.S)       # module docstring
    return s

events = body("events.py")
europe = body("europe.py")
funds = body("funds.py")
politics = body("politics.py")
news = body("news.py")
notify = body("notify.py")
out = body("outlook.py")

# replace CLI + toml loading with the SETTINGS dict
start = out.index("import argparse")
cfg_end = out.index("_cfg = tomllib.loads")
cfg_end = out.index("\n", cfg_end) + 1
out = (out[:start] + "import io, base64, sys\nfrom pathlib import Path\n"
       "ARGS = types.SimpleNamespace(demo=False, out='reports', pdf=MAKE_PDF, send=SEND, config=None)\n"
       "_cfg = SETTINGS\n" + out[cfg_end:])
out = out.replace("import events as _ev\n", "")
out = out.replace("import europe as _eu\n", "")
out = out.replace("import funds as _fu\n", "")
out = out.replace("import politics as _po\n", "")
out = out.replace("import news as _nw\n", "")
out = out.replace("    import notify as _nt\n", "")

ns_events = ("_ev = types.SimpleNamespace(macro_calendar=macro_calendar, earnings=earnings, "
             "sec_filings=sec_filings, politician_trades=politician_trades, demo_events=demo_events)\n")
ns_europe = "_eu = types.SimpleNamespace(euro_rates=euro_rates, demo_rates=demo_rates)\n"

code = (HEAD
        + "\n# ======================= events.py =======================\n" + events + ns_events
        + "\n# ======================= europe.py =======================\n" + europe + ns_europe
        + "\n# ======================= funds.py ========================\n" + funds.replace("def _warn", "def _fwarn").replace("_warn(", "_fwarn(").replace("def _get(", "def _fget(").replace("_get(", "_fget(")
        + "_fu = types.SimpleNamespace(fund_moves=fund_moves, demo_funds=demo_funds, DEFAULT_FUNDS=DEFAULT_FUNDS)\n"
        + "\n# ======================= politics.py =====================\n" + politics.replace("_warn(", "_pwarn(")
        + "_po = types.SimpleNamespace(senate_trades=senate_trades, house_filings=house_filings, demo_politics=demo_politics)\n"
        + "\n# ======================= news.py =========================\n" + news.replace("_warn(", "_nwarn(")
        + "_nw = types.SimpleNamespace(headlines=headlines, demo_news=demo_news)\n"
        + "\n# ======================= notify.py =======================\n" + notify.replace("_warn(", "_ntwarn(")
        + "_nt = types.SimpleNamespace(deliver=deliver, telegram_chat_ids=telegram_chat_ids)\n"
        + "\n# ======================= outlook.py ======================\n" + out
        + TAIL)
Path("colab").mkdir(exist_ok=True)
Path("colab/weekly_outlook_colab.py").write_text(code, encoding="utf-8")
print("wrote colab/weekly_outlook_colab.py", len(code.splitlines()), "lines")
