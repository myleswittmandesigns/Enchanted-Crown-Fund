#!/usr/bin/env python3
"""
GSIT Mean Reversion Backtester — headless, no UI required.

Grid-searches N, K, and StopPct combinations against the full GSIT price history.
Entry:  first day close crosses below the lower Bollinger Band
Exit:   close crosses above upper BB (take profit)  OR  close <= entry × (1 - StopPct) (stop loss)

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
        "WF_MIN_TRADES":   extract("WF_MIN_TRADES"),
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
N_VALUES = list(range(16, 55))                          # Lookback period: [16, 17, ..., 54]
K_VALUES = [round(k * 0.1, 1) for k in range(15, 33)]  # Band width: [1.5, 1.6, ..., 3.2]
STOP_PCT_VALUES = [0.20, 0.30, 0.40, 0.50, 0.60]       # Stop loss: [20%, 30%, 40%, 50%, 60%]

# ──────────────────────────────────────────────────────────────────────────────


# ── Indicators ────────────────────────────────────────────────────────────────
def bollinger_base(close: pd.Series, n: int):
    """Compute SMA and STD for a given N — k-independent. Call once per N, reuse across K values."""
    sma = close.rolling(n).mean()
    std = close.rolling(n).std(ddof=0)
    return sma, std


def bollinger(close: pd.Series, n: int, k: float):
    sma, std = bollinger_base(close, n)
    return sma, sma + k * std, sma - k * std


# ── Single backtest run ───────────────────────────────────────────────────────
def run(close: pd.Series, n: int, k: float, stop_pct: float, min_trades: int,
        entry_from_idx: int = 0, _precomp: tuple = None) -> dict | None:
    """_precomp: optional (sma, upper, lower) from indicator cache — avoids recomputation."""
    if _precomp is not None:
        sma, upper, lower = _precomp
    else:
        sma, upper, lower = bollinger(close, n, k)
    buy = (close < lower) & (close.shift(1) >= lower.shift(1))

    # Single-pass: signal detection + compounding balance + daily mark-to-market
    trades       = []
    daily_equity = []           # portfolio value at every bar — used for true max drawdown
    balance      = INITIAL_CAPITAL
    shares       = 0.0
    in_trade     = False
    entry_price  = entry_idx = None
    bal_at_entry = INITIAL_CAPITAL
    wins_count   = 0
    win_pnls     = []
    loss_pnls    = []
    stop_hits    = 0
    trade_rets   = []

    for i in range(max(n, entry_from_idx), len(close)):
        c = close.iloc[i]
        if not in_trade:
            if buy.iloc[i]:
                in_trade     = True
                entry_price  = c
                entry_idx    = i
                bal_at_entry = balance
                shares       = balance / c
        else:
            # Take profit: close crosses above upper Bollinger Band
            tp = c > upper.iloc[i] and close.iloc[i - 1] <= upper.iloc[i - 1]
            sl = c <= entry_price * (1 - stop_pct)
            if tp or sl:
                balance  = shares * c
                ret_pct  = (c / entry_price - 1) * 100
                pnl      = balance - bal_at_entry
                trades.append({"entry": entry_price, "exit": c,
                                "hold": i - entry_idx, "reason": "tp" if tp else "sl"})
                trade_rets.append(ret_pct)
                if pnl > 0:
                    wins_count += 1
                    win_pnls.append(pnl)
                else:
                    loss_pnls.append(pnl)
                if not tp:
                    stop_hits += 1
                shares   = 0.0
                in_trade = False

        # Mark-to-market: value of portfolio at today's close
        daily_equity.append(shares * c if in_trade else balance)

    if len(trades) < min_trades:
        return None

    final_balance = shares * close.iloc[-1] if in_trade else balance
    total_return  = final_balance - INITIAL_CAPITAL
    total_ret_pct = total_return / INITIAL_CAPITAL * 100
    num_trades    = len(trades)
    win_rate      = wins_count / num_trades * 100
    avg_win       = sum(win_pnls)  / len(win_pnls)  if win_pnls  else 0.0
    avg_loss      = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    avg_ret_pct   = sum(trade_rets) / len(trade_rets)
    avg_hold      = sum(t["hold"] for t in trades) / len(trades)

    # True max drawdown from daily mark-to-market equity curve
    eq_s       = pd.Series(daily_equity)
    peak       = eq_s.cummax()
    max_dd     = float((peak - eq_s).max())
    max_dd_pct = max_dd / peak.max() * 100 if peak.max() > 0 else 0.0

    rdr = min(round(total_return / max_dd, 2), 999.0) if max_dd > 0 else 999.0  # always cap at 999

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
def walk_forward(df_raw: pd.DataFrame, params: dict, n_values: list, k_values: list,
                 stop_values: list = None) -> list:
    if stop_values is None:
        stop_values = [params["StopPct"]]
    train_years   = int(params["WF_TRAIN_YEARS"])
    test_years    = int(params["WF_TEST_YEARS"])
    step_months   = int(params["WF_STEP_MONTHS"])
    wf_min_trades = int(params["WF_MIN_TRADES"])
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

        # Optimize: find best (N, K, Stop) on train period
        best_score  = -1
        best_n, best_k, best_stop = n_values[0], k_values[0], stop_values[0]
        best_train  = None
        # Precompute SMA+STD per N for this training window
        _wf_cache = {}
        for n in n_values:
            _sma, _std = bollinger_base(close.iloc[:train_end_idx], n)
            _wf_cache[n] = (_sma, _std)
        for n in n_values:
            _sma, _std = _wf_cache[n]
            for k in k_values:
                _upper = _sma + k * _std
                _lower = _sma - k * _std
                for stop_pct in stop_values:
                    r = run(close.iloc[:train_end_idx], n, k, stop_pct, wf_min_trades,
                            _precomp=(_sma, _upper, _lower))
                    if r and r["Score"] > best_score:
                        best_score = r["Score"]
                        best_n, best_k, best_stop = n, k, stop_pct
                        best_train = r

        # Evaluate best params on test period (use full history for Bollinger warmup)
        test_r = run(close.iloc[:test_end_idx], best_n, best_k, best_stop, 1,
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
            "Best Stop":      f"{best_stop:.0%}",
            "Train Return %": round(best_train["Total Return %"], 1) if best_train else None,
            "Train Score":    round(best_train["Score"], 1)          if best_train else None,
            "Test Trades":    test_r["Trades"]                        if test_r    else 0,
            "Test Return %":  round(test_r["Total Return %"], 1)      if test_r    else None,
            "Test CAGR %":    test_cagr,
        })

        t = t + pd.DateOffset(months=step_months)

    return windows


# ── Heat map ──────────────────────────────────────────────────────────────────
def find_hotspots(df_all: pd.DataFrame, n_values: list, k_values: list,
                  stop_values: list, top_pct: float = 0.10) -> list:
    """
    Find connected high-score regions in (N, K, Stop) space using 3D BFS clustering.
    Returns clusters sorted by peak score, each with bounding box and centroid.
    """
    if df_all.empty or len(df_all) < 5:
        return []

    threshold = df_all["Score"].quantile(1 - top_pct)
    hot = df_all[df_all["Score"] >= threshold]
    if hot.empty:
        return []

    n_sorted = sorted(set(int(n) for n in n_values))
    k_sorted = sorted(set(round(k, 1) for k in k_values))
    s_sorted = sorted(set(round(s, 2) for s in stop_values))

    n_idx = {n: i for i, n in enumerate(n_sorted)}
    k_idx = {k: i for i, k in enumerate(k_sorted)}
    s_idx = {s: i for i, s in enumerate(s_sorted)}

    hot_set: dict = {}
    for _, row in hot.iterrows():
        key = (n_idx[int(row["N"])], k_idx[round(row["K"], 1)], s_idx[round(row["Stop %"], 2)])
        hot_set[key] = row["Score"]

    visited: set = set()
    clusters: list = []

    for start in hot_set:
        if start in visited:
            continue
        cluster_pts: list = []
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            cluster_pts.append(node)
            ni, ki, si = node
            for dn, dk, ds in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                nb = (ni+dn, ki+dk, si+ds)
                if nb in hot_set and nb not in visited:
                    queue.append(nb)
        clusters.append(cluster_pts)

    clusters.sort(key=lambda c: max(hot_set[p] for p in c), reverse=True)

    n_rev = {i: n for n, i in n_idx.items()}
    k_rev = {i: k for k, i in k_idx.items()}
    s_rev = {i: s for s, i in s_idx.items()}

    result = []
    for cluster in clusters:
        ns     = [n_rev[p[0]] for p in cluster]
        ks     = [k_rev[p[1]] for p in cluster]
        ss     = [s_rev[p[2]] for p in cluster]
        scores = [hot_set[p] for p in cluster]
        peak_i = scores.index(max(scores))
        result.append({
            "size":       len(cluster),
            "peak_score": max(scores),
            "peak_n":     n_rev[cluster[peak_i][0]],
            "peak_k":     k_rev[cluster[peak_i][1]],
            "peak_stop":  s_rev[cluster[peak_i][2]],
            "n_range":    (min(ns), max(ns)),
            "k_range":    (min(ks), max(ks)),
            "stop_range": (min(ss), max(ss)),
        })
    return result


def build_heatmap_3d(df_all: pd.DataFrame, df_filtered: pd.DataFrame,
                     n_values: list, k_values: list, stop_values: list) -> str:
    """
    Interactive 3D heat map: N × K grid with a tab selector per stop value.
    All stop panels share the same color scale for cross-stop comparison.
    """
    score_map: dict = {}
    for _, row in df_all.iterrows():
        score_map[(int(row["N"]), round(row["K"], 1), round(row["Stop %"], 2))] = row["Score"]

    valid_set: set = set()
    for _, row in df_filtered.iterrows():
        valid_set.add((int(row["N"]), round(row["K"], 1), round(row["Stop %"], 2)))

    valid_scores = [score_map[k] for k in valid_set if k in score_map]
    min_s = min(valid_scores) if valid_scores else 0
    max_s = max(valid_scores) if valid_scores else 1

    # Global best for gold highlight
    global_best = None
    if not df_filtered.empty:
        gb = df_filtered.loc[df_filtered["Score"].idxmax()]
        global_best = (int(gb["N"]), round(gb["K"], 1), round(gb["Stop %"], 2))

    k_sorted = sorted(set(round(k, 1) for k in k_values))
    n_sorted = sorted(set(int(n) for n in n_values))
    s_sorted = sorted(set(round(s, 2) for s in stop_values))

    def cell_color(score, is_global_best):
        if score is None:
            return 'background:#e0e0e0;'
        t = (score - min_s) / (max_s - min_s) if max_s > min_s else 0.5
        r = int(200 - t * 179)
        g = int(230 - t * 143)
        b = int(200 - t * 164)
        border = ' outline:3px solid #FFD700; outline-offset:-2px; z-index:1; position:relative;' if is_global_best else ''
        return f'background:rgb({r},{g},{b});{border}'

    tabs_html = []
    panels_html = []

    for si, stop_pct in enumerate(s_sorted):
        stop_label = f"{stop_pct:.0%}"
        is_first   = si == 0
        tabs_html.append(
            f'<button class="hm3-tab{"  hm3-active" if is_first else ""}" '
            f'onclick="showStop({si})" id="hm3-btn-{si}">{stop_label}</button>'
        )

        # Transposed layout: K as rows (18), N as columns (39)
        # N header row with rotated labels to keep columns narrow
        n_headers = ''.join(f'<th class="hm-nh"><div class="hm-n-lbl">{n}</div></th>' for n in n_sorted)
        header = f'<th class="hm-corner">K \\ N</th>{n_headers}'

        rows = []
        for k in k_sorted:
            cells = [f'<th class="hm-kh">{k:.1f}</th>']
            for n in n_sorted:
                key   = (n, round(k, 1), round(stop_pct, 2))
                score = score_map.get(key)
                valid = key in valid_set
                is_gb = (key == global_best)
                style = cell_color(score if valid else None, is_gb)
                tip   = (f'N={n} K={k:.1f} Stop={stop_label}&#10;'
                         + (f'Score={score:.1f}' if (score and valid) else 'Below filters'))
                cells.append(f'<td style="{style}" title="{tip}"></td>')
            rows.append(f'<tr>{"".join(cells)}</tr>')

        display = '' if is_first else ' style="display:none"'
        panels_html.append(
            f'<div id="hm3-panel-{si}" class="hm3-panel"{display}>'
            f'<table class="heatmap"><thead><tr>{header}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )

    js = """
