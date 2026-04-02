import os
from db.account import update_cash
from db.portfolio import get_portfolio
from utils.logger import log


def fix_cash(starting_balance: float = 500.00):
    log.info("Fetching active positions from portfolio table...")
    portfolio = get_portfolio()

    total_invested = 0.0
    for pos in portfolio:
        cost = float(pos["shares"]) * float(pos["buy_price"])
        log.info(
            "  - %s: %.4f shares @ $%.2f = $%.2f",
            pos["ticker"],
            float(pos["shares"]),
            float(pos["buy_price"]),
            cost,
        )
        total_invested += cost

    log.info("Total Invested Amount: $%.2f", total_invested)

    new_cash = starting_balance - total_invested

    log.info("Target Starting Balance: $%.2f", starting_balance)
    log.info("Recalculated Cash Balance: $%.2f", new_cash)

    if new_cash < 0:
        log.warning("Computed cash is negative! Clamping to 0.0")
        new_cash = 0.0

    log.info("Updating 'account' table (id=1)...")
    update_cash(new_cash)
    log.info("SUCCESS! Account cash officially updated to: $%.2f", new_cash)


if __name__ == "__main__":
    fix_cash()
