"""US Congress trade disclosures from the official sources, free and without a key.

Senate: efdsearch.senate.gov. Electronic Periodic Transaction Reports are HTML tables,
so each trade is read (date, senator, ticker, side, size). Paper filings are listed only.
House: disclosures-clerk.house.gov publishes a yearly index of filings and one PDF per
report. Members and filing dates come from the index. Tickers are read from the PDF text
where it has any (scanned PDFs have none).
Disclosures can lag trades by up to 45 days. Never raises: returns [] on failure.
"""
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

UA = {"User-Agent": "Mozilla/5.0 (weekly-market-outlook; research use)"}


def _warn(msg):
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
        _warn(f"Senate disclosures failed: {ex}")
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
            _warn(f"Senate report skipped: {ex}")
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
            _warn(f"House disclosures {yr} failed: {ex}")
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
            _warn("pypdf not installed, House tickers not read (pip install pypdf).")
            return out
        for f in out:
            try:
                pdf = requests.get(f["url"], headers=UA, timeout=30).content
                txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(pdf)).pages)
                tk = sorted(set(re.findall(r"\(([A-Z][A-Z.]{0,5})\)", txt)) - {"SP", "JT", "DC", "ST", "OP", "NA"})
                f["tickers"] = ", ".join(tk[:12]) if tk else "not readable, open PDF"
            except Exception as ex:
                f["tickers"] = "not readable, open PDF"
                _warn(f"House PDF {f['url']}: {ex}")
    return out


def demo_politics():
    return ([{"reported": "2026-10-08", "traded": "2026-09-20", "who": "DEMO Senator", "ticker": "DEMO",
              "side": "Purchase", "size": "$1,001 - $15,000", "url": ""}],
            [{"reported": "2026-10-07", "who": "DEMO Rep (XX01)", "tickers": "DEMO", "url": ""}])
