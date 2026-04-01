import logging
import os
import re
import time
import urllib.request
import warnings
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client

_dotenv_path = Path(__file__).resolve().parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

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

# Silence noisy ResourceWarnings (common with yfinance/threads)
warnings.filterwarnings("ignore", category=ResourceWarning)

# ===== CONFIG =====
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or "").strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY.")

STOP_LOSS = 0.95
TAKE_PROFIT = 1.10
MIN_HOLD_DAYS = 3       # Rule 11: prefer 3
MIN_REBUY_DAYS = 5      # Rule 6
MAX_POSITIONS = 5
TOP_BUY_PICKS = 5       # Rule 7: top 3-5
FUTURE_RETURN_DAYS = 5  # Rule 2
MIN_PREDICTED_RETURN = 0.0 # Rule 7

# Transaction Costs (Rule 9)
COST_BUY = 1.001
COST_SELL = 0.999

SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FILTER_PERIOD = "6mo"    # Increased to ensure enough data for MA200 SPY and features
MIN_FILTER_ROWS = 100
MIN_AVG_VOLUME = 1_000_000
TOP_ML_COUNT = 50
BULK_CHUNK = 120
MAX_ML_WORKERS = 16

FEATURE_COLUMNS = [
    "returns", "MA20", "MA50", "momentum_5", "momentum_10", 
    "momentum_20", "volatility_10", "volatility_20", 
    "volume_change", "ma_ratio", "price_vs_ma"
]

_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
for noisy_logger in ("yfinance", "httpx", "httpcore", "hpack", "peewee"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
log = logging.getLogger("trading_bot")

# ===== CONNECT =====
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== HELPERS =====
def _t0(): return time.perf_counter()
def _dt(start): return (time.perf_counter() - start) * 1000.0

def days_since(date_str):
    try:
        d1 = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.now() - d1).days
    except:
        return 0

def log_trade(action, ticker, price, shares):
    log.info("TRADE: action=%s ticker=%s price=%.6f shares=%s", action, ticker, float(price), shares)
    if discord_trade_alert:
        try:
            discord_trade_alert(action, ticker, float(price), float(shares))
        except Exception as e:
            log.debug("discord_trade_alert failed: %s", e)
    
    supabase.table("trades").insert({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "action": action,
        "ticker": ticker,
        "price": float(price),
        "shares": float(shares)
    }).execute()

def get_account():
    res = supabase.table("account").select("*").eq("id", 1).execute()
    if not res.data:
        raise RuntimeError("Account id=1 not found.")
    return res.data[0]

def update_cash(new_cash):
    supabase.table("account").update({"cash": float(new_cash)}).eq("id", 1).execute()

def get_portfolio():
    return supabase.table("portfolio").select("*").execute().data or []

def add_position(ticker, shares, price):
    supabase.table("portfolio").insert({
        "ticker": ticker,
        "shares": float(shares),
        "buy_price": float(price),
        "buy_date": datetime.now().strftime("%Y-%m-%d")
    }).execute()

def remove_position(ticker):
    supabase.table("portfolio").delete().eq("ticker", ticker).execute()

def get_recent_sells():
    """Rule 6: Track last sell date per ticker from trades table."""
    try:
        five_days_ago = (datetime.utcnow() - timedelta(days=6)).strftime("%Y-%m-%d")
        res = supabase.table("trades") \
            .select("ticker,date") \
            .filter("action", "in", '("SELL","STOP_LOSS","TAKE_PROFIT")') \
            .gte("date", five_days_ago) \
            .execute()
        return {r["ticker"] for r in (res.data or [])}
    except Exception as e:
        log.warning("get_recent_sells failed: %s", e)
        return set()

def get_market_regime():
    """Rule 3: SPY MA50 vs MA200 filter."""
    try:
        spy = yf.download("SPY", period="2y", progress=False)
        if spy.empty: return True
        spy["MA50"] = spy["Close"].rolling(50).mean()
        spy["MA200"] = spy["Close"].rolling(200).mean()
        ma50 = spy["MA50"].iloc[-1]
        ma200 = spy["MA200"].iloc[-1]
        log.info("Market Regime: SPY MA50=%.2f, MA200=%.2f", ma50, ma200)
        return ma50 >= ma200
    except Exception as e:
        log.warning("Market regime check failed: %s", e)
        return True