<script>
function showStop(idx) {
  var panels = document.querySelectorAll('.hm3-panel');
  var btns   = document.querySelectorAll('.hm3-tab');
  for (var i = 0; i < panels.length; i++) {
    panels[i].style.display = (i === idx) ? '' : 'none';
    btns[i].classList.toggle('hm3-active', i === idx);
  }
}
</script>"""

    tabs_div   = f'<div class="hm3-tabs">{"".join(tabs_html)}</div>'
    panels_div = "".join(panels_html)
    return f'{tabs_div}{panels_div}{js}'


# ── HTML report ───────────────────────────────────────────────────────────────
def build_wf_html(windows: list, train_yrs: int, test_yrs: int, step_mo: int, cagr_threshold: float, wf_min_trades: int = 1) -> str:
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
            f'<td>{w.get("Best Stop","—")}</td>'
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
  <p class="meta">Train: {train_yrs}yr &nbsp;·&nbsp; Test: {test_yrs}yr &nbsp;·&nbsp; Step: {step_mo}mo &nbsp;·&nbsp; {len(windows)} windows &nbsp;·&nbsp; Min trades per window: {wf_min_trades} &nbsp;·&nbsp; Settings from STRATEGY_RULES.md</p>
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
      <th title="Window number — each window slides forward by {step_mo} months">#</th>
      <th title="The {train_yrs}-year period used to optimize N and K. The backtester finds the highest-scoring parameter combination within this window.">Train Period</th>
      <th title="The {test_yrs}-year out-of-sample period immediately following training. The best parameters from training are applied here without re-optimization — this is the true performance test.">Test Period</th>
      <th title="The lookback period (days) that scored highest during training. Used as-is on the test window.">Best N</th>
      <th title="The Bollinger Band width multiplier that scored highest during training. Used as-is on the test window.">Best K</th>
      <th title="The stop loss percentage that scored highest during training. Used as-is on the test window.">Best Stop</th>
      <th title="Total return of the best N/K combination on the training period. Higher is expected — the model was optimized here. Use this to sanity-check, not to evaluate.">Train Return</th>
      <th title="Composite score on the training period: Total Return % × RDR ÷ 100. Used to select the best N/K for that window.">Train Score</th>
      <th title="Number of completed trades fired during the test (out-of-sample) period. Low counts reduce statistical confidence.">Test Trades</th>
      <th title="Total return during the out-of-sample test period using the parameters chosen in training. This is the real signal — consistent positive returns across windows indicate a robust strategy.">Test Return</th>
      <th title="Annualized return during the test period. Highlighted green if it meets the CAGR threshold in STRATEGY_RULES.md.">Test CAGR</th>
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


def _build_hotspot_html(hotspots: list) -> str:
    """Render hotspot clusters as an HTML section."""
    if not hotspots:
        return ''
    rows = []
    for i, h in enumerate(hotspots[:5]):   # show top 5 clusters
        rows.append(
            f'<tr>'
            f'<td>{"★ " if i == 0 else ""}Cluster {i+1}</td>'
            f'<td>{h["peak_score"]:.1f}</td>'
            f'<td>N={h["peak_n"]}  K={h["peak_k"]:.1f}  Stop={h["peak_stop"]:.0%}</td>'
            f'<td>N {h["n_range"][0]}–{h["n_range"][1]}</td>'
            f'<td>K {h["k_range"][0]:.1f}–{h["k_range"][1]:.1f}</td>'
            f'<td>Stop {h["stop_range"][0]:.0%}–{h["stop_range"][1]:.0%}</td>'
            f'<td>{h["size"]} cells</td>'
            f'</tr>'
        )
    return f"""
