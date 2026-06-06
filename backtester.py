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

try:
    from tqdm import tqdm as _tqdm
    def _progress(it, **kw):
        return _tqdm(it, ncols=80, ascii=True, **kw)
except ImportError:
    def _progress(it, **kw):
        return it

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
BB_WF_TOP_COMBOS = 25                                   # Per-ticker BB walk-forward: re-optimize only top-N combos

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


def walk_forward_bb(df_raw: pd.DataFrame, params: dict, top_combos: list) -> list:
    """Narrowed walk-forward: re-optimize only among `top_combos` [(n,k,stop), ...]
    per window instead of the full N×K×Stop grid. Same window schema as
    walk_forward(), but ~(grid/len(top_combos))× faster — used for the per-ticker
    BB reports so the all-tickers run stays tractable in CI."""
    train_years   = int(params["WF_TRAIN_YEARS"])
    test_years    = int(params["WF_TEST_YEARS"])
    step_months   = int(params["WF_STEP_MONTHS"])
    wf_min_trades = int(params["WF_MIN_TRADES"])
    dates = df_raw["Date"]
    close = df_raw["Close"]
    if not top_combos:
        return []

    windows = []
    t = dates.min()
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

        # Precompute SMA/STD per unique N over the train slice (shared across K/Stop)
        train_close = close.iloc[:train_end_idx]
        wf_cache    = {n: bollinger_base(train_close, n) for n in {c[0] for c in top_combos}}

        best_score = -1
        best_n, best_k, best_stop = top_combos[0][0], top_combos[0][1], top_combos[0][2]
        best_train = None
        for n, k, stop_pct in top_combos:
            sma, std = wf_cache[n]
            r = run(train_close, n, k, stop_pct, wf_min_trades,
                    _precomp=(sma, sma + k * std, sma - k * std))
            if r and r["Score"] > best_score:
                best_score = r["Score"]
                best_n, best_k, best_stop = n, k, stop_pct
                best_train = r

        test_r = run(close.iloc[:test_end_idx], best_n, best_k, best_stop, 1,
                     entry_from_idx=train_end_idx)
        test_span_yrs = (dates.iloc[test_end_idx - 1] - dates.iloc[train_end_idx]).days / 365.25
        if test_r and test_span_yrs > 0:
            test_cagr = round(((test_r["Final Balance $"] / INITIAL_CAPITAL) ** (1 / test_span_yrs) - 1) * 100, 1)
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
        test_ret_str   = f'{w["Test Return %"]:+.1f}%' if has_test else '—'
        test_cagr_str  = f'{w["Test CAGR %"]:+.1f}%'  if w["Test CAGR %"] is not None else '—'
        train_ret_str  = f'{w["Train Return %"]:+.1f}%' if w["Train Return %"] is not None else '—'
        train_score_str = f'{w["Train Score"]:.1f}'    if w["Train Score"]   is not None else '—'
        rows.append(
            f'<tr{row_cls}>'
            f'<td>{w["Window"]}</td>'
            f'<td>{w["Train Start"]} → {w["Train End"]}</td>'
            f'<td>{w["Test Start"]} → {w["Test End"]}</td>'
            f'<td>{w["Best N"]}</td>'
            f'<td>{w["Best K"]:.1f}</td>'
            f'<td>{w.get("Best Stop","—")}</td>'
            f'<td>{train_ret_str}</td>'
            f'<td>{train_score_str}</td>'
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
      <div class="value">{f'{avg_ret:+.1f}%' if avg_ret is not None else '—'}</div>
    </div>
    <div class="card">
      <div class="label">Avg Out-of-Sample CAGR</div>
      <div class="value">{f'{avg_cagr:+.1f}%' if avg_cagr is not None else '—'}</div>
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
               stop_values: list = None, ticker: str = "GSIT") -> str:
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
<title>{ticker} Backtest — {run_date}</title>
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
<h1>📊 {ticker} Mean Reversion — Backtest Report</h1>
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

    if not DATA_PATH.exists():
        print(f"  SKIP: {DATA_PATH.name} not in universe — legacy single-ticker "
              f"BB run skipped (cross-sectional engine is the core path).")
        return

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


