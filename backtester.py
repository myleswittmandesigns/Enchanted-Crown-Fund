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
import re
import pandas as pd
from itertools import product
from datetime import datetime
from pathlib import Path

REPO_DIR   = Path(__file__).parent
DATA_PATH  = REPO_DIR / "data" / "GSIT_daily_high_low.csv"
OUT_DIR    = REPO_DIR / "reports"
RULES_PATH = REPO_DIR / "STRATEGY_RULES.md"


def load_strategy_params() -> dict:
    text = RULES_PATH.read_text()

    def extract(symbol: str):
        pattern = rf"\|\s*`{symbol}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"Cannot find parameter `{symbol}` in STRATEGY_RULES.md")
        val = match.group(1)
        return float(val) if "." in val else int(val)

    return {
        "StopPct":         extract("StopPct") / 100,
        "RDR_THRESHOLD":   extract("RDR_THRESHOLD"),
        "MIN_TRADES":      extract("MIN_TRADES"),
        "CAGR_THRESHOLD":  extract("CAGR_THRESHOLD"),
        "WF_TRAIN_YEARS":  extract("WF_TRAIN_YEARS"),
        "WF_TEST_YEARS":   extract("WF_TEST_YEARS"),
        "WF_STEP_MONTHS":  extract("WF_STEP_MONTHS"),
    }

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                        BACKTESTER CONFIGURATION                             ║
# ║  All tunable variables live here. Do not edit below the dashed line.        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── Portfolio (hardcoded by design) ───────────────────────────────────────────
INITIAL_CAPITAL = 5_000     # Starting dollars. Full balance reinvested each trade.

# ── Scoring (hardcoded by design) ─────────────────────────────────────────────
# Score = Total Return % × RDR ÷ SCORE_DIVISOR
# Increase SCORE_DIVISOR to compress score range; decrease to widen it.
SCORE_DIVISOR   = 100

# ── Parameter search grid ─────────────────────────────────────────────────────
# These define the space the backtester explores to find optimal N and K.
# All other rules (StopPct, RDR_THRESHOLD, MIN_TRADES, CAGR_THRESHOLD)
# are read from STRATEGY_RULES.md at runtime.
N_VALUES = list(range(16, 28))                          # Lookback period: [16, 17, ..., 27]
K_VALUES = [round(k * 0.1, 1) for k in range(15, 31)]  # Band width: [1.5, 1.6, ..., 3.0]

# ──────────────────────────────────────────────────────────────────────────────


# ── Indicators ────────────────────────────────────────────────────────────────
def bollinger(close: pd.Series, n: int, k: float):
    sma = close.rolling(n).mean()
    std = close.rolling(n).std(ddof=0)
    return sma, sma + k * std, sma - k * std


# ── Single backtest run ───────────────────────────────────────────────────────
def run(close: pd.Series, n: int, k: float, stop_pct: float, min_trades: int,
        entry_from_idx: int = 0) -> dict | None:
    sma, _, lower = bollinger(close, n, k)
    buy = (close < lower) & (close.shift(1) >= lower.shift(1))

    trades = []
    in_trade    = False
    entry_price = None
    entry_idx   = None

    for i in range(max(n, entry_from_idx), len(close)):
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

    if len(trades) < min_trades:
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
        "Score":          round(total_ret_pct * rdr / SCORE_DIVISOR, 1),
    }


