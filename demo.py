"""Synthetic data so the pipeline can be tested offline. Never use in a real note."""
import numpy as np, pandas as pd

def make_demo(tickers, fred_ids, start, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, pd.Timestamp.today().normalize())
    prices = pd.DataFrame({k: 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(idx))))
                           for k in tickers}, index=idx)
    base = {"DGS3MO": 4.3, "DGS2": 3.9, "DGS5": 3.9, "DGS10": 4.2, "DGS30": 4.5,
            "BAMLC0A0CM": 0.9, "BAMLH0A0HYM2": 3.4, "DFF": 4.1, "T10YIE": 2.3, "VIXCLS": 18.0}
    fred = {sid: pd.Series(base[sid] + np.cumsum(rng.normal(0, 0.02, len(idx))), index=idx)
            for sid in fred_ids}
    return prices, fred
