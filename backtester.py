#!/usr/bin/env python3
"""
GSIT Mean Reversion Backtester — headless, no UI required.

Grid-searches N, K, and StopPct combinations against the full GSIT price history.
Entry:  first day close crosses below the lower Bollinger Band
Exit:   close >= SMA (take profit)  OR  close <= entry × (1 - StopPct) (stop loss)

Writes a sortable HTML report to reports/backtest_YYYY-MM-DD.html.
Run manually or via cron after update_data.py.
"""

import os
import pandas as pd
from itertools import product
from datetime import datetime
from pathlib import Path

REPO_DIR  = Path(__file__).parent
DATA_PATH = REPO_DIR / "data" / "GSIT_daily_high_low.csv"
OUT_DIR   = REPO_DIR / "reports"

# ── Parameter grid ─────────────────────────────────────────────────────────────
N_VALUES        = list(range(16, 28))                                   # [16, 17, ..., 27]
K_VALUES        = [round(k * 0.1, 1) for k in range(15, 31)]           # [1.5, 1.6, ..., 3.0]
STOP_PCT_VALUES = [0.46]

RDR_THRESHOLD   = 5.0    # rows at or above this are highlighted
MIN_TRADES      = 3      # skip combos with fewer completed trades
INITIAL_CAPITAL = 5000   # starting dollars — full balance is reinvested each trade


# ── Indicators ────────────────────────────────────────────────────────────────
def bollinger(close: pd.Series, n: int, k: float):
    sma = close.rolling(n).mean()
    std = close.rolling(n).std(ddof=0)
    return sma, sma + k * std, sma - k * std


# ── Single backtest run ───────────────────────────────────────────────────────
def run(close: pd.Series, n: int, k: float, stop_pct: float) -> dict | None:
    sma, _, lower = bollinger(close, n, k)
    buy = (close < lower) & (close.shift(1) >= lower.shift(1))

    trades = []
    in_trade    = False
    entry_price = None
    entry_idx   = None

    for i in range(n, len(close)):
        if not in_trade:
            if buy.iloc[i]:
                in_trade    = True
                entry_price = close.iloc[i]
                entry_idx   = i
        else:
            c = close.iloc[i]
            if c >= sma.iloc[i]:
                trades.append({"entry": entry_price, "exit": c, "hold": i - entry_idx, "reason": "tp"})
                in_trade = False
            elif c <= entry_price * (1 - stop_pct):
                trades.append({"entry": entry_price, "exit": c, "hold": i - entry_idx, "reason": "sl"})
                in_trade = False

    if len(trades) < MIN_TRADES:
        return None

    # Compounding model: full portfolio balance reinvested each trade
    balance       = INITIAL_CAPITAL
    balances      = [INITIAL_CAPITAL]
    trade_rets    = []
    wins_count    = 0
    win_pnls      = []
    loss_pnls     = []
    stop_hits     = 0

    for trade in trades:
        shares      = balance / trade["entry"]
        new_balance = shares * trade["exit"]
        pnl         = new_balance - balance
        ret_pct     = (trade["exit"] - trade["entry"]) / trade["entry"] * 100

        trade_rets.append(ret_pct)
        if pnl > 0:
            wins_count += 1
            win_pnls.append(pnl)
        else:
            loss_pnls.append(pnl)
        if trade["reason"] == "sl":
            stop_hits += 1

        balance = new_balance
        balances.append(balance)

    t             = pd.DataFrame(trades)
    num_trades    = len(trades)
    win_rate      = wins_count / num_trades * 100
    avg_win       = sum(win_pnls)  / len(win_pnls)  if win_pnls  else 0.0
    avg_loss      = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    avg_ret_pct   = sum(trade_rets) / len(trade_rets)
    avg_hold      = t["hold"].mean()
    final_balance = balance
    total_return  = final_balance - INITIAL_CAPITAL
    total_ret_pct = total_return / INITIAL_CAPITAL * 100

    # Max drawdown on portfolio value curve
    bal_series = pd.Series(balances)
    peak       = bal_series.cummax()
    max_dd     = (peak - bal_series).max()
    max_dd_pct = max_dd / peak.max() * 100

    rdr = round(total_return / max_dd, 2) if max_dd > 0 else float("inf")

    return {
        "N":              n,
        "K":              k,
        "Stop %":         stop_pct,
        "Trades":         num_trades,
        "Stop Hits":      int(stop_hits),
        "Win %":          round(win_rate, 1),
        "Avg Hold Days":  round(avg_hold, 1),
        "Final Balance $":round(final_balance, 2),
        "Total Return $": round(total_return, 2),
        "Total Return %": round(total_ret_pct, 2),
        "Max Drawdown $": round(max_dd, 2),
        "Max Drawdown %": round(max_dd_pct, 2),
        "RDR":            rdr,
    }


