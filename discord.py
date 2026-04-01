import os
import requests
from datetime import datetime

# ===== CONFIG =====
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")  # set this in your environment

# ===== CORE FUNCTION =====
def send_discord(message):
    if not DISCORD_WEBHOOK:
        print("Discord webhook not set (DISCORD_WEBHOOK).")
        return

    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message})
    except Exception as e:
        print("Discord error:", e)

# ===== TRADE ALERT =====
def discord_trade_alert(action, ticker, price, shares):
    msg = (
        "**TRADE ALERT**\n"
        f"- Action: {action}\n"
        f"- Ticker: {ticker}\n"
        f"- Price: ${price:.2f}\n"
        f"- Shares: {shares}\n"
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_discord(msg)

# ===== PORTFOLIO SUMMARY =====
def discord_portfolio_summary(
    *,
    run_date,
    cash,
    invested,
    total_value,
    profit_loss_since_start=None,
    profit_loss_day=None,
    top_picks=None,
    positions=None,
    prices=None,
):
    positions = positions or {}
    prices = prices or {}
    top_picks = top_picks or []

    msg = f"**PORTFOLIO UPDATE** ({run_date})\n\n"
    msg += f"- Cash left: ${cash:.2f}\n"
    msg += f"- Total invested (open positions): ${invested:.2f}\n"
    msg += f"- Total value: ${total_value:.2f}\n"

    if profit_loss_since_start is not None:
        msg += f"- P/L since start: ${profit_loss_since_start:.2f}\n"
    if profit_loss_day is not None:
        msg += f"- P/L vs previous snapshot: ${profit_loss_day:.2f}\n"

    msg += "\n**Top Picks (predicted return)**\n"
    if top_picks:
        for ticker, score in top_picks:
            msg += f"- {ticker}: {score:.4f}\n"
    else:
        msg += "- None\n"

    msg += "\n**Positions**\n"
    if not positions:
        msg += "- None\n"
    else:
        for ticker, pos in positions.items():
            price = float(prices.get(ticker) or 0.0)
            shares = int(pos.get("shares") or 0)
            buy_price = float(pos.get("buy_price") or 0.0)
            value = shares * price
            pnl_pct = ((price - buy_price) / buy_price) * 100 if buy_price else 0.0
            msg += f"- {ticker}: {shares} sh | ${value:.2f} | {pnl_pct:.2f}%\n"

    send_discord(msg)

# ===== NO TRADE ALERT =====
def discord_no_trade():
    msg = "**No valid trading signals today.**"
    send_discord(msg)

# ===== ERROR ALERT =====
def discord_error(error_msg):
    msg = f"**BOT ERROR**\n{error_msg}"
    send_discord(msg)