# ===== DATA / ML =====
def fetch_sp500_tickers():
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
    if raw is None or raw.empty: return out
    if not isinstance(raw.columns, pd.MultiIndex):
        if len(tickers) == 1: out[tickers[0]] = raw.dropna(how="all")
        return out
    level0 = raw.columns.get_level_values(0)
    for t in tickers:
        if t in level0:
            sub = raw[t].dropna(how="all")
            if not sub.empty: out[t] = sub
    return out

def bulk_download_by_ticker(tickers: list[str], period: str) -> dict[str, pd.DataFrame]:
    result = {}
    if not tickers: return result
    for i in range(0, len(tickers), BULK_CHUNK):
        chunk = tickers[i : i + BULK_CHUNK]
        try:
            raw = yf.download(chunk, period=period, group_by="ticker", progress=False, threads=True)
            result.update(split_bulk_ohlcv(raw, chunk))
        except Exception as e:
            log.warning("Bulk download failed for chunk: %s", e)
    return result

def prepare_ml_dataframe(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Rule 1 & 2: Feature Engineering & Target Improvement."""
    try:
        df = ohlcv.copy()
        if df.empty or "Close" not in df.columns: return pd.DataFrame()
        
        # Core returns
        df["returns"] = df["Close"].pct_change()
        
        # Existing MA
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()
        
        # New Features (Rule 1)
        df["momentum_5"] = df["Close"].pct_change(5)
        df["momentum_10"] = df["Close"].pct_change(10)
        df["momentum_20"] = df["Close"].pct_change(20)
        df["volatility_10"] = df["returns"].rolling(10).std()
        df["volatility_20"] = df["returns"].rolling(20).std()
        if "Volume" in df.columns:
            df["volume_change"] = df["Volume"].pct_change()
        else:
            df["volume_change"] = 0
            
        # Ratios (Rule 1 / Rule 13 safety)
        df["ma_ratio"] = df["MA20"] / df["MA50"].replace(0, np.nan)
        df["price_vs_ma"] = df["Close"] / df["MA20"].replace(0, np.nan)
        
        # Target (Rule 2)
        df["target"] = (df["Close"].shift(-FUTURE_RETURN_DAYS) - df["Close"]) / df["Close"]
        
        out = df.dropna(subset=FEATURE_COLUMNS + ["target"])
        return out
    except Exception as e:
        log.debug("prepare_ml_dataframe error: %s", e)
        return pd.DataFrame()

def train_and_score(df):
    """Rule 1: Update feature list used in model."""
    X = df[FEATURE_COLUMNS]
    y = df["target"]
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    last_row = df.iloc[-1:]
    pred_return = float(model.predict(last_row[FEATURE_COLUMNS])[0])
    
    # Need volatility_10 for position sizing (Rule 4)
    vol_10 = float(last_row["volatility_10"].iloc[0])
    
    return pred_return, vol_10

def _score_one_ticker_ml(pair):
    ticker, ohlcv = pair
    try:
        ml_df = prepare_ml_dataframe(ohlcv)
        if ml_df.empty: return ticker, None, None, None, "Insufficient data"
        
        pred_return, vol_10 = train_and_score(ml_df)
        price = float(ohlcv["Close"].dropna().iloc[-1])
        return ticker, pred_return, vol_10, price, None
    except Exception as e:
        return ticker, None, None, None, str(e)

def run_parallel_ml_scoring(ohlcv_map):
    scores, vol_map, prices, errors = {}, {}, {}, []
    pairs = list(ohlcv_map.items())
    if not pairs:
        log.warning("No tickers found to score.")
        return scores, vol_map, prices, errors

    n_workers = max(1, min(MAX_ML_WORKERS, len(pairs)))
    
    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        futures = [ex.submit(_score_one_ticker_ml, p) for p in pairs]
        for fut in as_completed(futures):
            ticker, pred, vol, px, err = fut.result()
            if err: errors.append((ticker, err))
            elif pred is not None:
                scores[ticker] = pred
                vol_map[ticker] = vol
                prices[ticker] = px
    return scores, vol_map, prices, errors

# ===== MAIN =====
def main():
    log.info("========== BOT RUN START %s ==========", datetime.utcnow().isoformat())
    
    # Rule 10: Time-based execution
    hour_utc = datetime.utcnow().hour
    MODE = "OPEN" if hour_utc < 16 else "CLOSE"
    log.info("Time Check: UTC Hour=%d, MODE=%s", hour_utc, MODE)

    account = get_account()
    cash = float(account["cash"])
    portfolio = get_portfolio()
    positions = {p["ticker"]: p for p in portfolio}
    cooldown_tickers = get_recent_sells()
    market_regime_bullish = get_market_regime()
    
    log.info("Startup: cash=%.2f, positions=%s, cooldowns=%s", cash, list(positions.keys()), list(cooldown_tickers))

    # Data Fetching
    sp500 = fetch_sp500_tickers()
    filter_map = bulk_download_by_ticker(sp500, "6mo")
    
    # Preliminary Momentum Filter
    ranked_mom = []
    for t, df in filter_map.items():
        if len(df) < 50: continue
        px = df["Close"].astype(float)
        mom = float(px.iloc[-1] / px.iloc[-21] - 1.0)
        if mom > 0: ranked_mom.append((t, mom))
    
    ranked_mom.sort(key=lambda x: -x[1])
    top_tickers = [t for t, _ in ranked_mom[:TOP_ML_COUNT]]
    
    # Ensure held positions are also scored
    ml_list = list(set(top_tickers + list(positions.keys())))
    ohlcv_1y = bulk_download_by_ticker(ml_list, "1y")
    
    scores, vol_map, prices, errors = run_parallel_ml_scoring(ohlcv_1y)
    
    if not scores:
        log.error("No valid ML scores generated. Exiting.")
        return

    # Rule 8: Cross-sectional Normalization
    pred_values = list(scores.values())
    mean_pred = np.mean(pred_values)
    std_pred = np.std(pred_values) or 1.0
    z_scores = {t: (s - mean_pred) / std_pred for t, s in scores.items()}
    
    # Rule 7 & 12: Ranking & Debug
    ranked_candidates = sorted(z_scores.items(), key=lambda x: -x[1])
    log.info("Top 10 Ranked Stocks (Z-Score):")
    for t, zs in ranked_candidates[:10]:
        log.info("  %s: pred_return=%.6f, z_score=%.4f", t, scores[t], zs)

    # ===== SELL PHASE (Rule 10: Only in CLOSE mode) =====
    log.info("---------- SELL PHASE (MODE=%s) ----------", MODE)
    if MODE == "CLOSE":
        for ticker, pos in list(positions.items()):
            price = prices.get(ticker)
            if price is None: continue
            
            hold_days = days_since(pos["buy_date"])
            buy_price = float(pos["buy_price"])
            shares = float(pos["shares"])
            
            # Rule 11: Strict No Day-Trading
            if datetime.now().strftime("%Y-%m-%d") == pos["buy_date"]:
                log.info("SELL skip %s: bought today (Day-trading protection)", ticker)
                continue
            
            sell_reason = None
            if price < buy_price * STOP_LOSS: sell_reason = "STOP_LOSS"
            elif price > buy_price * TAKE_PROFIT: sell_reason = "TAKE_PROFIT" # Rule 5
            elif ticker in scores and scores[ticker] < 0.4 and hold_days >= MIN_HOLD_DAYS:
                sell_reason = "MODEL_SELL"
            
            if sell_reason:
                # Rule 9: Transaction Costs
                execution_price = price * COST_SELL
                proceeds = shares * execution_price
                cash += proceeds
                log_trade(sell_reason, ticker, execution_price, shares)
                remove_position(ticker)
                log.info("Sold %s: %s @ %.2f (proceeds %.2f)", ticker, sell_reason, execution_price, proceeds)
            else:
                log.info("Hold %s: price=%.2f, hold_days=%d", ticker, price, hold_days)
    else:
        log.info("Skipping SELL phase (Rules: Only allow SELL when MODE == CLOSE)")

    # ===== BUY PHASE (Rule 10: Only in OPEN mode) =====
    log.info("---------- BUY PHASE (MODE=%s) ----------", MODE)
    current_portfolio_size = len(get_portfolio())
    available_slots = MAX_POSITIONS - current_portfolio_size
    
    # Rule 3: Market Regime Filter
    if not market_regime_bullish:
        log.info("BUY disabled: Market Regime is BEARISH (MA50 < MA200)")
        available_slots = 0

    if MODE == "OPEN" and available_slots > 0:
        # Filter top picks (Rule 7: pred > 0, Rule 6: No cooldown, not already owned)
        eligible = []
        for t, zs in ranked_candidates:
            if scores[t] > MIN_PREDICTED_RETURN and t not in positions and t not in cooldown_tickers:
                # Rule 4: Risk-adjusted score
                vol = vol_map.get(t, 0.02) # fallback
                risk_score = scores[t] / (vol if vol > 0 else 0.02)
                eligible.append((t, risk_score))
            if len(eligible) >= 10: break # Look at top 10 for sizing
            
        top_picks = eligible[:TOP_BUY_PICKS]
        log.info("Selected Top Picks for Buy: %s", top_picks)
        
        if not top_picks:
            log.info("No eligible top picks found.")
            if discord_no_trade: discord_no_trade()
        else:
            # Rule 4: Normalizing weights
            total_risk_score = sum(rs for _, rs in top_picks[:available_slots])
            
            for ticker, rs in top_picks[:available_slots]:
                price = prices.get(ticker)
                if price is None: continue
                
                weight = rs / total_risk_score if total_risk_score > 0 else (1.0 / available_slots)
                allocation = cash * weight
                
                if allocation < 5.0:
                    log.info("Skipped %s: allocation too small ($%.2f)", ticker, allocation)
                    continue

                # Rule 9: Transaction Costs
                execution_price = price * COST_BUY
                shares = float(allocation / execution_price)
                
                cost = shares * execution_price
                if cost <= cash + 1e-6:
                    cash -= cost
                    cash = max(0.0, cash)
                    add_position(ticker, shares, execution_price)
                    log_trade("BUY", ticker, execution_price, shares)
                    log.info("Bought %s: %.4f shares @ %.2f (cost %.2f)", ticker, shares, execution_price, cost)
                    log.info("DEBUG BUY | Ticker: %s | Pred Return: %.4f | Alloc: $%.2f | Shares: %.4f", ticker, scores[ticker], allocation, shares)
                else:
                    log.info("Skipped %s: insufficient cash for %.4f shares", ticker, shares)
    elif MODE != "OPEN":
        log.info("Skipping BUY phase (Rules: Only allow BUY when MODE == OPEN)")
    else:
        log.info("Skipping BUY phase: Available slots=%d", available_slots)

    # Wrap up
    log.info("Final Cash: %.2f", cash)
    update_cash(cash)
    
    # Performance Snapshot
    final_portfolio = get_portfolio()
    total_val = cash
    unrealized_pl = 0.0
    for p in final_portfolio:
        px = prices.get(p["ticker"], float(p["buy_price"]))
        shares = float(p["shares"])
        total_val += shares * px
        unrealized_pl += (px - float(p["buy_price"])) * shares
    
    try:
        supabase.table("performance").insert({"date": datetime.now().strftime("%Y-%m-%d"), "total_value": float(total_val)}).execute()
        
        if discord_portfolio_summary:
            discord_portfolio_summary(
                run_date=datetime.now().strftime("%Y-%m-%d"),
                cash=cash,
                invested=total_val - cash,
                total_value=total_val,
                pl_unrealized=unrealized_pl,
                top_picks=[(t, scores[t]) for t, _ in (top_picks if 'top_picks' in locals() else [])],
                positions={p["ticker"]: p for p in final_portfolio},
                prices=prices
            )
    except Exception as e:
        log.error("Final reporting error: %s", e)

    log.info("========== BOT RUN END wall_ms=%.2f ==========", _dt(RUN_T0))

if __name__ == "__main__":
    RUN_T0 = _t0()
    try:
        main()
    except Exception as e:
        log.exception("Fatal error in main")
        if discord_error: discord_error(str(e))
