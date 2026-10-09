"""Weekly market outlook generator.

Pulls FRED and Yahoo Finance data, writes a one-file HTML client note
(optionally a PDF). Settings live in config.toml.

Usage:
    python outlook.py                 # live data
    python outlook.py --pdf           # also export PDF (needs playwright)
    python outlook.py --demo          # synthetic data, for testing only
"""
import argparse, io, base64, sys, tomllib
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config.toml")
ap.add_argument("--out", default="reports")
ap.add_argument("--pdf", action="store_true")
ap.add_argument("--send", action="store_true", help="email/Telegram the note (settings from env vars)")
ap.add_argument("--demo", action="store_true", help="synthetic data, NOT for clients")
ARGS, _ = ap.parse_known_args()

_cfg = tomllib.loads(Path(ARGS.config).read_text(encoding="utf-8"))
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
import events as _ev
import politics as _po
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
import europe as _eu
_er = _eu.demo_rates() if ARGS.demo else (_eu.euro_rates() if EV.get("europe_rates", True) else [])
def _f(x, d=0, suf=""):
    return "" if x is None else f"{x:+.{d}f}{suf}"
europe_html = ""
if _er:
    _rows = [(r["name"], r["asof"], f"{r['level']:.0f} bp" if r.get("bp") else f"{r['level']:.2f}%",
              _f(r["w"], 0, " bp"), _f(r["m"], 0, " bp")) for r in _er]
    europe_html = "<h2>Euro area rates</h2>" + _table("ECB Data Portal", ["Series", "As of", "Level", "1W chg", "1M chg"], _rows)

# ---- big funds (13F) ----
import funds as _fu
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
import news as _nw
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
    import notify as _nt
    _nt.deliver(f"Weekly market outlook, week ending {ASOF.strftime('%d %B %Y')}",
                SUMMARY + "\n\nFull note attached. Not investment advice.", pdf_path or fname)
