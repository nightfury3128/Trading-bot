import re
import urllib.request
import yfinance as yf
import pandas as pd
from config import SP500_WIKI_URL, BULK_CHUNK
from utils.logger import log


def fetch_sp500_tickers() -> list[str]:
    log.info("Fetching S&P 500 tickers...")
    req = urllib.request.Request(SP500_WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    start = html.find('id="constituents"')
    end = html.find("</table>", start)
    blob = html[start:end]
    raw = re.findall(r"<tr>\s*<td>\s*<a[^>]*>([A-Za-z0-9.\-]+)</a>", blob)
    return sorted(list(set(s.strip().upper().replace(".", "-") for s in raw)))


def split_bulk_ohlcv(raw: pd.DataFrame, tickers: list) -> dict[str, pd.DataFrame]:
    out = {}
    if raw is None or raw.empty:
        return out
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(tickers) == 1:
            out[tickers[0]] = raw.dropna(how="all")
        return out
    level0 = raw.columns.get_level_values(0)
    for t in tickers:
        if t in level0:
            sub = raw[t].dropna(how="all")
            if not sub.empty:
                out[t] = sub
    return out


def bulk_download_by_ticker(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    result = {}
    if not tickers:
        return result
    for i in range(0, len(tickers), BULK_CHUNK):
        chunk = tickers[i : i + BULK_CHUNK]
        try:
            raw = yf.download(
                chunk,
                period=period,
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
            )
            result.update(split_bulk_ohlcv(raw, chunk))
        except Exception as e:
            log.warning("Bulk download failed for chunk: %s", e)
    return result
