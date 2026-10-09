"""Free headlines from public RSS/Atom feeds (no key). Headlines and links only.
Never raises: a failed feed is skipped with a warning."""
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


def _warn(msg):
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
            _warn(f"news feed {src}: {ex}")
    return out


def demo_news():
    return [{"source": "DEMO", "title": "DEMO headline", "url": "", "date": "2026-10-09"}]
