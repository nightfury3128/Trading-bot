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


def discord_trade_alert(action: str, ticker: str, price: float, shares: float):
    shares = float(shares)
    price = float(price)
    allocation = shares * price
    msg = (
        "**TRADE ALERT**\n"
        f"- Action: {action}\n"
        f"- Ticker: {ticker}\n"
        f"- Investment: ${allocation:.2f}\n"
        f"- Price: ${price:.2f}\n"
        f"- Shares: {shares:.4f}\n"
        f"- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    send_discord(msg)


def discord_portfolio_summary(
    *,
    run_date: str,
    cash: float,
    invested: float,
    total_value: float,
    pl_unrealized: float = None,
    top_picks: list = None,
    positions: dict = None,
    prices: dict = None,
    position_actions: dict = None,
):
    positions = positions or {}
    prices = prices or {}
    top_picks = top_picks or []
    position_actions = position_actions or {}
    msg = "@everyone\n"
    msg += f"**PORTFOLIO UPDATE** ({run_date})\n\n"
    msg += f"**Amount Invested**: ${invested:.2f}\n"
    msg += f"**Capital Left**: ${cash:.2f}\n"
    if pl_unrealized is not None:
        msg += f"**P/L Unrealized**: ${pl_unrealized:.2f}\n"
    msg += f"**Total Value**: ${total_value:.2f}\n"

    msg += "\n**Top picks**\n"
    if top_picks:
        for ticker, score in top_picks:
            msg += f"- {ticker}: {score:.4f}\n"
    else:
        msg += "- None\n"

    msg += "\n**Positions**\n"
    if not positions:
        msg += "- None\n"
    else:
        rows = []
        for ticker, pos in positions.items():
            price = float(prices.get(ticker) or 0.0)
            shares = float(pos.get("shares") or 0.0)
            buy_price = float(pos.get("buy_price") or 0.0)
            invested_amt = shares * buy_price
            value = shares * price
            pnl_amt = value - invested_amt
            pnl_pct = (pnl_amt / invested_amt) * 100 if invested_amt > 0 else 0.0
            action = position_actions.get(ticker, "HOLD")
            rows.append((invested_amt, ticker, value, pnl_amt, pnl_pct, action, shares))

        rows.sort(key=lambda x: x[0], reverse=True)  # by invested amount
        for invested_amt, ticker, value, pnl_amt, pnl_pct, action, shares in rows:
            msg += (
                f"- {ticker}: {shares:.4f} shares (${value:.2f}) | invested=${invested_amt:.2f} | "
                f"P/L=${pnl_amt:.2f} ({pnl_pct:.2f}%) | action={action}\n"
            )

    send_discord(msg)


def discord_no_trade():
    msg = "**No valid trading signals today.**"
    send_discord(msg)


def discord_error(error_msg: str):
    msg = f"**BOT ERROR**\n{error_msg}"
    send_discord(msg)