def _process_ticker_bb(ticker: str):
    """Single-ticker Bollinger grid search + walk-forward. Called by Pool.map.

    Returns (ticker, out_df, df_all, wf_windows, data_through) or None.
    """
    params = load_strategy_params()
    MIN_TRADES     = params["MIN_TRADES"]
    RDR_THRESHOLD  = params["RDR_THRESHOLD"]
    CAGR_THRESHOLD = params["CAGR_THRESHOLD"]

    path = DATA_DIR / f"{ticker}_daily_high_low.csv"
    if not path.exists():
        return None
    df_raw = (
        pd.read_csv(path, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    close        = df_raw["Close"]
    data_through = df_raw["Date"].max().strftime("%Y-%m-%d")

    combos    = list(product(N_VALUES, K_VALUES, STOP_PCT_VALUES))
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
        print(f"  [{ticker}] no valid BB results", flush=True)
        return None

    years  = (df_raw["Date"].max() - df_raw["Date"].min()).days / 365.25
    df_all = pd.DataFrame(results)
    df_all["CAGR %"] = (((df_all["Final Balance $"] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100).round(1)
    out = (
        df_all
        .query("RDR >= @RDR_THRESHOLD and `CAGR %` >= @CAGR_THRESHOLD")
        .sort_values("Score", ascending=False)
        .reset_index(drop=True)
    )
    # Narrowed walk-forward: only re-optimize the top combos by Score per window.
    top_combos = [
        (int(r["N"]), float(r["K"]), float(r["Stop %"]))
        for _, r in df_all.nlargest(BB_WF_TOP_COMBOS, "Score").iterrows()
    ]
    wf_windows = walk_forward_bb(df_raw, params, top_combos)
    print(f"  [{ticker}] BB grid {len(combos):,} → {len(out)} valid | WF {len(wf_windows)} windows", flush=True)
    return ticker, out, df_all, wf_windows, data_through


def main_bb_all():
    """Run the single-ticker Bollinger backtest for EVERY ticker in the universe,
    writing one report per ticker (backtest_bb_<ticker>.html) so the app's
    'BB Backtest' tab can offer a ticker dropdown. Heavy compute stays in CI."""
    from multiprocessing import Pool, cpu_count

    run_date = datetime.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Per-ticker Bollinger backtester starting")

    tickers   = sorted(p.stem.replace("_daily_high_low", "") for p in DATA_DIR.glob("*_daily_high_low.csv"))
    n_workers = max(1, min(cpu_count(), len(tickers)))
    print(f"  Tickers: {len(tickers)}  |  Workers: {n_workers}  |  Grid/ticker: {len(N_VALUES)*len(K_VALUES)*len(STOP_PCT_VALUES):,} combos")

    with Pool(n_workers) as pool:
        results_list = list(_progress(
            pool.imap(_process_ticker_bb, tickers),
            total=len(tickers), desc="BB tickers",
        ))

    params   = load_strategy_params()
    OUT_DIR.mkdir(exist_ok=True)
    summary  = []
    for res in results_list:
        if res is None:
            continue
        ticker, out, df_all, wf_windows, data_through = res
        # One bad ticker must not abort the whole pipeline (ML + cross-sectional
        # still need to run after this), so isolate each report.
        try:
            html = build_html(out, df_all, wf_windows, run_date, data_through, params,
                              stop_values=STOP_PCT_VALUES, ticker=ticker)
            (OUT_DIR / f"backtest_bb_{ticker}.html").write_text(html, encoding="utf-8")
            if len(out):
                best = out.iloc[0]
                wf_pos = sum(1 for w in wf_windows if w.get("Test Return %") and w["Test Return %"] > 0)
                summary.append({
                    "Ticker": ticker, "N": int(best["N"]), "K": float(best["K"]),
                    "Stop %": float(best["Stop %"]), "CAGR %": round(float(best["CAGR %"]), 1),
                    "Total Return %": round(float(best["Total Return %"]), 1),
                    "RDR": round(float(best["RDR"]), 2), "Win %": round(float(best["Win %"]), 1),
                    "Max DD %": round(float(best["Max Drawdown %"]), 1), "Trades": int(best["Trades"]),
                    "WF Profitable": f"{wf_pos}/{len(wf_windows)}", "Data Through": data_through,
                })
        except Exception as e:
            print(f"  [{ticker}] report FAILED: {type(e).__name__}: {e}", flush=True)

    if summary:
        pd.DataFrame(summary).sort_values("CAGR %", ascending=False).to_csv(
            OUT_DIR / f"bb_summary_{run_date}.csv", index=False)
        print(f"  Wrote {len(summary)} per-ticker BB reports + bb_summary_{run_date}.csv")
    else:
        print("  No BB results to report.")


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

    if not DATA_PATH.exists():
        print(f"  SKIP: {DATA_PATH.name} not in universe — legacy Keltner run skipped.")
        return

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


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║               MULTI-LOOKBACK CONSENSUS BACKTESTER                           ║
# ║  Entry: close below ALL three lower BBs simultaneously                      ║
# ║  Exit:  close crosses above ANY upper BB  OR  stop loss                     ║
# ║  Grid:  (N_base, gap, K, Stop) — N1=N_base, N2=N_base+gap, N3=N_base+2*gap ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── Multi-lookback grid ───────────────────────────────────────────────────────
ML_N_BASE_VALUES  = list(range(16, 41))          # Base lookback: [16 .. 40]
ML_GAP_VALUES     = [5, 8, 10, 12, 15]           # Spacing between bands
ML_K_VALUES       = [round(k * 0.1, 1) for k in range(15, 33)]  # [1.5 .. 3.2]
ML_STOP_PCT_VALUES = [0.20, 0.30, 0.40, 0.50, 0.60]
ML_MIN_TRADES     = 3                            # Lower floor — fewer trades expected
ML_WF_TOP_COMBOS  = 200                          # Only top-N combos by Score enter walk-forward

DATA_DIR = REPO_DIR / "data"


def run_multilookback(
    close_np: "np.ndarray",
    upper1_np: "np.ndarray", lower1_np: "np.ndarray",
    upper2_np: "np.ndarray", lower2_np: "np.ndarray",
    upper3_np: "np.ndarray", lower3_np: "np.ndarray",
    stop_pct: float,
    min_trades: int,
    entry_from_idx: int = 0,
) -> dict | None:
    """
    NumPy-based inner loop for speed at multi-ticker scale.
    Entry:  close < lower1 AND lower2 AND lower3
    Exit TP: close crosses above upper1 OR upper2 OR upper3
    Exit SL: close <= entry_price * (1 - stop_pct)
    """
    n_bars = len(close_np)
    start  = max(entry_from_idx, 1)   # need i-1 for crossover check

    trades       = []
    daily_equity = []
    balance      = INITIAL_CAPITAL
    shares       = 0.0
    in_trade     = False
    entry_price  = 0.0
    entry_idx    = 0
    bal_at_entry = INITIAL_CAPITAL
    wins_count   = 0
    win_pnls     = []
    loss_pnls    = []
    stop_hits    = 0
    trade_rets   = []

    for i in range(start, n_bars):
        c    = close_np[i]
        c_p  = close_np[i - 1]

        if not in_trade:
            # Entry: below ALL three lower bands
            if (c < lower1_np[i] and c < lower2_np[i] and c < lower3_np[i]):
                in_trade     = True
                entry_price  = c
                entry_idx    = i
                bal_at_entry = balance
                shares       = balance / c
        else:
            # Take profit: crosses above ANY upper band
            tp = (
                (c > upper1_np[i] and c_p <= upper1_np[i - 1]) or
                (c > upper2_np[i] and c_p <= upper2_np[i - 1]) or
                (c > upper3_np[i] and c_p <= upper3_np[i - 1])
            )
            sl = c <= entry_price * (1.0 - stop_pct)
            if tp or sl:
                balance  = shares * c
                ret_pct  = (c / entry_price - 1.0) * 100.0
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

        daily_equity.append(shares * c if in_trade else balance)

    if len(trades) < min_trades:
        return None

    import numpy as np
    final_balance = shares * close_np[-1] if in_trade else balance
    total_return  = final_balance - INITIAL_CAPITAL
    total_ret_pct = total_return / INITIAL_CAPITAL * 100.0
    num_trades    = len(trades)
    win_rate      = wins_count / num_trades * 100.0
    avg_hold      = sum(t["hold"] for t in trades) / num_trades

    eq_arr     = np.array(daily_equity)
    peak       = np.maximum.accumulate(eq_arr)
    max_dd     = float((peak - eq_arr).max())
    max_dd_pct = max_dd / peak.max() * 100.0 if peak.max() > 0 else 0.0
    rdr        = min(round(total_return / max_dd, 2), 999.0) if max_dd > 0 else 999.0

    return {
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


def walk_forward_ml(
    close_np: "np.ndarray",
    dates: pd.Series,
    top_combos: list,           # [(n_base, gap, k, stop_pct), ...] — pre-filtered top-N
    train_years: int = 5,
    test_years: int  = 1,
    step_months: int = 6,
    wf_min_trades: int = 2,
) -> list:
    """Walk-forward validation — only evaluates the supplied top_combos per window."""
    windows = []
    t = dates.min()
    first_combo = top_combos[0]

    while True:
        train_end_date = t + pd.DateOffset(years=train_years)
        test_end_date  = train_end_date + pd.DateOffset(years=test_years)
        if test_end_date > dates.max():
            break

        te_mask = dates >= train_end_date
        xt_mask = dates >= test_end_date
        if not te_mask.any() or not xt_mask.any():
            break
        train_end_idx = int(dates[te_mask].index[0])
        test_end_idx  = int(dates[xt_mask].index[0])

        train_close = close_np[:train_end_idx]

        # Precompute only the N values needed by top_combos
        unique_ns = sorted({n for n_base, gap, k, sp in top_combos
                            for n in [n_base, n_base + gap, n_base + 2 * gap]})
        ind_cache = {}
        for n in unique_ns:
            if n < len(train_close):
                sma = pd.Series(train_close).rolling(n).mean().to_numpy()
                std = pd.Series(train_close).rolling(n).std(ddof=0).to_numpy()
                ind_cache[n] = (sma, std)

        best_score  = -1.0
        best_n_base, best_gap, best_k, best_stop = first_combo
        best_train  = None

        for n_base, gap, k, stop_pct in top_combos:
            n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
            if n1 not in ind_cache or n2 not in ind_cache or n3 not in ind_cache:
                continue
            sma1, std1 = ind_cache[n1]
            upper1 = sma1 + k * std1; lower1 = sma1 - k * std1
            sma2, std2 = ind_cache[n2]
            upper2 = sma2 + k * std2; lower2 = sma2 - k * std2
            sma3, std3 = ind_cache[n3]
            upper3 = sma3 + k * std3; lower3 = sma3 - k * std3

            r = run_multilookback(
                train_close,
                upper1, lower1, upper2, lower2, upper3, lower3,
                stop_pct, wf_min_trades,
            )
            if r and r["Score"] > best_score:
                best_score  = r["Score"]
                best_n_base, best_gap, best_k, best_stop = n_base, gap, k, stop_pct
                best_train  = r

        # Run test period with best params from this window
        test_close = close_np[:test_end_idx]
        n1, n2, n3 = best_n_base, best_n_base + best_gap, best_n_base + 2 * best_gap
        test_cache = {}
        for n in {n1, n2, n3}:
            sma = pd.Series(test_close).rolling(n).mean().to_numpy()
            std = pd.Series(test_close).rolling(n).std(ddof=0).to_numpy()
            test_cache[n] = (sma, std)

        sma1, std1 = test_cache[n1]
        upper1 = sma1 + best_k * std1; lower1 = sma1 - best_k * std1
        sma2, std2 = test_cache[n2]
        upper2 = sma2 + best_k * std2; lower2 = sma2 - best_k * std2
        sma3, std3 = test_cache[n3]
        upper3 = sma3 + best_k * std3; lower3 = sma3 - best_k * std3

        test_r = run_multilookback(
            test_close,
            upper1, lower1, upper2, lower2, upper3, lower3,
            best_stop, 1, entry_from_idx=train_end_idx,
        )

        test_span_yrs = (dates.iloc[test_end_idx - 1] - dates.iloc[train_end_idx]).days / 365.25
        test_cagr = None
        if test_r and test_span_yrs > 0:
            test_cagr = round(
                ((test_r["Final Balance $"] / INITIAL_CAPITAL) ** (1 / test_span_yrs) - 1) * 100, 1
            )

        windows.append({
            "Window":         len(windows) + 1,
            "Train Start":    t.strftime("%Y-%m"),
            "Train End":      train_end_date.strftime("%Y-%m"),
            "Test Start":     train_end_date.strftime("%Y-%m"),
            "Test End":       test_end_date.strftime("%Y-%m"),
            "Best N_base":    best_n_base,
            "Best Gap":       best_gap,
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


def _process_ticker_ml(ticker: str):
    """Process one ticker — grid search + walk-forward. Called by Pool.map."""
    from itertools import product as iproduct

    data_path = DATA_DIR / f"{ticker}_daily_high_low.csv"
    if not data_path.exists():
        return None

    df_raw = (
        pd.read_csv(data_path, parse_dates=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )
    close_np     = df_raw["Close"].to_numpy(dtype=float)
    dates        = df_raw["Date"]
    data_through = dates.max().strftime("%Y-%m-%d")
    years        = (dates.max() - dates.min()).days / 365.25

    print(f"  [{ticker}] {dates.min().date()} → {data_through}  ({len(df_raw):,} rows)", flush=True)

    # Precompute all unique N values for the full grid
    unique_ns = sorted({n for n_base in ML_N_BASE_VALUES
                        for gap in ML_GAP_VALUES
                        for n in [n_base, n_base + gap, n_base + 2 * gap]})
    ind_cache = {}
    for n in unique_ns:
        sma = pd.Series(close_np).rolling(n).mean().to_numpy()
        std = pd.Series(close_np).rolling(n).std(ddof=0).to_numpy()
        ind_cache[n] = (sma, std)

    combos = list(iproduct(ML_N_BASE_VALUES, ML_GAP_VALUES, ML_K_VALUES, ML_STOP_PCT_VALUES))
    rows = []
    for n_base, gap, k, stop_pct in combos:
        n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
        if n1 not in ind_cache or n2 not in ind_cache or n3 not in ind_cache:
            continue
        sma1, std1 = ind_cache[n1]
        upper1 = sma1 + k * std1; lower1 = sma1 - k * std1
        sma2, std2 = ind_cache[n2]
        upper2 = sma2 + k * std2; lower2 = sma2 - k * std2
        sma3, std3 = ind_cache[n3]
        upper3 = sma3 + k * std3; lower3 = sma3 - k * std3

        r = run_multilookback(
            close_np, upper1, lower1, upper2, lower2, upper3, lower3,
            stop_pct, ML_MIN_TRADES,
        )
        if r:
            r.update({"Ticker": ticker, "N_base": n_base, "Gap": gap,
                      "N1": n1, "N2": n2, "N3": n3, "K": k, "Stop %": stop_pct})
            rows.append(r)

    if not rows:
        print(f"  [{ticker}] No valid results", flush=True)
        return None

    df_all = pd.DataFrame(rows)
    df_all["CAGR %"] = ((df_all["Final Balance $"] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100
    df_all["CAGR %"] = df_all["CAGR %"].round(1)

    best = df_all.loc[df_all["Score"].idxmax()]
    print(f"  [{ticker}] Best: N=({int(best['N1'])},{int(best['N2'])},{int(best['N3'])}) "
          f"K={best['K']} Stop={best['Stop %']:.0%}  CAGR={best['CAGR %']:.1f}%  "
          f"RDR={best['RDR']:.2f}  Trades={int(best['Trades'])}", flush=True)

    # Walk-forward: only top ML_WF_TOP_COMBOS combos — ~100x fewer evaluations per window
    top_combos = list(
        df_all.nlargest(ML_WF_TOP_COMBOS, "Score")[["N_base", "Gap", "K", "Stop %"]]
        .itertuples(index=False, name=None)
    )
    print(f"  [{ticker}] Walk-forward ({len(top_combos)} combos × windows)...", flush=True)
    wf_windows = walk_forward_ml(close_np, dates, top_combos)
    print(f"  [{ticker}] Walk-forward: {len(wf_windows)} windows done", flush=True)

    return ticker, df_all, wf_windows, data_through, years


def main_multilookback():
    from multiprocessing import Pool, cpu_count

    run_date = datetime.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Multi-lookback backtester starting")

    tickers   = sorted(p.stem.replace("_daily_high_low", "") for p in DATA_DIR.glob("*_daily_high_low.csv"))
    n_workers = min(cpu_count(), len(tickers))
    print(f"  Tickers: {len(tickers)}  |  Workers: {n_workers}  |  Grid: {len(list(__import__('itertools').product(ML_N_BASE_VALUES, ML_GAP_VALUES, ML_K_VALUES, ML_STOP_PCT_VALUES))):,} combos  |  WF top-N: {ML_WF_TOP_COMBOS}")

    with Pool(n_workers) as pool:
        results_list = list(_progress(
            pool.imap(_process_ticker_ml, tickers),
            total=len(tickers), desc="ML tickers",
        ))

    all_results = {}
    for res in results_list:
        if res is not None:
            ticker, df_all, wf_windows, data_through, years = res
            all_results[ticker] = {"df_all": df_all, "wf_windows": wf_windows,
                                   "data_through": data_through, "years": years}

    if not all_results:
        print("No results to report.")
        return

    # Write per-ticker HTML + CSV reports
    OUT_DIR.mkdir(exist_ok=True)
    for ticker, res in all_results.items():
        out_path = OUT_DIR / f"backtest_ml_{ticker}_{run_date}.html"
        out_path.write_text(
            _build_ml_html(ticker, res["df_all"], res["wf_windows"], run_date, res["data_through"], res["years"]),
            encoding="utf-8"
        )
        res["df_all"].to_csv(OUT_DIR / f"ml_{ticker}_{run_date}.csv", index=False)
        pd.DataFrame(res["wf_windows"]).to_csv(OUT_DIR / f"ml_wf_{ticker}_{run_date}.csv", index=False)
        print(f"  Report: {out_path}")

    # Cross-ticker summary CSV + console table
    summary_rows = []
    print(f"\n{'='*60}")
    print(f"MULTI-LOOKBACK SUMMARY  ({run_date})")
    print(f"{'='*60}")
    for ticker, res in all_results.items():
        df = res["df_all"]
        best = df.loc[df["Score"].idxmax()]
        wf_pos = sum(1 for w in res["wf_windows"] if w.get("Test Return %") and w["Test Return %"] > 0)
        wf_total = len(res["wf_windows"])
        summary_rows.append({
            "Ticker":          ticker,
            "Best Score":      round(float(best["Score"]), 1),
            "CAGR %":          round(float(best["CAGR %"]), 1),
            "Total Return %":  round(float(best["Total Return %"]), 1),
            "RDR":             round(float(best["RDR"]), 2),
            "Win %":           round(float(best["Win %"]), 1),
            "Max DD %":        round(float(best["Max Drawdown %"]), 1),
            "Trades":          int(best["Trades"]),
            "Avg Hold Days":   round(float(best["Avg Hold Days"]), 1),
            "N1":              int(best["N1"]),
            "N2":              int(best["N2"]),
            "N3":              int(best["N3"]),
            "K":               float(best["K"]),
            "Stop %":          float(best["Stop %"]),
            "WF Profitable":   f"{wf_pos}/{wf_total}",
            "Data Through":    res["data_through"],
        })
        print(f"  {ticker:6}  N=({int(best['N1'])},{int(best['N2'])},{int(best['N3'])})  K={best['K']}  Stop={best['Stop %']:.0%}  "
              f"CAGR={best['CAGR %']:.1f}%  RDR={best['RDR']:.2f}  "
              f"Trades={int(best['Trades'])}  WF profitable: {wf_pos}/{wf_total}")

    pd.DataFrame(summary_rows).to_csv(OUT_DIR / f"ml_summary_{run_date}.csv", index=False)
    print(f"\n  Summary CSV: {OUT_DIR / f'ml_summary_{run_date}.csv'}")


def _build_ml_html(ticker: str, df_all: pd.DataFrame, wf_windows: list,
                   run_date: str, data_through: str, years: float) -> str:
    """Minimal HTML report for multi-lookback results."""
    best  = df_all.loc[df_all["Score"].idxmax()]
    top20 = df_all.nlargest(20, "Score")

    rows_html = ""
    for _, r in top20.iterrows():
        rows_html += (
            f"<tr>"
            f"<td>({int(r['N1'])},{int(r['N2'])},{int(r['N3'])})</td>"
            f"<td>{r['K']}</td><td>{r['Stop %']:.0%}</td>"
            f"<td>{r['CAGR %']:.1f}%</td><td>{r['Total Return %']:.1f}%</td>"
            f"<td>{r['RDR']:.2f}</td><td>{r['Win %']:.1f}%</td>"
            f"<td>{r['Avg Hold Days']:.0f}</td><td>{r['Max Drawdown %']:.1f}%</td>"
            f"<td>{int(r['Trades'])}</td><td>{r['Score']:.1f}</td>"
            f"</tr>\n"
        )

    wf_rows = ""
    for w in wf_windows:
        ret   = w.get("Test Return %")
        cagr  = w.get("Test CAGR %")
        color = "#f0fff4" if (ret and ret > 0) else "#fdf2f2"
        wf_rows += (
            f"<tr style='background:{color}'>"
            f"<td>{w['Window']}</td><td>{w['Train Start']}–{w['Train End']}</td>"
            f"<td>{w['Test Start']}–{w['Test End']}</td>"
            f"<td>({w['Best N_base']},{w['Best N_base']+w['Best Gap']},{w['Best N_base']+2*w['Best Gap']})</td>"
            f"<td>{w['Best K']}</td><td>{w['Best Stop']}</td>"
            f"<td>{w.get('Train Return %', '—')}%</td>"
            f"<td>{ret if ret is not None else '—'}%</td>"
            f"<td>{cagr if cagr is not None else '—'}%</td>"
            f"<td>{w.get('Test Trades', 0)}</td>"
            f"</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Multi-Lookback Backtest — {ticker} — {run_date}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; font-size: 0.82rem; width: 100%; margin-bottom: 1.5rem; }}
  th {{ background: #f0f0f0; padding: 0.4rem 0.6rem; text-align: left; border-bottom: 2px solid #ddd; }}
  td {{ padding: 0.3rem 0.6rem; border-bottom: 1px solid #eee; }}
  .stat {{ display: inline-block; margin: 0.3rem 1rem 0.3rem 0; }}
  .stat .v {{ font-size: 1.4rem; font-weight: 700; }}
  .stat .l {{ font-size: 0.75rem; color: #666; }}
</style></head><body>
<h1>Multi-Lookback Consensus — {ticker}</h1>
<p style="color:#666;font-size:0.85rem">Data through {data_through} &nbsp;|&nbsp; Run {run_date} &nbsp;|&nbsp; {years:.1f} years</p>
<p style="color:#666;font-size:0.82rem">Entry: close &lt; lower BB(N1) AND lower BB(N2) AND lower BB(N3) &nbsp;|&nbsp; Exit: close crosses above ANY upper BB or stop loss</p>

<div>
  <span class="stat"><span class="v">{best['CAGR %']:.1f}%</span><br><span class="l">Best CAGR</span></span>
  <span class="stat"><span class="v">{best['Total Return %']:.1f}%</span><br><span class="l">Total Return</span></span>
  <span class="stat"><span class="v">{best['RDR']:.2f}</span><br><span class="l">RDR</span></span>
  <span class="stat"><span class="v">{best['Win %']:.1f}%</span><br><span class="l">Win Rate</span></span>
  <span class="stat"><span class="v">{int(best['Trades'])}</span><br><span class="l">Trades</span></span>
  <span class="stat"><span class="v">({int(best['N1'])},{int(best['N2'])},{int(best['N3'])})</span><br><span class="l">N1,N2,N3</span></span>
  <span class="stat"><span class="v">{best['K']}</span><br><span class="l">K</span></span>
  <span class="stat"><span class="v">{best['Stop %']:.0%}</span><br><span class="l">Stop</span></span>
</div>

<h2>Top 20 Parameter Combinations</h2>
<table>
  <thead><tr>
    <th>(N1,N2,N3)</th><th>K</th><th>Stop</th>
    <th>CAGR %</th><th>Return %</th><th>RDR</th><th>Win %</th>
    <th>Avg Hold</th><th>Max DD %</th><th>Trades</th><th>Score</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>

<h2>Walk-Forward Validation</h2>
<table>
  <thead><tr>
    <th>#</th><th>Train</th><th>Test</th>
    <th>Best (N1,N2,N3)</th><th>K</th><th>Stop</th>
    <th>Train Ret%</th><th>Test Ret%</th><th>Test CAGR%</th><th>Trades</th>
  </tr></thead>
  <tbody>{wf_rows}</tbody>
</table>
</body></html>"""


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          CROSS-SECTIONAL SINGLE-POSITION ENGINE (the fund simulator)        ║
# ║  One global param set across the whole universe. Each day:                  ║
# ║    • if holding → check exit (cross above ANY upper band, or stop)          ║
# ║    • if flat    → buy the single MOST oversold name (biggest loser)         ║
# ║      ranked by composite z-score = mean of (close−SMA)/STD over N1,N2,N3    ║
# ║  Hold-to-exit. Same-day exit-then-enter allowed. One equity curve.          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Reuse the multi-lookback grid as the GLOBAL search space (shared across all tickers)
CS_N_BASE_VALUES   = ML_N_BASE_VALUES
CS_GAP_VALUES      = ML_GAP_VALUES
CS_K_VALUES        = ML_K_VALUES
CS_STOP_PCT_VALUES = ML_STOP_PCT_VALUES
CS_MIN_TRADES      = 5
CS_WF_TOP_COMBOS   = 200


def load_aligned_universe():
    """Load every ticker CSV, align closes on a master date index. Returns (dates, tickers, close_mat)."""
    import numpy as np

    paths   = sorted(DATA_DIR.glob("*_daily_high_low.csv"))
    tickers = [p.stem.replace("_daily_high_low", "") for p in paths]

    series = {}
    for p, tk in zip(paths, tickers):
        df = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date")
        series[tk] = df.set_index("Date")["Close"]

    master = pd.DatetimeIndex(sorted(set().union(*[s.index for s in series.values()])))
    close_mat = np.column_stack([series[tk].reindex(master).to_numpy(dtype=float) for tk in tickers])
    return master, tickers, close_mat


def run_cross_sectional(
    close_mat, lower1, lower2, lower3, upper1, upper2, upper3,
    compz, entry_mask, stop_pct, start_idx, end_idx, min_trades,
    detailed: bool = False,
):
    """Single-position walk over [start_idx, end_idx). Starts flat. Returns metrics dict (+ detail)."""
    import numpy as np

    balance     = INITIAL_CAPITAL
    in_trade    = False
    held        = -1
    entry_price = 0.0
    shares      = 0.0
    entry_idx   = 0
    n_track     = end_idx - start_idx

    equity   = np.empty(n_track, dtype=float)
    trades   = []          # (entry_idx, exit_idx, held, entry_price, exit_price, reason)
    stop_hits = 0

    for j, i in enumerate(range(start_idx, end_idx)):
        if in_trade:
            c   = close_mat[i, held]
            c_p = close_mat[i - 1, held]
            tp = (
                (c > upper1[i, held] and c_p <= upper1[i - 1, held]) or
                (c > upper2[i, held] and c_p <= upper2[i - 1, held]) or
                (c > upper3[i, held] and c_p <= upper3[i - 1, held])
            )
            sl = c <= entry_price * (1.0 - stop_pct)
            force = not np.isfinite(c)      # delisted / missing → bail out
            if tp or sl or force:
                exit_price = c if np.isfinite(c) else close_mat[i - 1, held]
                balance    = shares * exit_price
                trades.append((entry_idx, i, held, entry_price, exit_price,
                               "tp" if tp else ("sl" if sl else "force")))
                if sl and not tp:
                    stop_hits += 1
                in_trade = False
                held     = -1
                shares   = 0.0

        if not in_trade:
            row = entry_mask[i]
            if row.any():
                masked = np.where(row & np.isfinite(compz[i]), compz[i], np.inf)
                best   = int(np.argmin(masked))
                if np.isfinite(masked[best]):
                    entry_price = close_mat[i, best]
                    shares      = balance / entry_price
                    held        = best
                    entry_idx   = i
                    in_trade    = True

        equity[j] = shares * close_mat[i, held] if in_trade else balance

    if len(trades) < min_trades:
        return None

    final_balance = equity[-1]
    total_return  = final_balance - INITIAL_CAPITAL
    total_ret_pct = total_return / INITIAL_CAPITAL * 100.0
    num_trades    = len(trades)
    wins          = sum(1 for t in trades if t[4] > t[3])
    win_rate      = wins / num_trades * 100.0
    avg_hold      = sum(t[1] - t[0] for t in trades) / num_trades

    peak       = np.maximum.accumulate(equity)
    max_dd     = float((peak - equity).max())
    max_dd_pct = max_dd / peak.max() * 100.0 if peak.max() > 0 else 0.0
    rdr        = min(round(total_return / max_dd, 2), 999.0) if max_dd > 0 else 999.0

    result = {
        "Trades":          num_trades,
        "Stop Hits":       int(stop_hits),
        "Win %":           round(win_rate, 1),
        "Avg Hold Days":   round(avg_hold, 1),
        "Final Balance $": round(final_balance, 2),
        "Total Return $":  round(total_return, 2),
        "Total Return %":  round(total_ret_pct, 2),
        "Max Drawdown $":  round(max_dd, 2),
        "Max Drawdown %":  round(max_dd_pct, 2),
        "RDR":             rdr,
        "Score":           round(total_ret_pct * rdr / SCORE_DIVISOR, 1),
    }
    if detailed:
        result["_trades"]   = trades
        result["_equity"]   = equity
        result["_final"]    = {"in_trade": in_trade, "held": held,
                               "entry_price": entry_price, "entry_idx": entry_idx}
    return result


def _cs_build_bands(sma_cache, std_cache, n1, n2, n3, k):
    """Assemble band matrices for one (N1,N2,N3,K). compz is K-independent so it's built by the caller."""
    lower1 = sma_cache[n1] - k * std_cache[n1]; upper1 = sma_cache[n1] + k * std_cache[n1]
    lower2 = sma_cache[n2] - k * std_cache[n2]; upper2 = sma_cache[n2] + k * std_cache[n2]
    lower3 = sma_cache[n3] - k * std_cache[n3]; upper3 = sma_cache[n3] + k * std_cache[n3]
    entry_mask = (close_mat_g < lower1) & (close_mat_g < lower2) & (close_mat_g < lower3)
    return lower1, lower2, lower3, upper1, upper2, upper3, entry_mask


def walk_forward_cs(dates, sma_cache, std_cache, compz_cache, top_combos,
                    train_years=5, test_years=1, step_months=6, wf_min_trades=3):
    """Walk-forward on the portfolio equity curve. Bands are causal so we reuse full-data caches."""
    import numpy as np

    n_days  = len(dates)
    first_valid = max(n_base + 2 * gap for n_base, gap, k, sp in top_combos)  # warmup of largest N3
    windows = []
    t = dates.min()

    while True:
        train_end_date = t + pd.DateOffset(years=train_years)
        test_end_date  = train_end_date + pd.DateOffset(years=test_years)
        if test_end_date > dates.max():
            break
        te_mask = np.asarray(dates >= train_end_date)
        xt_mask = np.asarray(dates >= test_end_date)
        if not te_mask.any() or not xt_mask.any():
            break
        train_end_idx = int(np.argmax(te_mask))
        test_end_idx  = int(np.argmax(xt_mask))

        best_score = -1e18
        best_combo = top_combos[0]
        best_train = None
        for n_base, gap, k, stop_pct in top_combos:
            n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
            lo1, lo2, lo3, up1, up2, up3, em = _cs_build_bands(sma_cache, std_cache, n1, n2, n3, k)
            compz = compz_cache[(n_base, gap)]
            r = run_cross_sectional(close_mat_g, lo1, lo2, lo3, up1, up2, up3, compz, em,
                                    stop_pct, first_valid, train_end_idx, wf_min_trades)
            if r and r["Score"] > best_score:
                best_score = r["Score"]
                best_combo = (n_base, gap, k, stop_pct)
                best_train = r

        # OOS test with the window's best params, starting flat at train_end
        n_base, gap, k, stop_pct = best_combo
        n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
        lo1, lo2, lo3, up1, up2, up3, em = _cs_build_bands(sma_cache, std_cache, n1, n2, n3, k)
        compz = compz_cache[(n_base, gap)]
        test_r = run_cross_sectional(close_mat_g, lo1, lo2, lo3, up1, up2, up3, compz, em,
                                     stop_pct, train_end_idx, test_end_idx, 1)

        test_span_yrs = (dates[test_end_idx - 1] - dates[train_end_idx]).days / 365.25
        test_cagr = None
        if test_r and test_span_yrs > 0:
            test_cagr = round(((test_r["Final Balance $"] / INITIAL_CAPITAL) ** (1 / test_span_yrs) - 1) * 100, 1)

        windows.append({
            "Window":         len(windows) + 1,
            "Train Start":    t.strftime("%Y-%m"),
            "Train End":      train_end_date.strftime("%Y-%m"),
            "Test Start":     train_end_date.strftime("%Y-%m"),
            "Test End":       test_end_date.strftime("%Y-%m"),
            "Best N_base":    n_base, "Best Gap": gap,
            "Best K":         round(k, 1), "Best Stop": f"{stop_pct:.0%}",
            "Train Return %": round(best_train["Total Return %"], 1) if best_train else None,
            "Test Trades":    test_r["Trades"]                       if test_r    else 0,
            "Test Return %":  round(test_r["Total Return %"], 1)     if test_r    else None,
            "Test CAGR %":    test_cagr,
        })
        t = t + pd.DateOffset(months=step_months)

    return windows


# Module-level handle so the band-builder can see the aligned close matrix
close_mat_g = None
# Shared read-only arrays for the grid workers. Set once in the parent before the
# Pool is forked; fork children inherit them copy-on-write (never pickled per task).
_cs_sma_g   = None
_cs_std_g   = None
_cs_compz_g = None


def _cs_grid_worker(combo):
    """Evaluate one (N_base, gap, K, stop) combo. Reads the shared close matrix and
    SMA/STD/compz caches from fork-inherited module globals, so only the tiny combo
    tuple and the small result dict cross the process boundary."""
    n_base, gap, k, stop_pct = combo
    n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
    lo1, lo2, lo3, up1, up2, up3, em = _cs_build_bands(_cs_sma_g, _cs_std_g, n1, n2, n3, k)
    compz  = _cs_compz_g[(n_base, gap)]
    n_days = close_mat_g.shape[0]
    r = run_cross_sectional(close_mat_g, lo1, lo2, lo3, up1, up2, up3, compz, em,
                            stop_pct, max(n3, 1), n_days, CS_MIN_TRADES)
    if not r:
        return None
    r.update({"N_base": n_base, "Gap": gap, "N1": n1, "N2": n2, "N3": n3,
              "K": k, "Stop %": stop_pct})
    return r


def main_cross_sectional():
    import numpy as np
    global close_mat_g, _cs_sma_g, _cs_std_g, _cs_compz_g

    run_date = datetime.today().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cross-sectional single-position backtester starting")

    dates, tickers, close_mat = load_aligned_universe()
    close_mat_g = close_mat
    n_days  = len(dates)
    years   = (dates.max() - dates.min()).days / 365.25
    print(f"  Universe: {len(tickers)} tickers  |  {dates.min().date()} → {dates.max().date()}  ({n_days:,} days)")

    # Precompute SMA/STD per unique N across the whole matrix (causal, no look-ahead)
    unique_ns = sorted({n for nb in CS_N_BASE_VALUES for g in CS_GAP_VALUES
                        for n in [nb, nb + g, nb + 2 * g]})
    df_close  = pd.DataFrame(close_mat)
    sma_cache, std_cache = {}, {}
    for n in unique_ns:
        sma_cache[n] = df_close.rolling(n).mean().to_numpy()
        std_cache[n] = df_close.rolling(n).std(ddof=0).to_numpy()

    # Composite z-score per (N_base, gap) — K-independent, reused across all K/stop
    compz_cache = {}
    for n_base in CS_N_BASE_VALUES:
        for gap in CS_GAP_VALUES:
            n1, n2, n3 = n_base, n_base + gap, n_base + 2 * gap
            z1 = (close_mat - sma_cache[n1]) / std_cache[n1]
            z2 = (close_mat - sma_cache[n2]) / std_cache[n2]
            z3 = (close_mat - sma_cache[n3]) / std_cache[n3]
            compz_cache[(n_base, gap)] = (z1 + z2 + z3) / 3.0

    # Publish shared arrays to module globals so forked grid workers inherit them.
    _cs_sma_g, _cs_std_g, _cs_compz_g = sma_cache, std_cache, compz_cache

    combos = list(product(CS_N_BASE_VALUES, CS_GAP_VALUES, CS_K_VALUES, CS_STOP_PCT_VALUES))

    # Parallelize the grid via fork (copy-on-write shares the big caches for free).
    # Serial fallback on platforms without fork (e.g. Windows) keeps it correct.
    import multiprocessing as mp
    from multiprocessing import cpu_count
    try:
        ctx = mp.get_context("fork")
        parallel = True
    except ValueError:
        parallel = False

    if parallel:
        n_workers = max(1, min(cpu_count(), 8))
        chunk     = max(1, len(combos) // (n_workers * 8))
        print(f"  Global grid: {len(combos):,} combos  |  {n_workers} fork workers  |  chunksize {chunk}")
        with ctx.Pool(n_workers) as pool:
            results = pool.map(_cs_grid_worker, combos, chunksize=chunk)
        rows = [r for r in results if r]
    else:
        print(f"  Global grid: {len(combos):,} combos  |  serial (fork unavailable)")
        rows = [r for r in (_cs_grid_worker(c) for c in combos) if r]

    if not rows:
        print("  No valid cross-sectional results.")
        return

    df_all = pd.DataFrame([{kk: vv for kk, vv in r.items() if not kk.startswith("_")} for r in rows])
    df_all["CAGR %"] = ((df_all["Final Balance $"] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100
    df_all["CAGR %"] = df_all["CAGR %"].round(1)

    best = df_all.loc[df_all["Score"].idxmax()]
    bn, bg, bk, bs = int(best["N_base"]), int(best["Gap"]), float(best["K"]), float(best["Stop %"])
    print(f"  Best global: N=({int(best['N1'])},{int(best['N2'])},{int(best['N3'])}) K={bk} Stop={bs:.0%}  "
          f"CAGR={best['CAGR %']:.1f}%  RDR={best['RDR']:.2f}  Win={best['Win %']:.1f}%  Trades={int(best['Trades'])}")

    # Re-run best combo with detail for trade log, equity curve, and today's signal
    n1, n2, n3 = bn, bn + bg, bn + 2 * bg
    lo1, lo2, lo3, up1, up2, up3, em = _cs_build_bands(sma_cache, std_cache, n1, n2, n3, bk)
    compz = compz_cache[(bn, bg)]
    detail = run_cross_sectional(close_mat, lo1, lo2, lo3, up1, up2, up3, compz, em,
                                 bs, max(n3, 1), n_days, 1, detailed=True)

    # Trade log
    trade_rows = []
    for e_idx, x_idx, col, e_px, x_px, reason in detail["_trades"]:
        trade_rows.append({
            "Ticker":     tickers[col],
            "Entry Date": dates[e_idx].strftime("%Y-%m-%d"),
            "Exit Date":  dates[x_idx].strftime("%Y-%m-%d"),
            "Entry $":    round(e_px, 2),
            "Exit $":     round(x_px, 2),
            "Return %":   round((x_px / e_px - 1) * 100, 2),
            "Hold Days":  x_idx - e_idx,
            "Reason":     reason,
        })
    trades_df = pd.DataFrame(trade_rows)

    # Equity curve (aligned to the detailed run range = [n3, n_days))
    eq_dates = dates[max(n3, 1):n_days]
    equity_df = pd.DataFrame({"Date": eq_dates.strftime("%Y-%m-%d"), "Equity": detail["_equity"].round(2)})

    # Today's signal — driven by Alpaca's actual live state, not simulation state.
    # The simulation's HOLDING state is intentionally ignored for signal output;
    # it's an artifact of the replay and does not reflect reality.
    #
    # Rules:
    #   Alpaca HOLDING X → check exit conditions → SELL or HOLDING (live)
    #   Alpaca FLAT      → check today's Z-scores → BUY or CASH
    #   No Alpaca keys   → only BUY or CASH from live Z-scores (never simulated HOLDING)

    last = n_days - 1
    masked_last       = np.where(em[last] & np.isfinite(compz[last]), compz[last], np.inf)
    biggest_loser_col = int(np.argmin(masked_last))
    has_candidate     = np.isfinite(masked_last[biggest_loser_col]) and masked_last[biggest_loser_col] <= -bk

    # BUY candidate (valid regardless of who is holding what)
    buy_signal = None
    if has_candidate:
        buy_signal = {"State": "BUY",
                      "Ticker": tickers[biggest_loser_col],
                      "Composite z": round(float(masked_last[biggest_loser_col]), 2),
                      "Last $": round(close_mat[last, biggest_loser_col], 2)}

    # Fetch live Alpaca position
    alpaca_ticker    = None
    alpaca_entry     = None
    alpaca_qty       = None
    alpaca_mkt_value = None
    alpaca_available = False
    _alpaca_api_key  = os.environ.get("ALPACA_API_KEY", "")
    _alpaca_secret   = os.environ.get("ALPACA_SECRET_KEY", "")
    if _alpaca_api_key and _alpaca_secret:
        try:
            from alpaca.trading.client import TradingClient
            _client    = TradingClient(_alpaca_api_key, _alpaca_secret, paper=True)
            _positions = _client.get_all_positions()
            alpaca_available = True
            if _positions:
                _pos             = _positions[0]
                alpaca_ticker    = _pos.symbol
                alpaca_entry     = float(_pos.avg_entry_price)
                alpaca_qty       = float(_pos.qty)
                alpaca_mkt_value = float(_pos.market_value)
                print(f"  Alpaca live position : HOLDING {alpaca_ticker}  "
                      f"entry=${alpaca_entry:.2f}  qty={alpaca_qty:.4f}  "
                      f"mkt=${alpaca_mkt_value:,.2f}")
            else:
                print("  Alpaca live position : FLAT (no open positions)")
        except Exception as _e:
            print(f"  Alpaca live position : unavailable ({_e})")
    else:
        print("  Alpaca live position : skipped (API keys not set)")

    # Build the actionable signal
    if alpaca_available and alpaca_ticker:
        # Alpaca is holding something — check exit conditions against today's bands
        _exit_reason = None
        _stop_level  = alpaca_entry * (1.0 - bs)
        _c           = close_mat[last]
        _c_prev      = close_mat[last - 1] if last > 0 else _c
        _col         = tickers.index(alpaca_ticker) if alpaca_ticker in tickers else -1

        # Stop loss check
        if _col >= 0 and _c[_col] <= _stop_level:
            _exit_reason = f"stop loss (close ${_c[_col]:.2f} <= stop ${_stop_level:.2f})"

        # Take profit: upper BB crossover on any of N1/N2/N3
        if _exit_reason is None and _col >= 0:
            for _ub in [up1, up2, up3]:
                if (_c[_col] > _ub[last, _col] and _c_prev[_col] <= _ub[last - 1, _col]):
                    _exit_reason = f"take profit (crossed upper BB, upper=${_ub[last, _col]:.2f})"
                    break

        if _exit_reason:
            signal = {"State": "SELL", "Ticker": alpaca_ticker,
                      "Reason": _exit_reason,
                      "Entry $": round(alpaca_entry, 2),
                      "Last $": round(_c[_col] if _col >= 0 else 0.0, 2),
                      "Qty": alpaca_qty}
        else:
            unreal = (close_mat[last, _col] / alpaca_entry - 1) * 100 if _col >= 0 else 0.0
            signal = {"State": "HOLDING", "Ticker": alpaca_ticker,
                      "Entry $": round(alpaca_entry, 2),
                      "Last $": round(close_mat[last, _col] if _col >= 0 else 0.0, 2),
                      "Unrealized %": round(unreal, 2),
                      "Qty": alpaca_qty,
                      "Mkt Value $": round(alpaca_mkt_value, 2),
                      "Source": "Alpaca"}
    elif alpaca_available and not alpaca_ticker:
        # Alpaca confirmed flat — show BUY or CASH
        signal = buy_signal if buy_signal else {"State": "CASH", "Ticker": None}
    else:
        # No Alpaca keys — only show BUY or CASH from live Z-scores
        signal = buy_signal if buy_signal else {"State": "CASH", "Ticker": None}

    print(f"  Signal as of {dates[last].date()}: {signal['State']}"
          + (f" {signal['Ticker']}" if signal.get("Ticker") else "")
          + (f" ({signal.get('Reason', '')})" if signal.get("Reason") else ""))

    # Walk-forward on top-N global combos
    top_combos = list(df_all.nlargest(CS_WF_TOP_COMBOS, "Score")[["N_base", "Gap", "K", "Stop %"]]
                      .itertuples(index=False, name=None))
    print(f"  Walk-forward ({len(top_combos)} combos × windows)...")
    wf = walk_forward_cs(dates, sma_cache, std_cache, compz_cache, top_combos)
    wf_pos = sum(1 for w in wf if w.get("Test Return %") and w["Test Return %"] > 0)
    print(f"  Walk-forward: {wf_pos}/{len(wf)} windows profitable OOS")

    # Write CSVs for the visualizer
    OUT_DIR.mkdir(exist_ok=True)
    df_all.to_csv(OUT_DIR / f"cs_grid_{run_date}.csv", index=False)
    trades_df.to_csv(OUT_DIR / f"cs_trades_{run_date}.csv", index=False)
    equity_df.to_csv(OUT_DIR / f"cs_equity_{run_date}.csv", index=False)
    pd.DataFrame(wf).to_csv(OUT_DIR / f"cs_wf_{run_date}.csv", index=False)
    pd.DataFrame([{
        "Run Date": run_date, "Data Through": dates.max().strftime("%Y-%m-%d"),
        "Universe": len(tickers), "Years": round(years, 1),
        "N1": n1, "N2": n2, "N3": n3, "K": bk, "Stop %": bs,
        "CAGR %": best["CAGR %"], "Total Return %": best["Total Return %"],
        "RDR": best["RDR"], "Win %": best["Win %"], "Max DD %": best["Max Drawdown %"],
        "Trades": int(best["Trades"]), "Avg Hold Days": best["Avg Hold Days"],
        "WF Profitable": f"{wf_pos}/{len(wf)}",
        "Signal": signal["State"], "Signal Ticker": signal.get("Ticker"),
    }]).to_csv(OUT_DIR / f"cs_summary_{run_date}.csv", index=False)
    pd.DataFrame([signal]).to_csv(OUT_DIR / f"cs_signal_{run_date}.csv", index=False)

    print(f"  CSVs written to {OUT_DIR}/cs_*_{run_date}.csv")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enchanted Crown Fund backtester")
    parser.add_argument(
        "--phase",
        choices=["bb", "ml", "cs", "all"],
        default="all",
        help="Which phase to run: bb=Bollinger per-ticker, ml=multi-lookback, cs=cross-sectional, all=all three",
    )
    args = parser.parse_args()

    if args.phase in ("bb", "all"):
        main_bb_all()      # per-ticker Bollinger reports (BB Backtest tab dropdown)
    # main_keltner()       # ARCHIVED — KC results not yet high-confidence
    if args.phase in ("ml", "all"):
        main_multilookback()
    if args.phase in ("cs", "all"):
        main_cross_sectional()
