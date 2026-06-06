# Enchanted Crown Fund — Strategy Rules

## Overview

A cross-sectional mean-reversion strategy applied to a universe of 50 small-cap equities
(Russell 2000 constituents). Rather than trading a single ticker, the model ranks the
entire universe daily by how statistically oversold each stock is. The most oversold ticker
is bought when it crosses a defined entry threshold. Only one position is held at a time.
The position is exited when price recovers to the upper Bollinger Band on any of three
lookback windows, or when a stop loss is triggered.

---

## Variable Definitions

| Symbol | Name | Description |
|--------|------|-------------|
| `t` | Time index | The current trading day |
| `C(t)` | Closing price | Closing price of the asset on day t |
| `N` | Lookback period | Number of trading days for SMA and Bollinger Bands |
| `μ(N)` | SMA | Simple moving average of closing prices over N days |
| `σ(N)` | Std deviation | Standard deviation of closing prices over N days (population, ddof=0) |
| `Z(t,N)` | Z-score | How many standard deviations today's price is from the N-day mean |
| `Z_composite` | Composite Z-score | Mean of Z(t,N1), Z(t,N2), Z(t,N3) — the primary ranking signal |
| `K` | Std dev multiplier | Band width in standard deviations; entry threshold = −K |
| `StopPct` | Stop loss % | Maximum tolerated loss from entry before forced exit |
| `P_entry` | Entry price | Closing price on the day the buy signal fired |
| `N_base` | Base lookback | Shortest of the three windows; N2 = N_base + Gap, N3 = N_base + 2×Gap |
| `Gap` | Window spacing | Days between each consecutive lookback window |

---

## Inputs

| Parameter | Symbol | Current Value | Description |
|-----------|--------|---------------|-------------|
| Base lookback | `N_base` | **28** | Shortest Bollinger Band window (N1) |
| Window gap | `Gap` | **12** | Spacing between windows; N2 = N1+Gap, N3 = N1+2×Gap |
| Window 1 | `N1` | **38** | N_base + 0×Gap |
| Window 2 | `N2` | **50** | N_base + 1×Gap |
| Window 3 | `N3` | **62** | N_base + 2×Gap |
| Band multiplier | `K` | **1.7** | Entry threshold = composite Z ≤ −1.7 |
| Stop loss | `StopPct` | **30%** | Exit if close falls ≥ 30% below entry price |
| Universe | — | **50 tickers** | Russell 2000 small-cap constituents |
| Position size | — | **$10,000** | Fixed notional per trade (not full-balance) |
| Max positions | — | **1** | Single position at a time |

Parameters are auto-loaded from the latest `cs_summary_*.csv` each night. Do not edit values
here manually — update them by running the backtester and committing updated reports.

---

## Indicator Definitions

### Simple Moving Average (SMA)

```
μ(N) = ( C(t) + C(t-1) + ... + C(t-N+1) ) / N
```

### Bollinger Bands

```
σ(N)           = sqrt( (1/N) × Σ (C(i) − μ(N))²  )   for i = t-N+1 to t   [population std, ddof=0]
Upper Band(t)  = μ(N) + K × σ(N)
Lower Band(t)  = μ(N) − K × σ(N)
```

**Standard deviation method: population (ddof=0), not sample (ddof=1).**
The formula divides by N, not N−1. Any implementation must use `ddof=0` to match backtested results.

### Z-Score (per window)

```
Z(t, N) = ( C(t) − μ(N) ) / σ(N)
```

A Z-score of −1.7 means price is 1.7 standard deviations below its N-day mean — statistically oversold.

### Composite Z-Score

```
Z_composite(t) = mean( Z(t, N1),  Z(t, N2),  Z(t, N3) )
```

Averaging across three lookback windows implements the **multi-lookback consensus** principle:
a ticker must be oversold across short, medium, and long windows simultaneously, not just
one. This significantly reduces false signals compared to a single-window model.

---

## Signal Rules

### Entry (when FLAT — no open position)

```
1. Compute Z_composite for every ticker in the universe
2. Identify the ticker with the lowest Z_composite (most oversold)
3. BUY if Z_composite ≤ −K   (i.e. ≤ −1.7)
```

The model buys the single most oversold ticker in the universe on the day the threshold is
crossed. If no ticker is below −K, the model remains in cash.

**Only one position is held at a time.** Once a position is open, the entry check is
skipped entirely until the position is closed. The model never switches tickers mid-trade.

### Exit — Take Profit (when HOLDING)

```
For each window n in [N1, N2, N3]:
    if C(t) > Upper Band(t, n)  AND  C(t-1) ≤ Upper Band(t-1, n):
        EXIT
```

Exit on the first day close crosses above the upper Bollinger Band on **any** of the three
windows. Whichever window triggers first ends the trade. This mirrors the backtester exactly.

### Exit — Stop Loss (when HOLDING)

```
C(t) ≤ P_entry × (1 − StopPct)
C(t) ≤ P_entry × 0.70           ← at StopPct = 30%
```

Exit when close falls 30% or more below the entry price. This caps the maximum loss on any
single trade. Stop loss is checked before take profit each day.

---

## Portfolio Model

| Rule | Description |
|------|-------------|
| Position size | Fixed **$10,000** notional per trade |
| Max positions | **1** — fully single-position, never diversified |
| Order type | Market order at next open (DAY time-in-force) |
| Idle cash | Remainder of portfolio sits in cash between trades |
| Entry price | Sourced from Alpaca `avg_entry_price` on the live position |
| Compounding | Not applicable — fixed notional, not full-balance reinvestment |

