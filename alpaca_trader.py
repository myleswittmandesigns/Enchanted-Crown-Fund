#!/usr/bin/env python3
"""
alpaca_trader.py
----------------
Reads today's cross-sectional signal and reconciles it against the
current Alpaca paper-trading portfolio.

Runs as the final step of update_data.yml, after the email is sent.

Required GitHub Actions secrets:
  ALPACA_API_KEY      Paper trading API key ID
  ALPACA_SECRET_KEY   Paper trading secret key

Trading is DISABLED by default. To enable paper trading, add a secret:
  TRADING_ENABLED = true

When disabled the script logs exactly what it WOULD do — useful for
shadow-trading a week or two before going live.
"""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR        = Path(__file__).parent
REPORTS_DIR     = REPO_DIR / "reports"
DATA_DIR        = REPO_DIR / "data"

TRADING_ENABLED = os.environ.get("TRADING_ENABLED", "false").lower() == "true"
API_KEY         = os.environ.get("ALPACA_API_KEY", "")
SECRET_KEY      = os.environ.get("ALPACA_SECRET_KEY", "")

MODE = "LIVE PAPER" if TRADING_ENABLED else "DRY RUN"

BUY_NOTIONAL = 10_000.00  # Fixed dollar amount per trade


# ── Helpers ───────────────────────────────────────────────────────────────────

def _latest(pattern: str) -> pd.DataFrame | None:
    files = sorted(REPORTS_DIR.glob(pattern), reverse=True)
    if not files:
        return None
    try:
        return pd.read_csv(files[0])
    except Exception:
        return None


def load_signal() -> tuple[str, str, float]:
    """Returns (state, ticker, last_price). State = HOLDING | FLAT."""
    df = _latest("cs_signal_*.csv")
    if df is None or df.empty:
        return "FLAT", "", 0.0
    row = df.iloc[0]
    state  = str(row.get("State", "FLAT")).upper()
    ticker = str(row.get("Ticker", ""))
    price  = float(row.get("Last $", 0.0))
    return state, ticker, price


def get_client():
    if not API_KEY or not SECRET_KEY:
        print(f"[alpaca] Skipping — ALPACA_API_KEY / ALPACA_SECRET_KEY not set.")
        return None
    try:
        from alpaca.trading.client import TradingClient
        return TradingClient(API_KEY, SECRET_KEY, paper=True)
    except ImportError:
        print("[alpaca] alpaca-py not installed.")
        return None
    except Exception as e:
        print(f"[alpaca] Connection failed: {e}")
        return None


def get_positions(client) -> dict[str, float]:
    """Returns {ticker: qty} for all open positions."""
    try:
        positions = client.get_all_positions()
        return {p.symbol: float(p.qty) for p in positions}
    except Exception as e:
        print(f"[alpaca] Could not fetch positions: {e}")
        return {}


def get_portfolio_value(client) -> float:
    try:
        account = client.get_account()
        return float(account.portfolio_value)
    except Exception as e:
        print(f"[alpaca] Could not fetch account: {e}")
        return 0.0


def place_buy(client, ticker: str):
    """Buy $BUY_NOTIONAL of ticker (market order, next open)."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    # Use notional (dollar amount) so we get fractional shares if needed
    order = MarketOrderRequest(
        symbol=ticker,
        notional=BUY_NOTIONAL,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    return client.submit_order(order_data=order)


def place_sell(client, ticker: str, qty: float):
    """Sell entire position in ticker (market order, next open)."""
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    order = MarketOrderRequest(
        symbol=ticker,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    return client.submit_order(order_data=order)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*60}")
    print(f"[alpaca] Enchanted Crown Fund — Alpaca Trader  [{MODE}]")
    print(f"[alpaca] Date: {today}")
    print(f"{'='*60}")

    # ── Load model signal ─────────────────────────────────────────────────────
    state, signal_ticker, last_price = load_signal()
    print(f"[alpaca] Model signal : {state}"
          + (f" {signal_ticker} @ ${last_price:.2f}" if signal_ticker else ""))

    # ── Connect to Alpaca ─────────────────────────────────────────────────────
    client = get_client()
    if client is None:
        return

    positions      = get_positions(client)
    portfolio_value = get_portfolio_value(client)
    held_tickers   = list(positions.keys())

    print(f"[alpaca] Portfolio    : ${portfolio_value:,.2f}")
    print(f"[alpaca] Positions    : {held_tickers if held_tickers else 'none'}")

    # ── Reconcile ─────────────────────────────────────────────────────────────
    actions = []

    # Close any position the model no longer wants
    for held in held_tickers:
        if state == "FLAT" or (state == "HOLDING" and held != signal_ticker):
            actions.append(("SELL", held, positions[held]))

    # Open a position if the model says HOLDING and we don't have it yet
    if state == "HOLDING" and signal_ticker and signal_ticker not in positions:
        actions.append(("BUY", signal_ticker, None))

    if not actions:
        print(f"[alpaca] No action needed — portfolio already matches model signal.")
        return

    # ── Execute (or log) ──────────────────────────────────────────────────────
    for action, ticker, qty in actions:
        if action == "SELL":
            print(f"[alpaca] {MODE} → SELL {qty:.4f} shares of {ticker}")
            if TRADING_ENABLED:
                try:
                    order = place_sell(client, ticker, qty)
                    print(f"[alpaca]   Order submitted: {order.id} | status: {order.status}")
                except Exception as e:
                    print(f"[alpaca]   SELL failed: {e}")

        elif action == "BUY":
            print(f"[alpaca] {MODE} → BUY  ${BUY_NOTIONAL:,.2f} of {ticker}"
                  + (f" (~{BUY_NOTIONAL / last_price:.1f} shares @ ${last_price:.2f})" if last_price else ""))
            if TRADING_ENABLED:
                try:
                    order = place_buy(client, ticker)
                    print(f"[alpaca]   Order submitted: {order.id} | status: {order.status}")
                except Exception as e:
                    print(f"[alpaca]   BUY failed: {e}")

    if not TRADING_ENABLED:
        print(f"\n[alpaca] DRY RUN complete — no orders placed.")
        print(f"[alpaca] To enable paper trading, add GitHub secret: TRADING_ENABLED=true")


if __name__ == "__main__":
    main()