<div class="hotspot-section">
  <h2>🔥 Parameter Hotspots — Top Scoring Regions</h2>
  <p style="font-size:0.82rem;color:#666;margin-bottom:0.6rem;">
    Connected clusters of top-10% scoring combinations in (N, K, Stop) space.
    A wide cluster = robust plateau. A narrow cluster = fragile spike. Prefer wide.
  </p>
  <div class="table-wrap">
  <table class="hotspot-table">
    <thead><tr>
      <th>Cluster</th><th>Peak Score</th><th>Peak (N, K, Stop)</th>
      <th>N Range</th><th>K Range</th><th>Stop Range</th><th>Size</th>
    </tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  </div>
</div>"""


def build_html(df: pd.DataFrame, df_all: pd.DataFrame, wf_windows: list,
               run_date: str, data_through: str, params: dict,
               n_values: list = None, k_values: list = None,
               stop_values: list = None) -> str:
    RDR_THRESHOLD   = params["RDR_THRESHOLD"]
    MIN_TRADES      = params["MIN_TRADES"]
    CAGR_THRESHOLD  = params["CAGR_THRESHOLD"]
    _stop_values    = stop_values if stop_values is not None else STOP_PCT_VALUES
    WF_TRAIN_YEARS  = int(params["WF_TRAIN_YEARS"])
    WF_TEST_YEARS   = int(params["WF_TEST_YEARS"])
    WF_STEP_MONTHS  = int(params["WF_STEP_MONTHS"])
    WF_MIN_TRADES   = int(params["WF_MIN_TRADES"])
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
    if df.empty:
        # No combinations passed filters — build a minimal "no results" report
        best_rdr   = best_ret = best_score = None
    else:
        best_rdr   = df.loc[df["RDR"].idxmax()]
        best_ret   = df.loc[df["Total Return $"].idxmax()]
        best_score = df.loc[df["Score"].idxmax()]

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
  .wf-section thead th[title] {{ cursor: help; border-bottom: 1px dotted #aaa; }}
  tr.wf-pass td {{ background: #f0fff4; }}
  tr.wf-ok   td {{ background: #fffde7; }}
  tr.wf-fail td {{ background: #fdf2f2; color: #999; }}
  .wf-pass-swatch, .wf-ok-swatch, .wf-fail-swatch {{
    display: inline-block; width: 12px; height: 12px;
    border-radius: 2px; vertical-align: middle; margin-right: 3px; }}
  .wf-pass-swatch {{ background: #f0fff4; border: 1px solid #b2dfdb; }}
  .wf-ok-swatch   {{ background: #fffde7; border: 1px solid #ffe082; }}
  .wf-fail-swatch {{ background: #fdf2f2; border: 1px solid #ffcdd2; }}
  .heatmap-section {{ margin-bottom: 1.5rem; }}
  .heatmap-section h2 {{ font-size: 1rem; margin-bottom: 0.25rem; }}
  .heatmap-caption {{ font-size: 0.8rem; color: #666; margin-bottom: 0.5rem; }}
  .heatmap-wrap {{ overflow-x: auto; }}
  table.heatmap {{ border-collapse: collapse; font-size: 0.65rem; }}
  table.heatmap td {{ width: 16px; min-width: 16px; height: 18px; padding: 0;
    border: 1px solid #fff; cursor: default; }}
  table.heatmap th {{ padding: 0; border: 1px solid #fff; background: #f0f0f0; }}
  table.heatmap th.hm-corner {{ font-weight: 600; font-size: 0.65rem; width: 32px;
    min-width: 32px; height: 44px; vertical-align: bottom; padding: 2px 3px; white-space: nowrap; }}
  table.heatmap th.hm-kh {{ font-weight: 500; font-size: 0.65rem; width: 32px;
    min-width: 32px; height: 18px; text-align: right; padding: 0 4px 0 0; white-space: nowrap; }}
  table.heatmap th.hm-nh {{ width: 16px; min-width: 16px; height: 44px; vertical-align: bottom; }}
  .hm-n-lbl {{ writing-mode: vertical-rl; transform: rotate(180deg);
    font-size: 0.6rem; font-weight: 500; line-height: 16px;
    padding-bottom: 2px; text-align: left; white-space: nowrap; }}
  .hm3-tabs {{ display: flex; gap: 0.35rem; margin-bottom: 0.5rem; flex-wrap: wrap; }}
  .hm3-tab  {{ padding: 0.25rem 0.75rem; border: 1px solid #ccc; border-radius: 4px;
               background: #f5f5f5; cursor: pointer; font-size: 0.8rem; font-weight: 500; }}
  .hm3-tab.hm3-active {{ background: #1a7f3c; color: #fff; border-color: #1a7f3c; }}
  .hm3-tab:hover:not(.hm3-active) {{ background: #e8e8e8; }}
  .hotspot-section {{ margin-bottom: 2rem; }}
  .hotspot-section h2 {{ font-size: 1rem; margin-bottom: 0.5rem; }}
  .hotspot-table {{ border-collapse: collapse; font-size: 0.85rem; width: 100%; margin-bottom: 0.75rem; }}
  .hotspot-table th {{ background: #f0f0f0; padding: 0.4rem 0.75rem; text-align: left; border-bottom: 2px solid #ddd; }}
  .hotspot-table td {{ padding: 0.35rem 0.75rem; border-bottom: 1px solid #eee; }}
  .hotspot-table tr:first-child td {{ font-weight: 600; background: #f0fff4; }}
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
  Exit: close crosses above upper BB (take profit) or close ≤ entry × (1 − Stop%) (stop loss)
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
    <div><strong>STOP_PCT_VALUES</strong> &nbsp;{", ".join(f"{s:.0%}" for s in _stop_values)}</div>
    <div><strong>Entry</strong> &nbsp;Close crosses below lower BB</div>
    <div><strong>Take profit</strong> &nbsp;Close crosses upper BB</div>
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
    <div class="value">{"—" if best_rdr is None else f"{best_rdr['RDR']:.2f}"}</div>
    <div class="sub">{"No combinations passed filters" if best_rdr is None else f"N={int(best_rdr['N'])} K={best_rdr['K']:.1f} Stop={best_rdr['Stop %']:.0%}"}</div>
  </div>
  <div class="card">
    <div class="label">Best Total Return</div>
    <div class="value">{"—" if best_ret is None else f"${best_ret['Total Return $']:,.2f}"}</div>
    <div class="sub">{"" if best_ret is None else f"N={int(best_ret['N'])} K={best_ret['K']:.1f} Stop={best_ret['Stop %']:.0%}"}</div>
  </div>
  <div class="card">
    <div class="label">Best Score</div>
    <div class="value">{"—" if best_score is None else f"{best_score['Score']:.1f}"}</div>
    <div class="sub">{"" if best_score is None else f"N={int(best_score['N'])} K={best_score['K']:.1f} Stop={best_score['Stop %']:.0%}"}</div>
  </div>
  <div class="card">
    <div class="label">Initial Capital</div>
    <div class="value">${INITIAL_CAPITAL:,}</div>
    <div class="sub">compounded across all trades · edit INITIAL_CAPITAL in backtester.py</div>
  </div>
</div>

{build_wf_html(wf_windows, WF_TRAIN_YEARS, WF_TEST_YEARS, WF_STEP_MONTHS, CAGR_THRESHOLD, WF_MIN_TRADES)}

{_build_hotspot_html(find_hotspots(df_all, n_values or N_VALUES, k_values or K_VALUES, stop_values or STOP_PCT_VALUES))}

<div class="heatmap-section">
  <h2>📊 Score Heat Map — N × K × Stop</h2>
  <p class="heatmap-caption">
    Each cell = composite Score (Total Return % × RDR ÷ {SCORE_DIVISOR}).
    Select a stop % tab to view the N × K slice. Gray cells did not meet the RDR ≥ {RDR_THRESHOLD} threshold.
    {"Gold border = global best combination across all stops." if best_score is not None else "<strong>No combinations passed all filters.</strong>"}

  </p>
  <div class="heatmap-wrap">
    {build_heatmap_3d(df_all, df, n_values or N_VALUES, k_values or K_VALUES, stop_values or STOP_PCT_VALUES)}
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
    RDR_THRESHOLD  = params["RDR_THRESHOLD"]
    MIN_TRADES     = params["MIN_TRADES"]
    CAGR_THRESHOLD = params["CAGR_THRESHOLD"]

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

    # Precompute SMA+STD once per N value — shared across all K and Stop combinations
    print("  Precomputing indicators...")
    ind_cache = {n: bollinger_base(close, n) for n in N_VALUES}

    results = []
    for n, k, stop_pct in combos:
        sma, std = ind_cache[n]
        upper    = sma + k * std
        lower    = sma - k * std
        r = run(close, n, k, stop_pct, MIN_TRADES, _precomp=(sma, upper, lower))
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
    wf_windows = walk_forward(df_raw, params, N_VALUES, K_VALUES, STOP_PCT_VALUES)
    print(f"  Walk-forward: {len(wf_windows)} windows completed")

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"backtest_{run_date}.html"
    out_path.write_text(build_html(out, df_all, wf_windows, run_date, data_through, params,
                                   stop_values=STOP_PCT_VALUES), encoding="utf-8")

    good_count = (out["RDR"] >= RDR_THRESHOLD).sum()
    best       = out.iloc[0]
    print(f"  Valid results: {len(out)}  |  RDR ≥ {RDR_THRESHOLD}: {good_count}")
    print(f"  Top result: N={int(best['N'])} K={best['K']} Stop={best['Stop %']:.0%}  →  RDR={best['RDR']:.2f}  Final=${best['Final Balance $']:,.2f}  Return={best['Total Return %']:.1f}%  (initial: ${INITIAL_CAPITAL:,})")
    print(f"  Report: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# KELTNER CHANNEL STRATEGY
# ══════════════════════════════════════════════════════════════════════════════

N_VALUES_KC = list(range(10, 35))                          # Lookback period: [10, 11, ..., 34]
K_VALUES_KC = [round(k * 0.1, 1) for k in range(10, 26)]  # Band width: [1.0, 1.1, ..., 2.5]
STOP_PCT_VALUES_KC = [0.20, 0.30, 0.40, 0.50, 0.60]       # Stop loss: [20%, 30%, 40%, 50%, 60%]


def keltner(close: pd.Series, high: pd.Series, low: pd.Series, n: int, k: float):
    ema = close.ewm(span=n, adjust=False).mean()
    tr  = pd.concat([high - low,
                     (high - close.shift(1)).abs(),
                     (low  - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    return ema, ema + k * atr, ema - k * atr


def lr_slope(close: pd.Series, period: int) -> pd.Series:
    """Rolling linear regression slope over `period` days.
    Positive = uptrend, negative = downtrend."""
    import numpy as np
    x = np.arange(period, dtype=float)
    x -= x.mean()  # centre x to improve numerical stability
    def _slope(y):
        return np.dot(x, y) / np.dot(x, x)
    return close.rolling(period).apply(_slope, raw=True)


def run_keltner(close: pd.Series, high: pd.Series, low: pd.Series,
                n: int, k: float, stop_pct: float, min_trades: int,
                entry_from_idx: int = 0, lr_period: int = 0) -> dict | None:
    ema, upper, lower = keltner(close, high, low, n, k)
    kc_cross = (close < lower) & (close.shift(1) >= lower.shift(1))
    if lr_period > 0:
        slope = lr_slope(close, lr_period)
        buy = kc_cross & (slope > 0)
    else:
        buy = kc_cross

    # Single-pass: signal detection + compounding balance + daily mark-to-market
    trades       = []
    daily_equity = []           # portfolio value at every bar — used for true max drawdown
    balance      = INITIAL_CAPITAL
    shares       = 0.0
    in_trade     = False
    entry_price  = entry_idx = None
    bal_at_entry = INITIAL_CAPITAL
    wins_count   = 0
    win_pnls     = []
    loss_pnls    = []
    stop_hits    = 0
    trade_rets   = []

    for i in range(max(n, entry_from_idx), len(close)):
        c = close.iloc[i]
        if not in_trade:
            if buy.iloc[i]:
                in_trade     = True
                entry_price  = c
                entry_idx    = i
                bal_at_entry = balance
                shares       = balance / c
        else:
            # Take profit: close crosses above upper Keltner Band
            tp = c > upper.iloc[i] and close.iloc[i - 1] <= upper.iloc[i - 1]
            sl = c <= entry_price * (1 - stop_pct)
            if tp or sl:
                balance  = shares * c
                ret_pct  = (c / entry_price - 1) * 100
                pnl      = balance - bal_at_entry
                trades.append({"entry": entry_price, "exit": c,
                                "hold": i - entry_idx, "reason": "tp" if tp else "sl"})
                trade_rets.append(ret_pct)
                if pnl > 0:
                    wins_count += 1
                    win_pnls.append(pnl)
                else:
                    loss_pnls.append(pnl)
                if not tp:
                    stop_hits += 1
                shares   = 0.0
                in_trade = False

        # Mark-to-market: value of portfolio at today's close
        daily_equity.append(shares * c if in_trade else balance)

    if len(trades) < min_trades:
        return None

    final_balance = shares * close.iloc[-1] if in_trade else balance
    total_return  = final_balance - INITIAL_CAPITAL
    total_ret_pct = total_return / INITIAL_CAPITAL * 100
    num_trades    = len(trades)
    win_rate      = wins_count / num_trades * 100
    avg_win       = sum(win_pnls)  / len(win_pnls)  if win_pnls  else 0.0
    avg_loss      = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    avg_ret_pct   = sum(trade_rets) / len(trade_rets)
    avg_hold      = sum(t["hold"] for t in trades) / len(trades)

    # True max drawdown from daily mark-to-market equity curve
    eq_s       = pd.Series(daily_equity)
    peak       = eq_s.cummax()
    max_dd     = float((peak - eq_s).max())
    max_dd_pct = max_dd / peak.max() * 100 if peak.max() > 0 else 0.0

    rdr = min(round(total_return / max_dd, 2), 999.0) if max_dd > 0 else 999.0  # always cap at 999

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


def load_kc_params() -> dict:
    text = RULES_PATH.read_text()

    def extract(symbol: str):
        pattern = rf"\|\s*`KC_{symbol}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"Cannot find parameter `KC_{symbol}` in STRATEGY_RULES.md")
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
        "WF_MIN_TRADES":   extract("WF_MIN_TRADES"),
        "LR_PERIOD":       extract("LR_PERIOD"),
    }


def walk_forward_keltner(df_raw: pd.DataFrame, params: dict, n_values: list, k_values: list,
                         stop_values: list = None) -> list:
    if stop_values is None:
        stop_values = [params["StopPct"]]
    stop_pct = stop_values[0]  # KC uses single stop for now (keeps report simple)
    train_years   = int(params["WF_TRAIN_YEARS"])
    test_years    = int(params["WF_TEST_YEARS"])
    step_months   = int(params["WF_STEP_MONTHS"])
    wf_min_trades = int(params["WF_MIN_TRADES"])
    lr_period     = int(params["LR_PERIOD"])
    dates        = df_raw["Date"]
    close        = df_raw["Close"]
    high         = df_raw["High"]
    low          = df_raw["Low"]
    windows      = []
    t            = dates.min()

    while True:
        train_end_date = t + pd.DateOffset(years=train_years)
        test_end_date  = train_end_date + pd.DateOffset(years=test_years)
        if test_end_date > dates.max():
            break

        te_mask = dates >= train_end_date
        xt_mask = dates >= test_end_date
        if not te_mask.any() or not xt_mask.any():
            break
        train_end_idx = int(df_raw[te_mask].index[0])
        test_end_idx  = int(df_raw[xt_mask].index[0])

        best_score  = -1
        best_n, best_k = n_values[0], k_values[0]
        best_train  = None
        for n in n_values:
            for k in k_values:
                r = run_keltner(close.iloc[:train_end_idx], high.iloc[:train_end_idx],
                                low.iloc[:train_end_idx], n, k, stop_pct, wf_min_trades,
                                lr_period=lr_period)
                if r and r["Score"] > best_score:
                    best_score = r["Score"]
                    best_n, best_k = n, k
                    best_train = r

        test_r = run_keltner(close.iloc[:test_end_idx], high.iloc[:test_end_idx],
                             low.iloc[:test_end_idx], best_n, best_k, stop_pct, 1,
                             entry_from_idx=train_end_idx, lr_period=lr_period)

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


def main_keltner():
    run_date = datetime.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Keltner backtester starting")

    params         = load_kc_params()
    RDR_THRESHOLD  = params["RDR_THRESHOLD"]
    MIN_TRADES     = params["MIN_TRADES"]
    CAGR_THRESHOLD = params["CAGR_THRESHOLD"]
    LR_PERIOD      = int(params["LR_PERIOD"])

    df_raw = (
        pd.read_csv(DATA_PATH, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    close        = df_raw["Close"]
    high         = df_raw["High"]
    low          = df_raw["Low"]
    data_through = df_raw["Date"].max().strftime("%Y-%m-%d")
    print(f"  Data: {df_raw['Date'].min().date()} → {data_through}  ({len(df_raw):,} days)")

    combos = list(product(N_VALUES_KC, K_VALUES_KC, STOP_PCT_VALUES_KC))
    print(f"  Grid: {len(combos)} combinations  (N={N_VALUES_KC}  K={K_VALUES_KC}  Stop%={[f'{s:.0%}' for s in STOP_PCT_VALUES_KC]})")

    results = []
    for n, k, sp in combos:
        r = run_keltner(close, high, low, n, k, sp, MIN_TRADES, lr_period=LR_PERIOD)
        if r:
            results.append(r)

    if not results:
        print("  No valid KC results — widening the parameter grid may help.")
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

    print("  Running Keltner walk-forward analysis...")
    wf_windows = walk_forward_keltner(df_raw, params, N_VALUES_KC, K_VALUES_KC)
    print(f"  Walk-forward: {len(wf_windows)} windows completed")

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / f"backtest_keltner_{run_date}.html"
    out_path.write_text(build_html(out, df_all, wf_windows, run_date, data_through, params,
                                   n_values=N_VALUES_KC, k_values=K_VALUES_KC,
                                   stop_values=STOP_PCT_VALUES_KC), encoding="utf-8")

    if len(out) == 0:
        print("  No KC results passed filters.")
        return

    good_count = (out["RDR"] >= RDR_THRESHOLD).sum()
    best       = out.iloc[0]
    print(f"  Valid KC results: {len(out)}  |  RDR ≥ {RDR_THRESHOLD}: {good_count}")
    print(f"  Top KC result: N={int(best['N'])} K={best['K']} Stop={best['Stop %']:.0%}  →  RDR={best['RDR']:.2f}  Final=${best['Final Balance $']:,.2f}  Return={best['Total Return %']:.1f}%  (initial: ${INITIAL_CAPITAL:,})")
    print(f"  Report: {out_path}")


if __name__ == "__main__":
    main()
    # main_keltner()  # ARCHIVED — KC results not yet high-confidence
