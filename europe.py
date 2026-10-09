"""Euro area rates from the ECB Data Portal (free, no key). Never raises: returns [] on failure."""
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