# ── Walk-forward analysis ─────────────────────────────────────────────────────
def walk_forward(df_raw: pd.DataFrame, params: dict, n_values: list, k_values: list) -> list:
    stop_pct     = params["StopPct"]
    train_years  = int(params["WF_TRAIN_YEARS"])
    test_years   = int(params["WF_TEST_YEARS"])
    step_months  = int(params["WF_STEP_MONTHS"])
    dates        = df_raw["Date"]
    close        = df_raw["Close"]
    windows      = []
    t            = dates.min()

    while True:
        train_end_date = t + pd.DateOffset(years=train_years)
        test_end_date  = train_end_date + pd.DateOffset(years=test_years)
        if test_end_date > dates.max():
            break

        # Convert dates to integer row positions
        te_mask = dates >= train_end_date
        xt_mask = dates >= test_end_date
        if not te_mask.any() or not xt_mask.any():
            break
        train_end_idx = int(df_raw[te_mask].index[0])
        test_end_idx  = int(df_raw[xt_mask].index[0])

        # Optimize: find best (N, K) on train period
        best_score  = -1
        best_n, best_k = n_values[0], k_values[0]
        best_train  = None
        for n in n_values:
            for k in k_values:
                r = run(close.iloc[:train_end_idx], n, k, stop_pct, 1)
                if r and r["Score"] > best_score:
                    best_score = r["Score"]
                    best_n, best_k = n, k
                    best_train = r

        # Evaluate best params on test period (use full history for Bollinger warmup)
        test_r = run(close.iloc[:test_end_idx], best_n, best_k, stop_pct, 1,
                     entry_from_idx=train_end_idx)

        # Annualize test return over the actual test window length
        test_span_yrs = (dates.iloc[test_end_idx - 1] - dates.iloc[train_end_idx]).days / 365.25
        if test_r and test_span_yrs > 0:
            test_cagr = round(
                ((test_r["Final Balance $"] / INITIAL_CAPITAL) ** (1 / test_span_yrs) - 1) * 100, 1
            )
        else:
            test_cagr = None

        windows.append({
            "Window":         len(windows) + 1,
            "Train Start":    t.strftime("%Y-%m"),
            "Train End":      train_end_date.strftime("%Y-%m"),
            "Test Start":     train_end_date.strftime("%Y-%m"),
            "Test End":       test_end_date.strftime("%Y-%m"),
            "Best N":         best_n,
            "Best K":         round(best_k, 1),
            "Train Return %": round(best_train["Total Return %"], 1) if best_train else None,
            "Train Score":    round(best_train["Score"], 1)          if best_train else None,
            "Test Trades":    test_r["Trades"]                        if test_r    else 0,
            "Test Return %":  round(test_r["Total Return %"], 1)      if test_r    else None,
            "Test CAGR %":    test_cagr,
        })

        t = t + pd.DateOffset(months=step_months)

    return windows


# ── Heat map ──────────────────────────────────────────────────────────────────
def build_heatmap(df_all: pd.DataFrame, df_filtered: pd.DataFrame, n_values: list, k_values: list) -> str:
    # All scores for lookup
    score_map = {}
    for _, row in df_all.iterrows():
        score_map[(int(row["N"]), round(row["K"], 1))] = row["Score"]

    # Only cells that passed ALL filters get colored
    valid = set()
    for _, row in df_filtered.iterrows():
        valid.add((int(row["N"]), round(row["K"], 1)))

    valid_scores = [score_map[k] for k in valid if k in score_map]
    min_s = min(valid_scores) if valid_scores else 0
    max_s = max(valid_scores) if valid_scores else 1

    best_row = df_all.loc[df_all["Score"].idxmax()]
    best_n   = int(best_row["N"])
    best_k   = round(best_row["K"], 1)

    def cell_color(key, score):
        if key not in valid:
            return "#e0e0e0", "#aaa"
        t = (score - min_s) / (max_s - min_s) if max_s > min_s else 1.0
        r = int(200 * (1 - t) + 21  * t)
        g = int(230 * (1 - t) + 87  * t)
        b = int(200 * (1 - t) + 36  * t)
        text = "#fff" if t > 0.55 else "#222"
        return f"rgb({r},{g},{b})", text

    html = ['<table class="heatmap"><thead><tr>']
    html.append('<th class="hm-corner">N \\ K</th>')
    for k in k_values:
        html.append(f'<th class="hm-kh">{k:.1f}</th>')
    html.append("</tr></thead><tbody>")

    for n in sorted(n_values):
        html.append(f'<tr><th class="hm-nh">{n}</th>')
        for k in k_values:
            key = (n, round(k, 1))
            if key in score_map:
                score  = score_map[key]
                bg, fg = cell_color(key, score)
                label  = f"{score:.0f}" if key in valid else "·"
            else:
                bg, fg = "#e0e0e0", "#aaa"
                label  = "·"
            is_best = (n == best_n and round(k, 1) == best_k)
            outline = ' outline: 3px solid #111; outline-offset: -3px; z-index:1; position:relative;' if is_best else ''
            weight  = ' font-weight:700;' if is_best else ''
            html.append(f'<td style="background:{bg}; color:{fg};{outline}{weight}">{label}</td>')
        html.append("</tr>")

    html.append("</tbody></table>")
    return "".join(html)


