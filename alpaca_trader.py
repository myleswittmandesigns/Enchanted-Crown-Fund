#!/usr/bin/env python3
"""
alpaca_trader.py
----------------
Mirrors the cross-sectional backtester's exact entry/exit logic against
the Alpaca paper-trading portfolio.

Entry logic (when FLAT):
  - Compute composite z-score (mean of Z(N1), Z(N2), Z(N3)) for every ticker
  - Buy the most oversold ticker if its composite Z ≤ -K
  - Never switches tickers mid-position

Exit logic (when HOLDING):
  - Take profit : today's close crosses above the upper Bollinger Band
                  for ANY of the 3 windows (N1, N2, or N3)
  - Stop loss   : close ≤ entry_price × (1 − Stop %)
  - No other exit conditions — z-score changes while holding are ignored

Parameters (N1, N2, N3, K, Stop %) are loaded from the latest cs_summary
file so they always stay in sync with the backtester.

Required GitHub Actions secrets:
  ALPACA_API_KEY      Paper trading API key ID
  ALPACA_SECRET_KEY   Paper trading secret key

Trading is DISABLED by default. To enable paper trading, add a secret:
  TRADING_ENABLED = true

When disabled the script logs exactly what it WOULD do.
"""

import os
from datetime import date
from pathlib import Path

import numpy as np
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


# ── Load model parameters ─────────────────────────────────────────────────────

def load_params() -> dict | None:
    """Load N1, N2, N3, K, Stop % from the latest cs_summary file."""
    files = sorted(REPORTS_DIR.glob("cs_summary_*.csv"), reverse=True)
    if not files:
        print("[alpaca] No cs_summary file found — cannot determine model parameters.")
        return None
    try:
        row = pd.read_csv(files[0]).iloc[0]
        return {
            "n1":       int(row["N1"]),
            "n2":       int(row["N2"]),
            "n3":       int(row["N3"]),
            "k":        float(row["K"]),
            "stop_pct": float(row["Stop %"]),
        }
    except Exception as e:
        print(f"[alpaca] Failed to load params: {e}")
        return None


# ── Entry signal (when flat) ──────────────────────────────────────────────────

def compute_entry_signal(params: dict) -> tuple[str, float]:
    """
    Rank all tickers by composite z-score.
    Returns (ticker, last_price) if the top ticker is below entry threshold,
    or ("", 0.0) if nothing qualifies.
    """
    n1, n2, n3 = params["n1"], params["n2"], params["n3"]
    k           = params["k"]
    threshold   = -k

    rows = []
    for p in sorted(DATA_DIR.glob("*_daily_high_low.csv")):
        ticker = p.stem.replace("_daily_high_low", "")
        try:
            df    = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
            close = df["Close"].astype(float)
            if len(close) < max(n1, n2, n3) + 1 or close.isna().all():
                continue
            zs, valid = [], True
            for n in [n1, n2, n3]:
                sma = close.rolling(n).mean()
                std = close.rolling(n).std(ddof=0)
                if pd.isna(sma.iloc[-1]) or pd.isna(std.iloc[-1]) or std.iloc[-1] < 1e-9:
                    valid = False; break
                zs.append(float((close.iloc[-1] - sma.iloc[-1]) / std.iloc[-1]))
            if not valid:
                continue
            rows.append({
                "Ticker":      ticker,
                "Close":       float(close.iloc[-1]),
                "Composite Z": float(np.mean(zs)),
            })
        except Exception:
            continue

    if not rows:
        print("[alpaca] No valid z-scores computed.")
        return "", 0.0

    df_z = pd.DataFrame(rows).sort_values("Composite Z").reset_index(drop=True)
    top  = df_z.iloc[0]

    print(f"[alpaca] Universe       : {len(df_z)} tickers ranked")
    print(f"[alpaca] Top candidate  : {top['Ticker']}  "
          f"Z={top['Composite Z']:.3f}  (threshold={threshold:.2f})")

    if top["Composite Z"] <= threshold:
        return str(top["Ticker"]), float(top["Close"])
    return "", 0.0


# ── Exit signal (when holding) ────────────────────────────────────────────────

def compute_exit_signal(ticker: str, entry_price: float, params: dict) -> tuple[bool, str]:
    """
    Mirrors the backtester's CS exit logic exactly.
    Returns (should_exit, reason).

    Take profit : today's close crosses ABOVE the upper BB on ANY of N1/N2/N3
                  (i.e. yesterday ≤ upper, today > upper)
    Stop loss   : today's close ≤ entry_price × (1 − stop_pct)
    """
    n1, n2, n3   = params["n1"], params["n2"], params["n3"]
    k            = params["k"]
    stop_pct     = params["stop_pct"]

    path = DATA_DIR / f"{ticker}_daily_high_low.csv"
    if not path.exists():
        print(f"[alpaca] Data file missing for {ticker} — cannot evaluate exit.")
        return False, ""

    try:
        df    = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
        close = df["Close"].astype(float)
        if len(close) < 2:
            return False, ""

        c   = float(close.iloc[-1])   # today's close
        c_p = float(close.iloc[-2])   # yesterday's close

        # Stop loss
        stop_level = entry_price * (1.0 - stop_pct)
        if c <= stop_level:
            return True, f"stop loss (close ${c:.2f} ≤ stop ${stop_level:.2f})"

        # Take profit: crossover on any of the 3 upper bands
        for n in [n1, n2, n3]:
            sma   = close.rolling(n).mean()
            std   = close.rolling(n).std(ddof=0)
            upper = (sma + k * std)
            if pd.isna(upper.iloc[-1]) or pd.isna(upper.iloc[-2]):
                continue
            if c > float(upper.iloc[-1]) and c_p <= float(upper.iloc[-2]):
                return True, f"take profit (crossed upper BB N={n}, upper=${upper.iloc[-1]:.2f})"

        return False, ""

    except Exception as e:
        print(f"[alpaca] Exit signal error for {ticker}: {e}")
        return False, ""


