# Enchanted Crown Fund — Mean Reversion Strategy Rules

## Overview
A mean reversion strategy assumes that price, after deviating significantly from its historical average, will tend to return to that average. Buy signals fire when price is statistically too low; sell signals fire when price is statistically too high.

---

## Variable Definitions

| Symbol | Name | Description |
|--------|------|-------------|
| `t` | Time index | The current trading day |
| `C(t)` | Closing price | The closing price of the asset on day t |
| `N` | Lookback period | Number of trading days for SMA and Bollinger Bands |
| `K` | Std dev multiplier | How many standard deviations define the band edges |
| `μ(N)` | SMA | Simple moving average of closing prices over N days |
| `d(i)` | Deviation | C(i) − μ(N) — how far day i's close sits from the mean |
| `σ(N)` | Std deviation | Standard deviation of closing prices over N days |
| `σ²(N)` | Variance | Mean of squared deviations over N days |
| `Z(t)` | Z-score | How many standard deviations today's price is from the N-day mean |

---

## Inputs

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Lookback period | `N` | **20** | Number of trading days for all indicators |
| Standard deviation multiplier | `K` | **2** | Band width in standard deviations |

---

## Indicator Definitions

### Simple Moving Average (SMA)

```
μ(N) = ( C(t) + C(t-1) + ... + C(t-N+1) ) / N
```

| Symbol | Definition |
|--------|------------|
| `μ(N)` | The resulting SMA value — the mean price over the window |
| `C(t)` | Closing price on the current day |
| `C(t-1) ... C(t-N+1)` | Closing prices on each of the previous N-1 days |
| `N` | Number of days in the lookback window |

The mean price over the last N days. This is the "equilibrium" the strategy expects price to revert to.

---

### Bollinger Bands

```
d(i)            = C(i) − μ(N)
σ²(N)           = (1/N) × Σ d(i)²       for i = t-N+1 to t
σ(N)            = √σ²(N)
Middle Band(t)  = μ(N)
Upper Band(t)   = μ(N) + K × σ(N)
Lower Band(t)   = μ(N) − K × σ(N)
Z(t)            = ( C(t) − μ(N) ) / σ(N)
```

| Symbol | Definition |
|--------|------------|
| `d(i)` | Deviation of day i's close from the N-day mean |
| `σ²(N)` | Variance — average of squared deviations over N days |
| `σ(N)` | Standard deviation — square root of variance, in price units (dollars) |
| `μ(N)` | The middle band — the N-day SMA |
| `K` | Number of standard deviations that define the band edges (default: 2) |
| `Z(t)` | Z-score — how many standard deviations today's price sits from the mean |

A signal fires when \|Z(t)\| > K. The bands self-adjust to volatility — wider when price has been volatile, narrower when calm.

---

## Signal Rules (Current)

### Buy Signal ▲
All of the following must be true:

```
1. C(t)   < Lower Band(t)      ← price has broken below the lower band TODAY
2. C(t-1) ≥ Lower Band(t-1)    ← price was still inside the band YESTERDAY
```

| Symbol | Definition |
|--------|------------|
| `C(t)` | Today's closing price |
| `C(t-1)` | Yesterday's closing price |
| `Lower Band(t)` | μ(N) − K × σ(N) calculated on today's N-day window |
| `Lower Band(t-1)` | μ(N) − K × σ(N) calculated on yesterday's N-day window |

This fires only on the **first day** price crosses below the lower Bollinger Band. It does not repeat while price remains below the band.

### Sell Signal ▼
All of the following must be true:

```
1. C(t)   > Upper Band(t)      ← price has broken above the upper band TODAY
2. C(t-1) ≤ Upper Band(t-1)    ← price was still inside the band YESTERDAY
```

| Symbol | Definition |
|--------|------------|
| `C(t)` | Today's closing price |
| `C(t-1)` | Yesterday's closing price |
| `Upper Band(t)` | μ(N) + K × σ(N) calculated on today's N-day window |
| `Upper Band(t-1)` | μ(N) + K × σ(N) calculated on yesterday's N-day window |

This fires only on the **first day** price crosses above the upper Bollinger Band.

---

## What the Rules Currently Ignore
The following factors are **not yet incorporated** into signal logic:

- Volume — is the move backed by conviction?
- Trend filter — is the broader trend up or down?
- Gap opens — overnight jumps that aren't "real" intraday moves
- Fundamental events — earnings, FDA announcements, news
- Stop-loss — no exit rule if the trade goes wrong
- Position sizing — no rule for how much to buy/sell

---

## Planned Enhancements
- [ ] Add volume filter: only signal if volume > N-day average volume
- [ ] Add trend filter: only buy if price is above 200-day SMA
- [ ] Define stop-loss rule: exit if price falls X% below entry
- [ ] Define take-profit rule: exit when price returns to SMA (middle band)
- [ ] Backtest all rules against historical GSIT data

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-02 | Initial rules — Bollinger Band crossover signals only |
| 1.1 | 2026-06-02 | Changed RSI period from fixed R=14 to R=N. Added full variable definitions and derivation notes. |
| 1.2 | 2026-06-02 | Added Open Questions section. Flagged RSI thresholds 70/30 for future GSIT-specific calibration. |
| 1.3 | 2026-06-02 | Added inline variable definition tables below every equation throughout the document. |
| 1.4 | 2026-06-02 | Removed RSI entirely — variable definitions, inputs, indicator section, planned enhancements, open questions, and derivation notes. |