# ── HTML report ───────────────────────────────────────────────────────────────
def build_wf_html(windows: list, train_yrs: int, test_yrs: int, step_mo: int, cagr_threshold: float) -> str:
    if not windows:
        return "<p>No walk-forward windows generated.</p>"

    profitable   = [w for w in windows if w["Test Return %"] is not None and w["Test Return %"] > 0]
    cagr_passing = [w for w in windows if w["Test CAGR %"] is not None and w["Test CAGR %"] >= cagr_threshold]
    test_returns = [w["Test Return %"] for w in windows if w["Test Return %"] is not None]
    test_cagrs   = [w["Test CAGR %"]   for w in windows if w["Test CAGR %"]   is not None]
    avg_ret  = round(sum(test_returns) / len(test_returns), 1) if test_returns else None
    avg_cagr = round(sum(test_cagrs)   / len(test_cagrs),   1) if test_cagrs   else None

    from collections import Counter
    param_counts = Counter((w["Best N"], w["Best K"]) for w in windows)
    most_common_n, most_common_k = param_counts.most_common(1)[0][0]

    rows = []
    for w in windows:
        has_test  = w["Test Return %"] is not None
        positive  = has_test and w["Test Return %"] > 0
        beats_cagr = has_test and w["Test CAGR %"] is not None and w["Test CAGR %"] >= cagr_threshold
        row_cls   = ' class="wf-pass"' if beats_cagr else (' class="wf-ok"' if positive else ' class="wf-fail"')
        test_ret_str  = f'{w["Test Return %"]:+.1f}%' if has_test else '—'
        test_cagr_str = f'{w["Test CAGR %"]:+.1f}%'  if w["Test CAGR %"] is not None else '—'
        rows.append(
            f'<tr{row_cls}>'
            f'<td>{w["Window"]}</td>'
            f'<td>{w["Train Start"]} → {w["Train End"]}</td>'
            f'<td>{w["Test Start"]} → {w["Test End"]}</td>'
            f'<td>{w["Best N"]}</td>'
            f'<td>{w["Best K"]:.1f}</td>'
            f'<td>{w["Train Return %"]:+.1f}%</td>'
            f'<td>{w["Train Score"]:.1f}</td>'
            f'<td>{w["Test Trades"]}</td>'
            f'<td>{test_ret_str}</td>'
            f'<td>{test_cagr_str}</td>'
            f'</tr>'
        )

    return f"""
<div class="wf-section">
  <h2>🔄 Walk-Forward Analysis</h2>
  <p class="meta">Train: {train_yrs}yr &nbsp;·&nbsp; Test: {test_yrs}yr &nbsp;·&nbsp; Step: {step_mo}mo &nbsp;·&nbsp; {len(windows)} windows &nbsp;·&nbsp; Settings from STRATEGY_RULES.md</p>
  <div class="summary">
    <div class="card">
      <div class="label">Profitable Windows</div>
      <div class="value">{len(profitable)}/{len(windows)}</div>
    </div>
    <div class="card">
      <div class="label">Beat CAGR {cagr_threshold:.0f}% Windows</div>
      <div class="value">{len(cagr_passing)}/{len(windows)}</div>
    </div>
    <div class="card">
      <div class="label">Avg Out-of-Sample Return</div>
      <div class="value">{avg_ret:+.1f}%</div>
    </div>
    <div class="card">
      <div class="label">Avg Out-of-Sample CAGR</div>
      <div class="value">{avg_cagr:+.1f}%</div>
    </div>
    <div class="card">
      <div class="label">Most Stable Params</div>
      <div class="value">N={most_common_n}, K={most_common_k:.1f}</div>
      <div class="sub">appeared most across windows</div>
    </div>
  </div>
  <div class="table-wrap">
  <table>
    <thead><tr>
      <th>#</th><th>Train Period</th><th>Test Period</th>
      <th>Best N</th><th>Best K</th>
      <th>Train Return</th><th>Train Score</th>
      <th>Test Trades</th><th>Test Return</th><th>Test CAGR</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  </div>
  <div class="legend">
    <span class="wf-pass-swatch"></span> Beats CAGR threshold &nbsp;·&nbsp;
    <span class="wf-ok-swatch"></span> Positive return &nbsp;·&nbsp;
    <span class="wf-fail-swatch"></span> Negative / no trades
  </div>
</div>
"""