# ── Alpaca client helpers ─────────────────────────────────────────────────────

def get_client():
    if not API_KEY or not SECRET_KEY:
        print("[alpaca] Skipping — ALPACA_API_KEY / ALPACA_SECRET_KEY not set.")
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


def get_positions(client) -> dict[str, dict]:
    """Returns {ticker: {qty, avg_entry_price}} for all open positions."""
    try:
        positions = client.get_all_positions()
        return {
            p.symbol: {
                "qty":             float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
            }
            for p in positions
        }
    except Exception as e:
        print(f"[alpaca] Could not fetch positions: {e}")
        return {}


def get_portfolio_value(client) -> float:
    try:
        return float(client.get_account().portfolio_value)
    except Exception as e:
        print(f"[alpaca] Could not fetch account: {e}")
        return 0.0


def place_buy(client, ticker: str):
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    order = MarketOrderRequest(
        symbol=ticker,
        notional=BUY_NOTIONAL,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    return client.submit_order(order_data=order)


def place_sell(client, ticker: str, qty: float):
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

    # ── Load model parameters ─────────────────────────────────────────────────
    params = load_params()
    if params is None:
        return
    print(f"[alpaca] Model params   : N={params['n1']}/{params['n2']}/{params['n3']}  "
          f"K={params['k']}  Stop={params['stop_pct']:.0%}")

    # ── Connect to Alpaca ─────────────────────────────────────────────────────
    client = get_client()
    if client is None:
        return

    positions       = get_positions(client)
    portfolio_value = get_portfolio_value(client)
    held_tickers    = list(positions.keys())

    print(f"[alpaca] Portfolio      : ${portfolio_value:,.2f}")
    print(f"[alpaca] Positions      : {held_tickers if held_tickers else 'none'}")

    # ── Single-position rule: warn if somehow holding more than one ───────────
    if len(positions) > 1:
        print(f"[alpaca] WARNING: {len(positions)} positions found — model is single-position only.")

    # ── HOLDING: check backtester exit conditions ─────────────────────────────
    if positions:
        ticker      = held_tickers[0]
        entry_price = positions[ticker]["avg_entry_price"]
        qty         = positions[ticker]["qty"]
        stop_level  = entry_price * (1.0 - params["stop_pct"])

        print(f"[alpaca] Holding        : {ticker}  entry=${entry_price:.2f}  "
              f"stop=${stop_level:.2f}  qty={qty:.4f}")

        should_exit, reason = compute_exit_signal(ticker, entry_price, params)

        if should_exit:
            print(f"[alpaca] EXIT SIGNAL    : {reason}")
            print(f"[alpaca] {MODE} → SELL {qty:.4f} shares of {ticker}")
            if TRADING_ENABLED:
                try:
                    order = place_sell(client, ticker, qty)
                    print(f"[alpaca]   Order submitted: {order.id} | status: {order.status}")
                except Exception as e:
                    print(f"[alpaca]   SELL failed: {e}")
        else:
            print(f"[alpaca] Holding {ticker} — no exit conditions met.")

    # ── FLAT: check entry conditions ──────────────────────────────────────────
    else:
        signal_ticker, last_price = compute_entry_signal(params)

        if signal_ticker:
            print(f"[alpaca] ENTRY SIGNAL   : BUY {signal_ticker} @ ${last_price:.2f}")
            print(f"[alpaca] {MODE} → BUY  ${BUY_NOTIONAL:,.2f} of {signal_ticker}"
                  f" (~{BUY_NOTIONAL / last_price:.1f} shares)")
            if TRADING_ENABLED:
                try:
                    order = place_buy(client, signal_ticker)
                    print(f"[alpaca]   Order submitted: {order.id} | status: {order.status}")
                except Exception as e:
                    print(f"[alpaca]   BUY failed: {e}")
        else:
            print(f"[alpaca] FLAT — no ticker below entry threshold. No action.")

    if not TRADING_ENABLED:
        print(f"\n[alpaca] DRY RUN complete — no orders placed.")
        print(f"[alpaca] To enable paper trading, add GitHub secret: TRADING_ENABLED=true")


if __name__ == "__main__":
    main()
