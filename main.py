import logging
import os
import re
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent / ".env")
try:
    from discord import (
        discord_error,
        discord_no_trade,
        discord_portfolio_summary,
        discord_trade_alert,
    )
except Exception:
    discord_error = None
    discord_no_trade = None
    discord_portfolio_summary = None
    discord_trade_alert = None

# ===== CONFIG =====
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Set SUPABASE_URL and SUPABASE_KEY in a .env file (see .env.example) "
        "or export them in the environment."
    )

STOP_LOSS = 0.95
MIN_HOLD_DAYS = 3
MAX_POSITIONS = 5
# Return-regression BUY: keep positive predicted-return names, cap at N candidates
TOP_BUY_PICKS = 3
FUTURE_RETURN_DAYS = 5
MIN_PREDICTED_RETURN = 0.0

SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FILTER_PERIOD = "3mo"
MIN_FILTER_ROWS = 50
MIN_AVG_VOLUME = 1_000_000
TOP_ML_COUNT = 50
BULK_CHUNK = 120
MAX_ML_WORKERS = 16

_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Keep external libraries quiet unless they emit warnings/errors.
for noisy_logger in ("yfinance", "httpx", "httpcore", "hpack", "peewee"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
log = logging.getLogger("trading_bot")

# ===== CONNECT =====
log.debug("Initializing Supabase client (url=%s)", SUPABASE_URL[:32] + "…")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== HELPERS =====
def _t0():
    return time.perf_counter()

def _dt(start):
    return (time.perf_counter() - start) * 1000.0

def days_since(date_str):
    d1 = datetime.strptime(date_str, "%Y-%m-%d")
    d = (datetime.now() - d1).days
    log.debug("days_since(%s) -> %s", date_str, d)
    return d

def log_trade(action, ticker, price, shares):
    log.info(
        "TRADE db insert: action=%s ticker=%s price=%.6f shares=%s",
        action,
        ticker,
        float(price),
        shares,
    )
    if discord_trade_alert is not None:
        try:
            discord_trade_alert(action, ticker, float(price), int(shares))
        except Exception as e:
            log.debug("discord_trade_alert failed: %s", e)
    t_s = _t0()
    res = supabase.table("trades").insert({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "action": action,
        "ticker": ticker,
        "price": float(price),
        "shares": shares
    }).execute()
    log.debug("log_trade execute took %.2f ms", _dt(t_s))
    if not (res.data or []):
        log.error("trades insert returned empty data")
        raise RuntimeError(
            "trades insert returned no rows — check RLS INSERT on `trades` and column types."
        )
    log.debug("trades insert response rows=%s", len(res.data or []))

def get_account():
    t_s = _t0()
    res = supabase.table("account").select("*").eq("id", 1).execute()
    log.debug("get_account query %.2f ms", _dt(t_s))
    rows = res.data or []
    if not rows:
        raise RuntimeError(
            "account query returned no rows for id=1. "
            "Add a row in Supabase (table `account`, id=1 with cash), "
            "or fix Row Level Security so your key can SELECT that row."
        )
    log.info("get_account id=1 cash=%s keys=%s", rows[0].get("cash"), list(rows[0].keys()))
    return rows[0]

def update_cash(new_cash):
    log.info("update_cash new_cash=%.6f", float(new_cash))
    t_s = _t0()
    res = (
        supabase.table("account")
        .update({"cash": float(new_cash)})
        .eq("id", 1)
        .execute()
    )
    log.debug("update_cash execute %.2f ms", _dt(t_s))
    if not (res.data or []):
        raise RuntimeError(
            "account update changed 0 rows — check id=1 exists and RLS allows UPDATE on `account`."
        )
    log.debug("update_cash returned %s row(s)", len(res.data or []))

def get_portfolio():
    t_s = _t0()
    data = supabase.table("portfolio").select("*").execute().data or []
    log.debug("get_portfolio %.2f ms count=%s", _dt(t_s), len(data))
    if data:
        log.debug("portfolio tickers: %s", [p.get("ticker") for p in data])
    return data

def add_position(ticker, shares, price):
    log.info("add_position ticker=%s shares=%s price=%.6f", ticker, shares, float(price))
    t_s = _t0()
    res = supabase.table("portfolio").insert({
        "ticker": ticker,
        "shares": shares,
        "buy_price": float(price),
        "buy_date": datetime.now().strftime("%Y-%m-%d")
    }).execute()
    log.debug("add_position execute %.2f ms", _dt(t_s))
    if not (res.data or []):
        log.error("portfolio insert empty for ticker=%s", ticker)
        raise RuntimeError(
            "portfolio insert returned no rows — check RLS INSERT on `portfolio`."
        )

def remove_position(ticker):
    log.info("remove_position ticker=%s", ticker)
    t_s = _t0()
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()
    log.debug("remove_position %.2f ms", _dt(t_s))

# ===== UNIVERSE (S&P 500 from Wikipedia) =====
def fetch_sp500_tickers():
    """Scrape S&P 500 tickers from Wikipedia; symbols normalized for Yahoo (e.g. BRK.B → BRK-B)."""
    log.info("fetch_sp500_tickers: GET %s", SP500_WIKI_URL)
    t_s = _t0()
    req = urllib.request.Request(
        SP500_WIKI_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; research/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    log.debug("Wikipedia HTML length=%s chars, fetch+decode %.2f ms", len(html), _dt(t_s))
    start = html.find('id="constituents"')
    if start == -1:
        raise RuntimeError('Could not find id="constituents" table on Wikipedia page.')
    end = html.find("</table>", start)
    blob = html[start:end]
    raw = re.findall(
        r"<tr>\s*<td>\s*<a[^>]*>([A-Za-z0-9.\-]+)</a>",
        blob,
    )
    seen: set[str] = set()
    out: list[str] = []
    for s in raw:
        sym = str(s).strip().upper().replace(".", "-")
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    if len(out) < 400:
        raise RuntimeError(f"Unexpected symbol count ({len(out)}); Wikipedia layout may have changed.")
    log.info("fetch_sp500_tickers: parsed %s unique symbols (first=%s last=%s)", len(out), out[0], out[-1])
    log.debug("SP500 sample head: %s", out[:10])
    return out

def split_bulk_ohlcv(raw: pd.DataFrame, tickers: list) -> dict[str, pd.DataFrame]:
    """Split a multi-ticker yfinance download into per-ticker OHLCV frames."""
    out: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        log.debug("split_bulk_ohlcv: empty raw for tickers chunk len=%s", len(tickers))
        return out
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(tickers) == 1 and "Close" in raw.columns:
            sub = raw.dropna(how="all")
            if not sub.empty:
                out[tickers[0]] = sub
        return out
    level0 = raw.columns.get_level_values(0)
    for t in tickers:
        try:
            if t in level0:
                sub = raw[t].dropna(how="all")
                if not sub.empty and "Close" in sub.columns:
                    out[t] = sub
        except Exception:
            continue
    missing = [x for x in tickers if x not in out]
    log.debug(
        "split_bulk_ohlcv: extracted %s/%s tickers; missing_sample=%s",
        len(out),
        len(tickers),
        missing[:15],
    )
    return out

def bulk_download_by_ticker(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    """Chunked bulk download; returns {ticker: ohlcv DataFrame}."""
    result: dict[str, pd.DataFrame] = {}
    if not tickers:
        log.warning("bulk_download_by_ticker: empty ticker list period=%s", period)
        return result
    log.info(
        "bulk_download_by_ticker: %s tickers period=%s chunk=%s",
        len(tickers),
        period,
        BULK_CHUNK,
    )
    t_all = _t0()
    n_chunks = (len(tickers) + BULK_CHUNK - 1) // BULK_CHUNK
    for ci, i in enumerate(range(0, len(tickers), BULK_CHUNK)):
        chunk = tickers[i : i + BULK_CHUNK]
        t_ch = _t0()
        log.debug(
            "yfinance chunk %s/%s index=%s size=%s sample=%s",
            ci + 1,
            n_chunks,
            i,
            len(chunk),
            chunk[:5],
        )
        try:
            raw = yf.download(
                chunk,
                period=period,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as e:
            log.exception("bulk download failed chunk index=%s: %s", i, e)
            continue
        log.debug("yfinance chunk %s download %.2f ms shape=%s", ci + 1, _dt(t_ch), getattr(raw, "shape", None))
        before = len(result)
        result.update(split_bulk_ohlcv(raw, chunk))
        log.debug("chunk %s added %s tickers (total keys=%s)", ci + 1, len(result) - before, len(result))
    log.info(
        "bulk_download_by_ticker done: period=%s collected=%s/requested=%s in %.2f ms",
        period,
        len(result),
        len(tickers),
        _dt(t_all),
    )
    return result

def momentum_and_filter_stats(ohlcv: pd.DataFrame):
    """Return 20-day momentum if row count, volume, and momentum pass; else None."""
    try:
        if ohlcv is None or ohlcv.empty:
            return None
        if "Close" not in ohlcv.columns or "Volume" not in ohlcv.columns:
            return None
        sub = ohlcv.dropna(subset=["Close", "Volume"])
        if len(sub) < MIN_FILTER_ROWS:
            return None
        avg_vol = float(sub["Volume"].mean())
        if avg_vol <= MIN_AVG_VOLUME:
            return None
        close = sub["Close"].astype(float)
        if len(close) < 21:
            return None
        mom = float(close.iloc[-1] / close.iloc[-21] - 1.0)
        if mom <= 0:
            return None
        return mom
    except Exception:
        return None

def momentum_filter_detail(ticker: str, ohlcv: pd.DataFrame) -> tuple[float | None, str]:
    """Same gates as momentum_and_filter_stats, but return a reason string for logging."""
    try:
        if ohlcv is None or ohlcv.empty:
            return None, "empty_ohlcv"
        if "Close" not in ohlcv.columns:
            return None, "no_close"
        if "Volume" not in ohlcv.columns:
            return None, "no_volume"
        sub = ohlcv.dropna(subset=["Close", "Volume"])
        n = len(sub)
        if n < MIN_FILTER_ROWS:
            return None, f"rows_{n}<{MIN_FILTER_ROWS}"
        avg_vol = float(sub["Volume"].mean())
        if avg_vol <= MIN_AVG_VOLUME:
            return None, f"avg_volume_{avg_vol:.0f}<={MIN_AVG_VOLUME}"
        close = sub["Close"].astype(float)
        if len(close) < 21:
            return None, f"close_len_{len(close)}<21"
        mom = float(close.iloc[-1] / close.iloc[-21] - 1.0)
        if mom <= 0:
            return None, f"non_positive_momentum_{mom:.6f}"
        return mom, f"ok_mom={mom:.6f}"
    except Exception as e:
        return None, f"exception:{type(e).__name__}:{e}"

def filter_universe_ranked(ohlcv_map: dict[str, pd.DataFrame]) -> list[tuple[str, float]]:
    ranked: list[tuple[str, float]] = []
    reason_counts: dict[str, int] = {}
    t_s = _t0()
    for t, df in ohlcv_map.items():
        try:
            mom, reason = momentum_filter_detail(t, df)
            if mom is not None:
                ranked.append((t, mom))
                log.debug("FILTER pass %s %s", t, reason)
            else:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                log.debug("FILTER reject %s: %s", t, reason)
        except Exception as e:
            log.debug("FILTER reject %s: outer_exception %s", t, e)
            reason_counts["outer_exception"] = reason_counts.get("outer_exception", 0) + 1
    ranked.sort(key=lambda x: -x[1])
    log.info(
        "filter_universe_ranked: pass=%s reject=%s in %.2f ms",
        len(ranked),
        len(ohlcv_map) - len(ranked),
        _dt(t_s),
    )
    log.debug("filter rejection histogram: %s", dict(sorted(reason_counts.items(), key=lambda x: -x[1])[:25]))
    if ranked:
        log.info("top 10 momentum: %s", [(a, f"{b:.4f}") for a, b in ranked[:10]])
    return ranked

# ===== DATA / ML =====
def prepare_ml_dataframe(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Feature frame for train_and_score (matches original get_data logic)."""
    try:
        df = ohlcv.copy()
        if df.empty or "Close" not in df.columns:
            log.debug("prepare_ml_dataframe: empty or no Close, shape=%s", getattr(df, "shape", None))
            return pd.DataFrame()
        rows_in = len(df)
        df["returns"] = df["Close"].pct_change()
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()
        df["volatility"] = df["returns"].rolling(10).std()
        df["target"] = (df["Close"].shift(-FUTURE_RETURN_DAYS) - df["Close"]) / df["Close"]
        out = df.dropna()
        log.debug(
            "prepare_ml_dataframe: rows %s -> %s (after features)",
            rows_in,
            len(out),
        )
        return out
    except Exception as e:
        log.debug("prepare_ml_dataframe failed: %s", e)
        return pd.DataFrame()

def get_data(ticker):
    """Per-ticker 1y download + feature prep (portfolio extras / fallback)."""
    log.debug("get_data: start ticker=%s", ticker)
    t_s = _t0()
    raw = yf.download(
        [ticker],
        period="1y",
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if raw.empty or (
        isinstance(raw.columns, pd.MultiIndex)
        and ticker not in raw.columns.get_level_values(0)
    ):
        log.debug("get_data: fallback single-arg download ticker=%s", ticker)
        raw = yf.download(ticker, period="1y", progress=False)
    log.debug("get_data: yfinance done ticker=%s in %.2f ms", ticker, _dt(t_s))
    if isinstance(raw.columns, pd.MultiIndex) and ticker in raw.columns.get_level_values(0):
        out = prepare_ml_dataframe(raw[ticker])
    else:
        out = prepare_ml_dataframe(raw)
    log.debug("get_data: done ticker=%s ml_rows=%s", ticker, len(out))
    return out

def train_and_score(df):
    t_s = _t0()
    X = df[["returns", "MA20", "MA50", "volatility"]]
    y = df["target"]
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    pred_return = float(model.predict(X.iloc[-1:])[0])
    log.debug(
        "train_and_score: rows=%s X_shape=%s fit+infer %.2f ms pred_return=%.6f",
        len(df),
        X.shape,
        _dt(t_s),
        pred_return,
    )
    return pred_return

def _score_one_ticker_ml(pair: tuple[str, pd.DataFrame]):
    ticker, ohlcv = pair
    try:
        t_row = len(ohlcv) if ohlcv is not None else 0
        log.debug("_score_one_ticker_ml start %s ohlcv_rows=%s", ticker, t_row)
        ml_df = prepare_ml_dataframe(ohlcv)
        if ml_df.empty:
            return ticker, None, None, ValueError("insufficient rows for ML features")
        pred_return = train_and_score(ml_df)
        if not pd.notna(pred_return):
            return ticker, None, None, ValueError("invalid predicted return")
        price = float(ohlcv["Close"].dropna().iloc[-1])
        log.debug(
            "_score_one_ticker_ml ok %s pred_return=%.6f price=%.6f",
            ticker,
            pred_return,
            price,
        )
        return ticker, pred_return, price, None
    except Exception as e:
        log.debug("_score_one_ticker_ml fail %s: %s", ticker, e)
        return ticker, None, None, e

def run_parallel_ml_scoring(
    ticker_to_ohlcv: dict[str, pd.DataFrame],
) -> tuple[dict, dict, list]:
    scores, prices = {}, {}
    errors = []
    pairs = [(t, ticker_to_ohlcv[t]) for t in ticker_to_ohlcv if t in ticker_to_ohlcv]
    if not pairs:
        log.warning("run_parallel_ml_scoring: no pairs to score")
        return scores, prices, errors
    n_workers = min(MAX_ML_WORKERS, len(pairs), (os.cpu_count() or 4) * 2)
    n_workers = max(1, n_workers)
    log.info(
        "run_parallel_ml_scoring: tickers=%s workers=%s cpu_count=%s",
        len(pairs),
        n_workers,
        os.cpu_count(),
    )
    t_all = _t0()
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futures = [ex.submit(_score_one_ticker_ml, p) for p in pairs]
        for fut in as_completed(futures):
            try:
                ticker, pred_return, price, err = fut.result()
            except Exception as e:
                log.exception("ML future crashed: %s", e)
                errors.append(("?", e))
                continue
            if err is not None:
                errors.append((ticker, err))
                log.debug("ML error ticker=%s err=%s", ticker, err)
            elif pred_return is not None and price is not None:
                scores[ticker] = pred_return
                prices[ticker] = price
    log.info(
        "run_parallel_ml_scoring: done scores=%s errors=%s in %.2f ms",
        len(scores),
        len(errors),
        _dt(t_all),
    )
    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        log.info("ML best ticker=%s predicted_return=%.6f", best[0], best[1])
    return scores, prices, errors

def fill_prices_bulk(tickers: list[str], prices: dict[str, float]):
    """Add latest close for tickers missing from prices (one bulk download)."""
    need = [t for t in tickers if t not in prices]
    if not need:
        log.debug("fill_prices_bulk: nothing missing")
        return
    log.info("fill_prices_bulk: fetching %s tickers: %s", len(need), need)
    ohlcv_map = bulk_download_by_ticker(need, "5d")
    for t in need:
        try:
            df = ohlcv_map.get(t)
            if df is not None and not df.empty and "Close" in df.columns:
                px = float(df["Close"].dropna().iloc[-1])
                prices[t] = px
                log.debug("fill_prices_bulk: %s close=%.6f", t, px)
            else:
                log.debug("fill_prices_bulk: no data for %s", t)
        except Exception as e:
            log.debug("fill_prices_bulk: %s failed %s", t, e)
            continue

# ===== MAIN =====
log.info("========== BOT RUN START %s ==========", datetime.now().isoformat())
RUN_T0 = _t0()

account = get_account()
cash = float(account["cash"])
positions = {p["ticker"]: p for p in get_portfolio()}
log.info("startup cash=%.6f positions=%s", cash, list(positions.keys()))

scores = {}
prices = {}
score_errors = []

try:
    sp500 = fetch_sp500_tickers()
except Exception as e:
    log.exception("fetch_sp500 failed")
    raise RuntimeError(f"Failed to load S&P 500 list from Wikipedia: {e!r}") from e

log.info("S&P 500 symbols: %s — bulk filter download period=%s", len(sp500), FILTER_PERIOD)
filter_map = bulk_download_by_ticker(sp500, FILTER_PERIOD)
ranked_momentum = filter_universe_ranked(filter_map)
top_ml_tickers = [t for t, _ in ranked_momentum[:TOP_ML_COUNT]]
log.info(
    "Filter: pass=%s names; ML universe top %s tickers (cap=%s)",
    len(ranked_momentum),
    len(top_ml_tickers),
    TOP_ML_COUNT,
)
log.debug("TOP_ML_TICKERS: %s", top_ml_tickers)

held_for_ml = [t for t in positions if t not in top_ml_tickers]
if held_for_ml:
    log.info(
        "Extra ML for %s portfolio ticker(s) not in top-%s: %s",
        len(held_for_ml),
        TOP_ML_COUNT,
        held_for_ml,
    )

ml_download_list = list(dict.fromkeys(top_ml_tickers + held_for_ml))
log.debug("ml_download_list len=%s", len(ml_download_list))
ohlcv_1y = bulk_download_by_ticker(ml_download_list, "1y")

scores, prices, score_errors = run_parallel_ml_scoring(ohlcv_1y)

for t in held_for_ml:
    if t in scores:
        log.debug("held ticker %s already scored; skip fallback", t)
        continue
    try:
        log.info("held fallback ML download ticker=%s", t)
        ml_df = get_data(t)
        if ml_df.empty:
            raise ValueError("empty ml df")
        pred_return = train_and_score(ml_df)
        if not pd.notna(pred_return):
            raise ValueError("invalid predicted return")
        raw_h = yf.download([t], period="5d", group_by="ticker", progress=False, threads=True)
        if not raw_h.empty and isinstance(raw_h.columns, pd.MultiIndex) and t in raw_h.columns.get_level_values(0):
            px = float(raw_h[t]["Close"].dropna().iloc[-1])
        else:
            px = float(ml_df["Close"].iloc[-1])
        scores[t] = pred_return
        prices[t] = px
        log.info("held fallback OK %s predicted_return=%.6f price=%.6f", t, pred_return, px)
    except Exception as e:
        log.warning("held fallback failed %s: %s", t, e)
        score_errors.append((t, e))

fill_prices_bulk(list(positions.keys()), prices)
log.debug("scores keys=%s prices keys=%s", list(scores.keys()), list(prices.keys()))

if score_errors and not scores:
    names = ", ".join(str(t) for t, _ in score_errors[:3])
    log.error("fatal: no scores, errors sample=%s", score_errors[:5])
    raise RuntimeError(
        f"No tickers scored (all failed). First errors for: {names}. — {score_errors[0]!r}"
    )
if score_errors:
    for t, err in score_errors[:20]:
        log.warning("scoring skip ticker=%s err=%r", t, err)
    if len(score_errors) > 20:
        log.warning("… plus %s more scoring warnings", len(score_errors) - 20)

ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
log.info("ranked (ml) count=%s", len(ranked))
log.debug("ranked full: %s", ranked)

ranked_with_return = [
    (ticker, float(pred_return))
    for ticker, pred_return in ranked
    if pd.notna(pred_return)
]
top_picks = [(t, r) for t, r in ranked_with_return if r > MIN_PREDICTED_RETURN][:TOP_BUY_PICKS]
print("Top 10 ranked stocks (predicted return):", [(t, float(r)) for t, r in ranked_with_return[:10]])
print("Selected top_picks:", top_picks)

today = datetime.now().strftime("%Y-%m-%d")
log.info("trade date today=%s", today)

# ===== SELL =====
log.info("---------- SELL phase ----------")
for ticker, pos in list(positions.items()):
    price = prices.get(ticker)
    if price is None:
        log.warning("SELL skip %s: no price in quotes", ticker)
        continue

    hold_days = days_since(pos["buy_date"])
    log.debug(
        "position %s shares=%s buy_price=%s price=%s hold_days=%s stop_level=%.6f",
        ticker,
        pos["shares"],
        pos["buy_price"],
        price,
        hold_days,
        float(pos["buy_price"]) * STOP_LOSS,
    )

    # STOP LOSS
    if price < pos["buy_price"] * STOP_LOSS:
        cash += pos["shares"] * price
        log.info(
            "STOP_LOSS %s proceeds=%.6f (shares=%s @ %.6f)",
            ticker,
            pos["shares"] * price,
            pos["shares"],
            price,
        )
        log_trade("STOP_LOSS", ticker, price, pos["shares"])
        remove_position(ticker)
        continue

    # MODEL SELL (no day trading)
    sc = scores.get(ticker)
    if ticker in scores and sc < 0.4 and hold_days >= MIN_HOLD_DAYS:
        cash += pos["shares"] * price
        log.info(
            "SELL %s model score=%.6f hold_days=%s proceeds=%.6f",
            ticker,
            sc,
            hold_days,
            pos["shares"] * price,
        )
        log_trade("SELL", ticker, price, pos["shares"])
        remove_position(ticker)
        continue
    log.debug("SELL no action %s (score=%s hold_days=%s)", ticker, sc, hold_days)

# ===== BUY =====
available_slots = MAX_POSITIONS - len(get_portfolio())
skipped_insufficient_cash = []
planned_allocations = []
log.info(
    "---------- BUY phase max_positions=%s open_after_sells=%s available_slots=%s cash=%.6f "
    "return_top_n=%s min_predicted_return=%.6f top_picks=%s ----------",
    MAX_POSITIONS,
    len(get_portfolio()),
    available_slots,
    cash,
    TOP_BUY_PICKS,
    MIN_PREDICTED_RETURN,
    top_picks,
)

total_return = sum(pred_return for _, pred_return in top_picks)
if total_return <= 0:
    log.warning("BUY skip: total_return <= 0 (top_picks=%s)", top_picks)
    if discord_no_trade is not None:
        try:
            discord_no_trade()
        except Exception as e:
            log.debug("discord_no_trade failed: %s", e)
else:
    starting_cash_for_alloc = cash
    for ticker, pred_return in top_picks:
        if available_slots <= 0:
            log.debug("BUY break: no slots")
            break

        if ticker in positions:
            log.debug("BUY skip %s already in initial positions dict", ticker)
            continue

        price = prices.get(ticker)
        if price is None:
            log.info("BUY skip %s missing latest price", ticker)
            continue
        weight = pred_return / total_return
        allocation = starting_cash_for_alloc * weight
        shares = int(allocation // price)
        print(
            "Allocator:",
            ticker,
            "pred_return=",
            round(pred_return, 6),
            "weight=",
            round(weight, 6),
            "allocation=",
            round(allocation, 2),
            "shares=",
            shares,
        )

        if shares <= 0:
            detail = (
                f"allocation ${allocation:.2f} < ${price:.2f}/share "
                f"(cash_now ${cash:.2f}, weight {weight:.4f})"
            )
            skipped_insufficient_cash.append((ticker, detail))
            log.info("BUY skip %s zero shares: %s", ticker, detail)
            continue

        cost = shares * price
        if cost > cash:
            # Extra guard against any float edge cases in allocation math.
            detail = (
                f"cost ${cost:.2f} > cash ${cash:.2f} "
                f"(alloc ${allocation:.2f}, shares={shares}, price=${price:.2f})"
            )
            skipped_insufficient_cash.append((ticker, detail))
            log.info("BUY skip %s insufficient cash: %s", ticker, detail)
            continue

        cash -= cost
        planned_allocations.append((ticker, allocation, cost))
        log.info(
            "BUY %s pred_return=%.6f weight=%.6f allocation=%.2f shares=%s price=%.6f cost=%.6f cash_after=%.6f",
            ticker,
            pred_return,
            weight,
            allocation,
            shares,
            price,
            cost,
            cash,
        )
        add_position(ticker, shares, price)
        log_trade("BUY", ticker, price, shares)

        available_slots -= 1

if planned_allocations:
    total_planned = sum(a for _, a, _ in planned_allocations)
    total_invested = sum(c for _, _, c in planned_allocations)
else:
    total_planned = 0.0
    total_invested = 0.0
print("Total allocated capital (planned):", round(total_planned, 2))
print("Total allocated capital (invested):", round(total_invested, 2))

# ===== UPDATE CASH =====
log.info("---------- UPDATE CASH final_cash=%.6f ----------", cash)
update_cash(cash)

# ===== PERFORMANCE =====
total_value = cash
for ticker, pos in positions.items():
    if ticker in prices:
        total_value += pos["shares"] * prices[ticker]

invested_amount = max(0.0, float(total_value - cash))

prev_total_value = None
first_total_value = None
try:
    prev_rows = (
        supabase.table("performance")
        .select("date,total_value")
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    if prev_rows:
        prev_total_value = float(prev_rows[0].get("total_value") or 0.0)
except Exception:
    prev_total_value = None

try:
    first_rows = (
        supabase.table("performance")
        .select("date,total_value")
        .order("date", desc=False)
        .limit(1)
        .execute()
        .data
        or []
    )
    if first_rows:
        first_total_value = float(first_rows[0].get("total_value") or 0.0)
except Exception:
    first_total_value = None

log.info(
    "performance snapshot cash=%.6f legacy_positions_notional=%.6f total_value=%.6f",
    cash,
    total_value - cash,
    total_value,
)

t_perf = _t0()
perf_res = supabase.table("performance").insert({
    "date": today,
    "total_value": float(total_value),
}).execute()
log.debug("performance insert %.2f ms", _dt(t_perf))
if not (perf_res.data or []):
    log.error("performance insert empty")
    raise RuntimeError(
        "performance insert returned no rows — check RLS INSERT on `performance` and unique constraints (e.g. duplicate `date`)."
    )
perf_row = perf_res.data[0]
perf_id = perf_row.get("id", "?")

log.info("Total Value: $%.2f", total_value)
log.info("Supabase performance row id=%s perf_row_keys=%s", perf_id, list(perf_row.keys()))

profit_loss_day = (total_value - prev_total_value) if prev_total_value is not None else None
profit_loss_since_start = (total_value - first_total_value) if first_total_value is not None else None
if discord_portfolio_summary is not None:
    try:
        discord_portfolio_summary(
            run_date=today,
            cash=float(cash),
            invested=float(invested_amount),
            total_value=float(total_value),
            profit_loss_since_start=profit_loss_since_start,
            profit_loss_day=profit_loss_day,
            top_picks=top_picks,
            positions=positions,
            prices=prices,
        )
    except Exception as e:
        log.debug("discord_portfolio_summary failed: %s", e)

if ranked:
    top_t, top_p = ranked[0]
    log.info(
        "Highest ML predicted return: %s = %.6f (positive-return filter, up to %s picks)",
        top_t,
        float(top_p),
        TOP_BUY_PICKS,
    )

if skipped_insufficient_cash:
    log.warning("Buys skipped — insufficient cash (showing up to 10):")
    for t, detail in skipped_insufficient_cash[:10]:
        log.warning("  %s: %s", t, detail)

log.info(
    "========== BOT RUN END wall_ms=%.2f ==========",
    _dt(RUN_T0),
)