def build_html(df: pd.DataFrame, df_all: pd.DataFrame, wf_windows: list,
               run_date: str, data_through: str, params: dict) -> str:
    RDR_THRESHOLD   = params["RDR_THRESHOLD"]
    MIN_TRADES      = params["MIN_TRADES"]
    CAGR_THRESHOLD  = params["CAGR_THRESHOLD"]
    STOP_PCT_VALUES = [params["StopPct"]]
    WF_TRAIN_YEARS  = int(params["WF_TRAIN_YEARS"])
    WF_TEST_YEARS   = int(params["WF_TEST_YEARS"])
    WF_STEP_MONTHS  = int(params["WF_STEP_MONTHS"])
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
            f'<td>{row["CAGR %"]:.1f}%</td>'
            f'<td><strong>{row["Score"]:.1f}</strong></td>'
        )
        rows_html.append(f"<tr{tr_class}>{cells}</tr>")

    good_count  = sum(1 for _, r in df.iterrows() if isinstance(r["RDR"], float) and r["RDR"] >= RDR_THRESHOLD)
    best_rdr    = df.loc[df["RDR"].idxmax()]
    best_ret    = df.loc[df["Total Return $"].idxmax()]
    best_score  = df.loc[df["Score"].idxmax()]

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
  .config {{ background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 8px;
             padding: 0.75rem 1.1rem; margin-bottom: 1.5rem; font-size: 0.82rem; color: #444; }}
  .config strong {{ color: #222; }}
  .config-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
                  gap: 0.3rem 2rem; margin-top: 0.4rem; }}
  .tip-icon {{ font-size: 0.7rem; color: #999; margin-left: 3px;
               vertical-align: super; cursor: default; }}
  .wf-section {{ margin-bottom: 2rem; }}
  .wf-section h2 {{ font-size: 1rem; margin-bottom: 0.25rem; }}
  tr.wf-pass td {{ background: #f0fff4; }}
  tr.wf-ok   td {{ background: #fffde7; }}
  tr.wf-fail td {{ background: #fdf2f2; color: #999; }}
  .wf-pass-swatch, .wf-ok-swatch, .wf-fail-swatch {{
    display: inline-block; width: 12px; height: 12px;
    border-radius: 2px; vertical-align: middle; margin-right: 3px; }}
  .wf-pass-swatch {{ background: #f0fff4; border: 1px solid #b2dfdb; }}
  .wf-ok-swatch   {{ background: #fffde7; border: 1px solid #ffe082; }}
  .wf-fail-swatch {{ background: #fdf2f2; border: 1px solid #ffcdd2; }}
  .heatmap-section {{ margin-bottom: 2rem; }}
  .heatmap-section h2 {{ font-size: 1rem; margin-bottom: 0.25rem; }}
  .heatmap-caption {{ font-size: 0.8rem; color: #666; margin-bottom: 0.6rem; }}
  .heatmap-wrap {{ overflow-x: auto; }}
  table.heatmap {{ border-collapse: collapse; font-size: 0.72rem; }}
  table.heatmap td, table.heatmap th {{ width: 36px; height: 28px; text-align: center;
    padding: 0; border: 1px solid #fff; }}
  table.heatmap th.hm-corner {{ background: #f0f0f0; font-weight: 600; font-size: 0.7rem; width: 36px; }}
  table.heatmap th.hm-kh {{ background: #f0f0f0; font-weight: 500; }}
  table.heatmap th.hm-nh {{ background: #f0f0f0; font-weight: 500; text-align: center; }}
  .heatmap-legend {{ display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem;
    color: #666; margin-top: 0.4rem; }}
  .heatmap-legend-bar {{ width: 120px; height: 12px; border-radius: 3px;
    background: linear-gradient(to right, rgb(200,230,200), rgb(21,87,36)); }}
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

<div class="config">
  <strong>⚙️ Active Configuration</strong>
  <span style="font-size:0.78rem; color:#888; margin-left:0.75rem;">Filter rules are read from <code>STRATEGY_RULES.md</code>. Search grid and portfolio settings are in <code>backtester.py</code>.</span>
  <div class="config-grid">
    <div><strong>INITIAL_CAPITAL</strong> &nbsp;${INITIAL_CAPITAL:,}</div>
    <div><strong>RDR_THRESHOLD</strong> &nbsp;{RDR_THRESHOLD}</div>
    <div><strong>CAGR_THRESHOLD</strong> &nbsp;{CAGR_THRESHOLD}%</div>
    <div><strong>MIN_TRADES</strong> &nbsp;{MIN_TRADES}</div>
    <div><strong>SCORE_DIVISOR</strong> &nbsp;{SCORE_DIVISOR}</div>
    <div><strong>N_VALUES</strong> &nbsp;{N_VALUES[0]}–{N_VALUES[-1]} (every {N_VALUES[1]-N_VALUES[0]})</div>
    <div><strong>K_VALUES</strong> &nbsp;{K_VALUES[0]}–{K_VALUES[-1]} (every {round(K_VALUES[1]-K_VALUES[0],1) if len(K_VALUES) > 1 else "—"})</div>
    <div><strong>STOP_PCT_VALUES</strong> &nbsp;{", ".join(f"{s:.0%}" for s in STOP_PCT_VALUES)}</div>
    <div><strong>Entry</strong> &nbsp;Close crosses below lower BB</div>
    <div><strong>Take profit</strong> &nbsp;Close ≥ SMA</div>
    <div><strong>Stop loss</strong> &nbsp;Close ≤ entry × (1 − Stop%)</div>
    <div><strong>Score formula</strong> &nbsp;Total Return % × RDR ÷ {SCORE_DIVISOR}</div>
  </div>
</div>

<div class="summary">
  <div class="card">
    <div class="label">Combinations Tested</div>
    <div class="value">{len(df)}</div>
  </div>
  <div class="card">
    <div class="label">RDR ≥ {RDR_THRESHOLD} &amp; CAGR ≥ {CAGR_THRESHOLD}%</div>
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
    <div class="label">Best Score</div>
    <div class="value">{best_score["Score"]:.1f}</div>
    <div class="sub">N={int(best_score["N"])} K={best_score["K"]:.1f} Stop={best_score["Stop %"]:.0%}</div>
  </div>
  <div class="card">
    <div class="label">Initial Capital</div>
    <div class="value">${INITIAL_CAPITAL:,}</div>
    <div class="sub">compounded across all trades · edit INITIAL_CAPITAL in backtester.py</div>
  </div>
</div>

{build_wf_html(wf_windows, WF_TRAIN_YEARS, WF_TEST_YEARS, WF_STEP_MONTHS, CAGR_THRESHOLD)}

<div class="heatmap-section">
  <h2>📊 Score Heat Map — N × K</h2>
  <p class="heatmap-caption">
    Each cell = composite Score (Total Return % × RDR ÷ {SCORE_DIVISOR}).
    Gray cells did not meet the RDR ≥ {RDR_THRESHOLD} threshold.
    <strong>Bold outline = current strategy params (N={best_score["N"]:.0f}, K={best_score["K"]:.1f})</strong>.
  </p>
  <div class="heatmap-wrap">
    {build_heatmap(df_all, df, N_VALUES, K_VALUES)}
  </div>
  <div class="heatmap-legend">
    <span>Low score</span>
    <div class="heatmap-legend-bar"></div>
    <span>High score</span>
    &nbsp;·&nbsp; <span style="display:inline-block;width:14px;height:14px;background:#e0e0e0;border:1px solid #ccc;vertical-align:middle;"></span> Below RDR threshold
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
    <th data-tip="Compound Annual Growth Rate\nCAGR = (Final ÷ Initial)^(1÷years) − 1\nAnnualizes total return across the full data span.\nAllows apples-to-apples comparison across time periods.">CAGR %<span class="tip-icon">ⓘ</span></th>
    <th data-tip="Composite Score\nScore = Total Return % × RDR ÷ 100\nRewards strategies that are both high-return\nand risk-disciplined. Higher is better.">Score<span class="tip-icon">ⓘ</span></th>
  </tr>
</thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</div>

<div class="legend">Score = Total Return % × RDR ÷ 100 &nbsp;·&nbsp; RDR = Total Return ÷ Max Drawdown &nbsp;·&nbsp; Sorted by Score descending</div>

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

    params         = load_strategy_params()
    stop_pct       = params["StopPct"]
    RDR_THRESHOLD  = params["RDR_THRESHOLD"]
    MIN_TRADES     = params["MIN_TRADES"]
    CAGR_THRESHOLD = params["CAGR_THRESHOLD"]
    STOP_PCT_VALUES = [stop_pct]

    df_raw = (
        pd.read_csv(DATA_PATH, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    close        = df_raw["Close"]
    data_through = df_raw["Date"].max().strftime("%Y-%m-%d")
    print(f"  Data: {df_raw['Date'].min().date()} → {data_through}  ({len(df_raw):,} days)")

    combos = list(product(N_VALUES, K_VALUES, STOP_PCT_VALUES))
    print(f"  Grid: {len(combos)} combinations  (N={N_VALUES}  K={K_VALUES}  Stop%={[f'{s:.0%}' for s in STOP_PCT_VALUES]})")

    results = []
    for n, k, sp in combos:
        r = run(close, n, k, sp, MIN_TRADES)
        if r:
            results.append(r)

    if not results:
        print("  No valid results — widening the parameter grid may help.")
        return

    years  = (df_raw["Date"].max() - df_raw["Date"].min()).days / 365.25
    df_all = pd.DataFrame(results)
    df_all["CAGR %"] = ((df_all["Final Balance $"] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100
    df_all["CAGR %"] = df_all["CAGR %"].round(1)
    out = (
        df_all
        .query("RDR >= @RDR_THRESHOLD and `CAGR %` >= @CAGR_THRESHOLD")
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )

    print("  Running walk-forward analysis...")
    wf_windows = walk_forward(df_raw, params, N_VALUES, K_VALUES)
    print(f"  Walk-forward: {len(wf_windows)} windows completed")

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"backtest_{run_date}.html"
    out_path.write_text(build_html(out, df_all, wf_windows, run_date, data_through, params), encoding="utf-8")

    good_count = (out["RDR"] >= RDR_THRESHOLD).sum()
    best       = out.iloc[0]
    print(f"  Valid results: {len(out)}  |  RDR ≥ {RDR_THRESHOLD}: {good_count}")
    print(f"  Top result: N={int(best['N'])} K={best['K']} Stop={best['Stop %']:.0%}  →  RDR={best['RDR']:.2f}  Final=${best['Final Balance $']:,.2f}  Return={best['Total Return %']:.1f}%  (initial: ${INITIAL_CAPITAL:,})")
    print(f"  Report: {out_path}")


if __name__ == "__main__":
    main()
