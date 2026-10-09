"""Big-fund positioning from SEC 13F-HR filings (free, no key, needs a User-Agent with contact).

For each fund CIK: the two latest 13F-HR filings, top holdings, biggest adds and cuts in dollars,
new positions and exits. 13F covers US-listed long positions only, at quarter end,
filed up to 45 days later. Never raises: a failed fund is skipped with a warning.
"""
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


def _warn(msg):
    print(f"[warn] {msg}", file=sys.stderr)


def _get(url, ua, as_json=True):
    time.sleep(0.15)                      # SEC fair-access limit is 10 requests per second
    r = requests.get(url, headers={"User-Agent": ua}, timeout=30)
    r.raise_for_status()
    return r.json() if as_json else r.text


def _holdings(cik, acc, ua):
    """{cusip: (issuer, value_usd, shares)} for one filing, options excluded."""
    folder = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
    items = _get(folder + "/index.json", ua)["directory"]["item"]
    xmls = [i["name"] for i in items if i["name"].lower().endswith(".xml") and "primary_doc" not in i["name"].lower()]
    if not xmls:
        raise ValueError("no information table in filing")
    root = ET.fromstring(_get(f"{folder}/{xmls[0]}", ua, as_json=False))
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
        _warn("sec_user_agent not set, skipping 13F fund positions.")
        return []
    rows = []
    for label, cik in funds.items():
        try:
            sub = _get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", ua)
            rec = sub["filings"]["recent"]
            f13 = [(acc, fd, rd) for f, acc, fd, rd in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec["reportDate"])
                   if f == "13F-HR"][:2]
            if not f13:
                _warn(f"13F {label}: no 13F-HR filings found")
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
            _warn(f"13F {label}: {ex}")
    if rows:
        latest = max(r["quarter"] for r in rows)
        for r in rows:
            r["stale"] = r["quarter"] < latest
    rows.sort(key=lambda r: (r["stale"], -r["total_bn"]))
    return rows


def demo_funds():
    return [{"fund": "DEMO Capital", "quarter": "2026-06-30", "filed": "2026-08-14", "total_bn": 12.3, "n": 40,
             "top": "Demo A 20%, Demo B 15%", "adds": "Demo C +40%", "cuts": "Demo D -30%", "new": "Demo E", "exits": "Demo F"}]