---

## Execution Schedule

| Step | Time | Action |
|------|------|--------|
| Data update | ~11:00pm ET weeknights | Fetch latest OHLCV from Massive API |
| Backtester | ~11:05pm ET | Re-run all 3 phases (BB, ML, CS) |
| Signal email | ~11:35pm ET | Send daily summary to myleswittman@gmail.com |
| Alpaca trader | ~11:36pm ET | Evaluate signal vs current positions; place orders if needed |
| Order fills | 9:30am ET next morning | Market orders execute at open |

---

## Scoring

The backtester ranks parameter combinations using a composite Score:

```
Score = Total Return % × RDR / 100
RDR   = Total Return $ / Max Drawdown $
```

A strategy that earns high returns with a large drawdown scores lower than one earning the
same return more smoothly. RDR above 3.0 is the minimum threshold; above 5.0 is strong.

---

## Parameter Optimization

The cross-sectional backtester performs a full grid search each run across:

| Parameter | Search Range | Current Best |
|-----------|-------------|--------------|
| N_base | 16 to 40 (step 1) | 28 |
| Gap | 5, 8, 10, 12, 15 | 12 |
| K | 1.5 to 3.2 (step 0.1) | 1.7 |
| Stop % | 20%, 30%, 40%, 50%, 60% | 30% |

Grid size: 25 × 5 × 18 × 5 = **11,250 combinations** evaluated per run.

---

## Validation Rules

A parameter combination is only adopted if it passes all of the following:

| Rule | Threshold | Description |
|------|-----------|-------------|
| Minimum RDR | ≥ 3.0 | Return-to-Drawdown ratio across full history |
| Minimum CAGR | ≥ 20% | Annualized return must beat ~2× S&P 500 long-run average |
| Minimum trades | ≥ 5 | Minimum completed trades for statistical validity |
| Walk-forward | ≥ 5/9 windows profitable | Out-of-sample robustness test (see below) |

---

## Walk-Forward Analysis

Walk-forward analysis validates that the optimized parameters are not overfit to history.
The model is optimized on a training window and evaluated out-of-sample on a test window,
rolling forward in steps across the full 10-year history.

| Parameter | Value | Description |
|-----------|-------|-------------|
| Train window | 5 years | Period used for optimization |
| Test window | 1 year | Out-of-sample evaluation period |
| Step size | 6 months | How far the window slides each iteration |
| Windows | ~9 | Number of train/test splits across 10 years |
| WF min trades | 3 | Minimum trades required within a training window |
| Top combos | 200 | Only the top 200 in-sample combos are walk-forward tested (efficiency) |

Current walk-forward result: **5/9 windows profitable** — the model generated positive
out-of-sample returns in 5 of 9 rolling test periods.

---

## Response Surface Test (Overfitting Check)

Before adopting any parameter set, the **radio-knob test** is applied: hold all parameters
fixed at their optimal values and vary one parameter at a time across its full range.

- **Smooth curve** → parameter is well-generalized
- **Flat curve** → parameter has negligible effect; consider removing
- **Spiky curve** → parameter is likely overfit to an unrepeatable historical event

Smoothness is quantified by Normalized Total Variation (NTV):

```
NTV = Σ|Δy| / range(y)
```

| NTV | Interpretation |
|-----|----------------|
| < 2.5 | Smooth — well-generalized |
| 2.5 – 5.0 | Moderate — monitor carefully |
| ≥ 5.0 | Spiky — overfit risk |

The Response Surface tab in the app shows 1D slice charts and NTV scores for all four
parameters after every backtest run.

---

## Current Backtested Performance (as of 2026-06-06)

| Metric | Value |
|--------|-------|
| CAGR | 65.0% |
| Total Return | 18,298% |
| RDR | 3.26 |
| Win Rate | 76.3% |
| Max Drawdown | 25.3% |
| Total Trades | 59 |
| Avg Hold | 40.5 days |
| Walk-Forward | 5/9 windows profitable |
| Data period | 10.4 years |

---

## Bollinger Tab Reference Parameters

The **Bollinger** tab in the app visualizes a single-ticker, single-window BB strategy
for research purposes. It reads the following parameters from this file:

| Symbol | Value | Description |
|--------|-------|-------------|
| `N` | **50** | Single lookback window for the Bollinger tab chart |
| `K` | **1.7** | Band multiplier |
| `StopPct` | **30%** | Stop loss threshold |

These are set to match the cross-sectional model's middle window (N2) and shared K/Stop
values so the single-ticker visualization stays consistent with the live model.

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-02 | Initial rules — single-ticker Bollinger Band crossover |
| 1.1–1.9 | 2026-06-02–03 | Iterative refinements: removed RSI, added stop-loss, portfolio model, walk-forward, scoring, 8-neighbor robustness test |
| 2.0 | 2026-06-03 | Updated params: N=51, K=2.0. Take-profit changed to upper BB crossover. |
| 2.1–2.2 | 2026-06-04 | Tested N=47. Added/reverted Keltner Channel strategy. |
| 3.0 | 2026-06-06 | **Full rewrite.** Model replaced with cross-sectional multi-lookback consensus engine. Single-ticker approach retired. Entry now uses composite Z-score across N1/N2/N3 windows. Live paper trading via Alpaca enabled. |
