import os
import requests
from datetime import datetime
from config import DISCORD_WEBHOOK
from utils.logger import log


def send_discord(message: str):
    if not DISCORD_WEBHOOK:
        log.warning("Discord webhook not set (DISCORD_WEBHOOK).")
        return

    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        log.error("Discord error: %s", e)


from utils.currency import get_currency, get_conversion_rates, format_currency

def discord_trade_alert(action: str, ticker: str, price: float, shares: float, remaining_shares: float = None, pnl_pct: float = None):
    shares = float(shares)
    price = float(price)
    currency = get_currency(ticker)
    inr_to_usd, _ = get_conversion_rates()
    
    local_allocation = shares * price
    
    icon = "🇮🇳" if currency == "INR" else "🇺🇸"
    market_name = "INDIA MARKET" if currency == "INR" else "US MARKET"
    
    # Partial Sale formatting
    partial_info = ""
    is_partial = remaining_shares is not None and remaining_shares > 0
    if is_partial:
        total_shares = float(shares + remaining_shares)
        pct_sold = (shares / total_shares) * 100
        partial_info = f"\n- **% Sold**: {pct_sold:.1f}%\n- **Remaining**: {remaining_shares:.4f}"
        action = f"PARTIAL {action.replace('PARTIAL_', '')}"

    pnl_info = ""
    if pnl_pct is not None:
        pnl_info = f"\n- **P/L**: {pnl_pct:+.2f}%"

    msg = (
        f"**{icon} {market_name} TRADE ALERT**\n"
        f"- Action: {action}\n"
        f"- Ticker: {ticker}\n"
        f"- Net Value: {format_currency(local_allocation, currency, inr_to_usd if currency == 'INR' else None)}\n"
        f"- Price: {format_currency(price, currency)}\n"
        f"- Shares Sold: {shares:.4f}{pnl_info}{partial_info}\n"
        f"- Time: {datetime.now().strftime('%H:%M:%S')}\n"
    )
    send_discord(msg)


def discord_portfolio_summary(
    *,
    run_date: str,
    cash_usd: float,
    cash_inr: float,
    pl_unrealized_usd: float = None, # Global P/L
    top_picks: list = None,
    positions: dict = None,
    prices: dict = None,
    position_actions: dict = None,
):
    positions = positions or {}
    prices = prices or {}
    top_picks = top_picks or []
    position_actions = position_actions or {}
    
    inr_to_usd, usd_to_inr = get_conversion_rates()
    
    # Marketplace calculations
    us_invested = 0.0
    us_value = 0.0
    in_invested = 0.0
    in_value = 0.0
    
    us_rows = []
    in_rows = []
    
    for ticker, pos in positions.items():
        price = float(prices.get(ticker) or 0.0)
        shares = float(pos.get("shares") or 0.0)
        buy_price = float(pos.get("buy_price") or 0.0)
        currency = pos.get("currency", get_currency(ticker))
        
        inv_local = shares * buy_price
        val_local = shares * price
        pnl_local = val_local - inv_local
        pnl_pct = (pnl_local / inv_local) * 100 if inv_local > 0 else 0.0
        
        from utils.currency import normalize_to_usd
        inv_usd = normalize_to_usd(inv_local, currency, inr_to_usd)
        
        action = position_actions.get(ticker, "HOLD")
        val_str = format_currency(val_local, currency, inr_to_usd if currency == 'INR' else None)
        row_str = f"- **{ticker}**: {shares:.4f} shares ({val_str}) | P/L: {pnl_pct:+.2f}%"
        
        if currency == "INR":
            in_invested += inv_local
            in_value += val_local
            in_rows.append((inv_usd, row_str))
        else:
            us_invested += inv_local
            us_value += val_local
            us_rows.append((inv_usd, row_str))

    us_pnl = us_value - us_invested
    in_pnl = in_value - in_invested
    
    global_val_usd = us_value + (in_value * inr_to_usd) + cash_usd + (cash_inr * inr_to_usd)
    
    msg = "@everyone\n"
    msg += f"🌎 **GLOBAL PORTFOLIO UPDATE** ({run_date})\n"
    msg += f"💰 **Total Net Value**: ${global_val_usd:.2f}\n\n"
    
    # US SECTION
    msg += "🇺🇸 **US MARKET SUMMARY**\n"
    msg += f"- Total Value: ${us_value + cash_usd:.2f}\n"
    msg += f"- Invested: ${us_invested:.2f}\n"
    msg += f"- Cash: ${cash_usd:.2f}\n"
    msg += f"- P/L Unrealized: ${us_pnl:+.2f} ({ (us_pnl/us_invested*100) if us_invested > 0 else 0:+.2f}%)\n"
    if us_rows:
        us_rows.sort(key=lambda x: x[0], reverse=True)
        for _, r in us_rows[:10]: msg += r + "\n"
    msg += "\n"

    # INDIA SECTION
    msg += "🇮🇳 **INDIA MARKET SUMMARY**\n"
    msg += f"- Total Value: ₹{in_value + cash_inr:.2f}\n"
    msg += f"- Invested: ₹{in_invested:.2f}\n"
    msg += f"- Cash: ₹{cash_inr:.2f}\n"
    msg += f"- P/L Unrealized: ₹{in_pnl:+.2f} ({ (in_pnl/in_invested*100) if in_invested > 0 else 0:+.2f}%)\n"
    if in_rows:
        in_rows.sort(key=lambda x: x[0], reverse=True)
        for _, r in in_rows[:10]: msg += r + "\n"

    msg += "\n--- **Top Potential Picks** ---\n"
    if top_picks:
        for ticker, score in top_picks[:5]:
            icon = "🇮🇳" if ticker.endswith(".NS") else "🇺🇸"
            msg += f"{icon} {ticker}: {score:.4f}\n"

    send_discord(msg)


def discord_no_trade():
    msg = "**No valid trading signals today.**"
    send_discord(msg)


def discord_error(error_msg: str):
    msg = f"**BOT ERROR**\n{error_msg}"
    send_discord(msg)
