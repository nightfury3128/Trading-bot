import re
import urllib.request
from html.parser import HTMLParser

import pandas as pd
import yfinance as yf

from config import BULK_CHUNK, SP500_WIKI_URL
from utils.logger import log

# Stable machine-readable mirror of the S&P 500 constituents list.
SP500_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"


class _ConstituentsTableParser(HTMLParser):
    """Extract first-column (symbol) text from the Wikipedia constituents table."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.cell_text = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table" and dict(attrs).get("id") == "constituents":
            self.in_table = True
        elif self.in_table and tag == "td":
            self.in_cell = True
            self.cell_text = []

    def handle_endtag(self, tag):
        if tag == "table" and self.in_table:
            self.in_table = False
        elif self.in_table and tag == "td" and self.in_cell:
            self.in_cell = False
            self.row.append("".join(self.cell_text).strip())
        elif self.in_table and tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []

    def handle_data(self, data):
        if self.in_cell:
            self.cell_text.append(data)


def _clean_tickers(symbols) -> list[str]:
    out = {str(s).strip().upper().replace(".", "-") for s in symbols if str(s).strip()}
    # Yahoo tickers: 1-6 chars, letters/digits/hyphen only (drops header junk like "Symbol")
    out = {s for s in out if re.fullmatch(r"[A-Z][A-Z0-9\-]{0,5}", s) and s != "SYMBOL"}
    return sorted(out)


def _fetch_sp500_from_csv() -> list[str]:
    df = pd.read_csv(SP500_CSV_URL)
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    return _clean_tickers(df[col].tolist())


def _fetch_sp500_from_wikipedia() -> list[str]:
    req = urllib.request.Request(SP500_WIKI_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _ConstituentsTableParser()
    parser.feed(html)
    return _clean_tickers(row[0] for row in parser.rows if row)


def fetch_sp500_tickers() -> list[str]:
    log.info("Fetching S&P 500 tickers...")
    best: list[str] = []
    for source, fn in (("csv", _fetch_sp500_from_csv), ("wikipedia", _fetch_sp500_from_wikipedia)):
        try:
            tickers = fn()
            log.info("S&P 500 tickers fetched (%s): %d tickers", source, len(tickers))
            if len(tickers) >= 400:  # sanity check: index has ~500 members
                return tickers
            log.warning("Only %d tickers from %s source, trying next source...", len(tickers), source)
            if len(tickers) > len(best):
                best = tickers
        except Exception as e:
            log.warning("Failed to fetch S&P 500 tickers from %s: %s", source, e)
    if not best:
        log.error("All S&P 500 ticker sources failed.")
    return best


def fetch_nifty500_tickers() -> list[str]:
    log.info("Fetching Nifty 500 tickers...")
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        # Nifty tickers usually need .NS suffix for yfinance
        tickers = [f"{s}.NS" for s in df["Symbol"].tolist()]
        return sorted(list(set(tickers)))
    except Exception as e:
        log.error("Failed to fetch Nifty 500: %s", e)
        return []


def split_bulk_ohlcv(raw: pd.DataFrame, tickers: list) -> dict[str, pd.DataFrame]:
    out = {}
    if raw is None or raw.empty:
        return out

    # Check if we have a MultiIndex or a single Ticker result
    if not isinstance(raw.columns, pd.MultiIndex):
        # Single ticker case
        if len(tickers) == 1:
            out[tickers[0]] = raw.copy().dropna(how="all")
        return out

    # yfinance MultiIndex order is (ticker, field) with group_by="ticker",
    # but be defensive in case a version returns (field, ticker).
    ticker_level = 0 if any(t in raw.columns.levels[0] for t in tickers) else 1
    try:
        for t in tickers:
            if t in raw.columns.levels[ticker_level]:
                sub = raw.xs(t, axis=1, level=ticker_level).dropna(how="all")
                if not sub.empty:
                    out[t] = sub
    except (KeyError, AttributeError, TypeError) as e:
        log.debug("Split failed for some tickers: %s", e)

    return out


def bulk_download_by_ticker(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    result = {}
    if not tickers:
        log.warning("bulk_download_by_ticker called with no tickers (period=%s)", period)
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
                timeout=20,
            )
            chunk_result = split_bulk_ohlcv(raw, chunk)
            if not chunk_result:
                log.warning(
                    "Bulk download returned no data for chunk %d-%d (period=%s, raw_empty=%s)",
                    i, i + len(chunk), period, raw is None or raw.empty,
                )
            result.update(chunk_result)
        except Exception as e:
            log.warning("Bulk download failed for chunk: %s", e)
    log.info("Bulk download (period=%s): %d/%d tickers have data", period, len(result), len(tickers))
    return result