# ── HTML report ───────────────────────────────────────────────────────────────
def build_html(df: pd.DataFrame, run_date: str, data_through: str) -> str:
    rows_html = []
    for _, row in df.iterrows():
        good = isinstance(row["RDR"], float) and row["RDR"] >= RDR_THRESHOLD
        tr_class = ' class="good"' if good else ""
        star     = "★ " if good else ""
        cells = (
            f'<td>{int(row["N"])}</td>'
            f'<td>{row["K"]:.1f}</td>'
            f'<td>{row["Stop %"]:.0%}</td>'
            f'<td>{int(row["Trades"])}</td>'
            f'<td>{int(row["Stop Hits"])}</td>'
            f'<td>{row["Win %"]:.0f}%</td>'
            f'<td>{row["Avg Hold Days"]:.0f}</td>'
            f'<td>${row["Final Balance $"]:,.0f}</td>'
            f'<td>${row["Total Return $"]:,.0f}</td>'
            f'<td>{row["Total Return %"]:.0f}%</td>'
            f'<td>${row["Max Drawdown $"]:,.0f}</td>'
            f'<td>{row["Max Drawdown %"]:.0f}%</td>'
            f'<td><strong>{row["RDR"]:.2f}</strong></td>'
        )
        rows_html.append(f"<tr{tr_class}>{cells}</tr>")

    good_count  = sum(1 for _, r in df.iterrows() if isinstance(r["RDR"], float) and r["RDR"] >= RDR_THRESHOLD)
    best_rdr    = df.loc[df["RDR"].idxmax()]
    best_ret    = df.loc[df["Total Return $"].idxmax()]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GSIT Backtest — {run_date}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 100%; margin: 2rem auto; padding: 0 1.5rem; color: #222; }}
  h1   {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }}
  .summary {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
  .card {{ background: #f5f5f5; border-radius: 8px; padding: 0.75rem 1.25rem; min-width: 160px; }}
  .card .label {{ font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card .value {{ font-size: 1.3rem; font-weight: 600; }}
  .card .sub   {{ font-size: 0.75rem; color: #888; margin-top: 0.1rem; }}
  .table-wrap  {{ overflow-x: auto; width: 100%; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.88rem; }}
  thead th {{ background: #f0f0f0; padding: 0.5rem 0.75rem; text-align: left;
              border-bottom: 2px solid #ddd; vertical-align: bottom;
              cursor: pointer; user-select: none; }}
  thead th:hover {{ background: #e4e4e4; }}
  thead th.sort-desc::after {{ content: " ▼"; font-size: 0.65rem; color: #555; }}
  thead th.sort-asc::after  {{ content: " ▲"; font-size: 0.65rem; color: #555; }}
  tbody td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid #eee; white-space: nowrap; }}
  tbody tr:hover td {{ background: #fafafa; }}
  tr.good td   {{ background: #f0fff4; }}
  tr.good td strong {{ color: #1a7f3c; }}
  .legend {{ font-size: 0.8rem; color: #666; margin-top: 0.75rem; }}
  .tip-icon {{ font-size: 0.7rem; color: #999; margin-left: 3px;
               vertical-align: super; cursor: default; }}
  #tooltip {{ position: fixed; display: none; background: #1a1a1a; color: #fff;
              font-size: 0.78rem; line-height: 1.6; padding: 0.55rem 0.8rem;
              border-radius: 6px; width: 280px; z-index: 9999;
              box-shadow: 0 4px 12px rgba(0,0,0,0.3);
              pointer-events: none; white-space: pre-line; }}
</style>
</head>
<body>
<h1>📊 GSIT Mean Reversion — Backtest Report</h1>
<div class="meta">
  Run: {run_date} &nbsp;·&nbsp;
  Data through: {data_through} &nbsp;·&nbsp;
  Initial capital: ${INITIAL_CAPITAL:,} (compounded across all trades) &nbsp;·&nbsp;
  Entry: first close below lower Bollinger Band &nbsp;·&nbsp;
  Exit: close ≥ SMA (take profit) or close ≤ entry × (1 − Stop%) (stop loss)
</div>

<div class="summary">
  <div class="card">
    <div class="label">Combinations Tested</div>
    <div class="value">{len(df)}</div>
  </div>
  <div class="card">
    <div class="label">RDR ≥ {RDR_THRESHOLD} (Good)</div>
    <div class="value">{good_count}</div>
  </div>
  <div class="card">
    <div class="label">Best RDR</div>
    <div class="value">{best_rdr["RDR"]:.2f}</div>
    <div class="sub">N={int(best_rdr["N"])} K={best_rdr["K"]:.1f} Stop={best_rdr["Stop %"]:.0%}</div>
  </div>
  <div class="card">
    <div class="label">Best Total Return</div>
    <div class="value">${best_ret["Total Return $"]:,.2f}</div>
    <div class="sub">N={int(best_ret["N"])} K={best_ret["K"]:.1f} Stop={best_ret["Stop %"]:.0%}</div>
  </div>
  <div class="card">
    <div class="label">Initial Capital</div>
    <div class="value">${INITIAL_CAPITAL:,}</div>
    <div class="sub">compounded across all trades · edit INITIAL_CAPITAL in backtester.py</div>
  </div>
</div>

<div class="table-wrap">
<table>
<thead>
  <tr>
    <th data-tip="Lookback period (trading days)\nWindow used for SMA and Bollinger Bands.\nμ(N) = (1/N) × Σ C(i)  for i = t−N+1 to t">N<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Standard deviation multiplier\nDefines how wide the Bollinger Bands are.\nUpper = μ(N) + K × σ(N)\nLower = μ(N) − K × σ(N)">K<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Stop loss threshold\nTrade exits when price falls this far below entry.\nExit if: C(t) ≤ Entry × (1 − Stop%)">Stop %<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Total completed trades\nCount of buy→exit pairs in the full history.\nOpen trades at end of history are excluded.">Trades<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Stop loss exits\nNumber of trades that hit the stop loss\nrather than closing at the SMA take-profit.">Stop Hits<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Win rate\nFraction of trades where Exit Price &gt; Entry Price.\nWin % = (winning trades ÷ total trades) × 100">Win %<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Average holding period\nMean number of trading days between\nentry (buy signal) and exit (TP or SL).">Avg Hold Days<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Portfolio value after all trades close\nStarts at ${INITIAL_CAPITAL:,} and compounds:\nshares = balance ÷ entry price each trade\nnew balance = shares × exit price">Final Balance $<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Total dollar gain or loss over full history\nTotal Return $ = Final Balance − ${INITIAL_CAPITAL:,}\nPositive = profit, negative = loss.">Total Return $<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Total return as a percentage of initial capital\nTotal Return % = Total Return $ ÷ ${INITIAL_CAPITAL:,} × 100\nThis is your overall return on the ${INITIAL_CAPITAL:,} starting investment.">Total Return %<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Maximum drawdown in dollars\nLargest peak-to-trough decline in portfolio value.\nMax DD $ = max( peak balance − balance at each point )">Max Drawdown $<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Maximum drawdown as % of peak portfolio value\nMax DD % = Max DD $ ÷ peak balance × 100\nTells you the worst % loss from a high point.">Max Drawdown %<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Return-to-Drawdown Ratio\nRDR = Total Return $ ÷ Max Drawdown $\nMeasures how much return you earned per dollar\nof peak-to-trough loss. Above 5 is good.">RDR<span class="tip-icon">ⓘ</span></th>
  </tr>
</thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</div>

<div class="legend">Green rows = RDR ≥ {RDR_THRESHOLD} &nbsp;·&nbsp; RDR = Total Return ÷ Max Drawdown &nbsp;·&nbsp; Sorted by Total Return %, then RDR</div>

<div id="tooltip"></div>
<script>
  // ── Tooltips ────────────────────────────────────────────────────────────────
  const tip = document.getElementById('tooltip');
  const PAD = 14;
  document.querySelectorAll('th[data-tip]').forEach(th => {{
    th.addEventListener('mouseenter', () => {{
      tip.textContent = th.getAttribute('data-tip');
      tip.style.display = 'block';
    }});
    th.addEventListener('mousemove', e => {{
      const w = tip.offsetWidth, h = tip.offsetHeight;
      let x = e.clientX + PAD, y = e.clientY + PAD;
      if (x + w > window.innerWidth  - PAD) x = e.clientX - w - PAD;
      if (y + h > window.innerHeight - PAD) y = e.clientY - h - PAD;
      tip.style.left = x + 'px';
      tip.style.top  = y + 'px';
    }});
    th.addEventListener('mouseleave', () => {{
      tip.style.display = 'none';
    }});
  }});

  // ── Column sorting ──────────────────────────────────────────────────────────
  function cellValue(td) {{
    // Strip $, %, commas — return numeric value for sorting
    return parseFloat(td.textContent.replace(/[$,%★]/g, '').replace(/,/g, '').trim()) || 0;
  }}

  const table   = document.querySelector('table');
  const tbody   = table.querySelector('tbody');
  const headers = table.querySelectorAll('thead th');
  let lastCol = null, lastDir = null;

  headers.forEach((th, col) => {{
    th.addEventListener('click', () => {{
      // Toggle direction: first click = desc, second click on same col = asc
      const dir = (th === lastCol && lastDir === 'desc') ? 'asc' : 'desc';

      // Clear sort indicators
      headers.forEach(h => h.classList.remove('sort-desc', 'sort-asc'));
      th.classList.add(dir === 'desc' ? 'sort-desc' : 'sort-asc');

      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {{
        const av = cellValue(a.querySelectorAll('td')[col]);
        const bv = cellValue(b.querySelectorAll('td')[col]);
        return dir === 'desc' ? bv - av : av - bv;
      }});
      rows.forEach(r => tbody.appendChild(r));

      lastCol = th; lastDir = dir;
    }});
  }});
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    run_date = datetime.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] GSIT backtester starting")

    df_raw = (
        pd.read_csv(DATA_PATH, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    close       = df_raw["Close"]
    data_through = df_raw["Date"].max().strftime("%Y-%m-%d")
    print(f"  Data: {df_raw['Date'].min().date()} → {data_through}  ({len(df_raw):,} days)")

    combos = list(product(N_VALUES, K_VALUES, STOP_PCT_VALUES))
    print(f"  Grid: {len(combos)} combinations  (N={N_VALUES}  K={K_VALUES}  Stop%={[f'{s:.0%}' for s in STOP_PCT_VALUES]})")

    results = []
    for n, k, sp in combos:
        r = run(close, n, k, sp)
        if r:
            results.append(r)

    if not results:
        print("  No valid results — widening the parameter grid may help.")
        return

    out = (
        pd.DataFrame(results)
        .query("RDR >= @RDR_THRESHOLD")
        .sort_values(["Total Return %", "RDR"], ascending=[False, False])
        .reset_index(drop=True)
    )

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"backtest_{run_date}.html"
    out_path.write_text(build_html(out, run_date, data_through), encoding="utf-8")

    good_count = (out["RDR"] >= RDR_THRESHOLD).sum()
    best       = out.iloc[0]
    print(f"  Valid results: {len(out)}  |  RDR ≥ {RDR_THRESHOLD}: {good_count}")
    print(f"  Top result: N={int(best['N'])} K={best['K']} Stop={best['Stop %']:.0%}  →  RDR={best['RDR']:.2f}  Final=${best['Final Balance $']:,.2f}  Return={best['Total Return %']:.1f}%  (initial: ${INITIAL_CAPITAL:,})")
    print(f"  Report: {out_path}")


if __name__ == "__main__":
    main()
