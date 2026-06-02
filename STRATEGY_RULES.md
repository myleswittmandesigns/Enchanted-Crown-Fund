# Enchanted Crown Fund — Mean Reversion Strategy Rules

## Overview
A mean reversion strategy assumes that price, after deviating significantly from its historical average, will tend to return to that average. Buy signals fire when price is statistically too low; sell signals fire when price is statistically too high.

---

## Variable Definitions

| Symbol | Name | Description |
|--------|------|-------------|
| `t` | Time index | The current trading day |
| `C(t)` | Closing price | The closing price of the asset on day t |
| `Δ(t)` | Daily change | C(t) − C(t−1) — the raw price move each day |
| `U(t)` | Daily gain | max(Δ(t), 0) — positive moves only |
| `D(t)` | Daily loss | max(−Δ(t), 0) — negative moves only (always positive) |
| `N` | Lookback period | Number of trading days for SMA, Bollinger Bands, and RSI |
| `K` | Std dev multiplier | How many standard deviations define the band edges |
| `R` | RSI period | Number of days used to calculate RSI — set equal to N |
| `μ(N)` | SMA | Simple moving average of closing prices over N days |
| `d(i)` | Deviation | C(i) − μ(N) — how far day i's close sits from the mean |
| `σ(N)` | Std deviation | Standard deviation of closing prices over N days |
| `σ²(N)` | Variance | Mean of squared deviations over N days |
| `Z(t)` | Z-score | How many standard deviations today's price is from the N-day mean |
| `Ū(R)` | Average gain | Mean of all daily gains U(t) over R days |
| `D̄(R)` | Average loss | Mean of all daily losses D(t) over R days |
| `RS` | Relative Strength | Ratio of average gains to average losses over R days |
| `RSI_low` | Oversold threshold | RSI below this value = oversold condition |
| `RSI_high` | Overbought threshold | RSI above this value = overbought condition |

---

## Inputs

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Lookback period | `N` | 20 | Number of trading days for all indicators |
| Standard deviation multiplier | `K` | 2 | Band width in standard deviations |
| RSI period | `R` | **= N** | Set equal to N — see derivation notes below |
| RSI oversold threshold | `RSI_low` | 30 | RSI below this = oversold |
| RSI overbought threshold | `RSI_high` | 70 | RSI above this = overbought |

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

### Relative Strength Index (RSI)

```
Ū(R)  = (1/R) × Σ U(t-i)    for i = 0 to R-1
D̄(R)  = (1/R) × Σ D(t-i)    for i = 0 to R-1
RS    = Ū(R) / D̄(R)
RSI   = 100 × Ū(R) / ( Ū(R) + D̄(R) )
```

| Symbol | Definition |
|--------|------------|
| `Ū(R)` | Average daily gain over R days |
| `D̄(R)` | Average daily loss over R days (positive value) |
| `U(t-i)` | Gain on day t-i = max(Δ(t-i), 0) |
| `D(t-i)` | Loss on day t-i = max(−Δ(t-i), 0) |
| `R` | RSI lookback period — set equal to N |
| `RS` | Relative Strength — ratio of average gain to average loss |
| `RSI` | Final value 0–100: fraction of total movement that was upward |

RSI = 100 means every day was up. RSI = 0 means every day was down. RSI = 50 means gains and losses were equal.

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
- RSI confirmation — is momentum aligned with the signal?
- Trend filter — is the broader trend up or down?
- Gap opens — overnight jumps that aren't "real" intraday moves
- Fundamental events — earnings, FDA announcements, news
- Stop-loss — no exit rule if the trade goes wrong
- Position sizing — no rule for how much to buy/sell

---

## Planned Enhancements
- [ ] Require RSI < `RSI_low` to confirm a buy signal
- [ ] Require RSI > `RSI_high` to confirm a sell signal
- [ ] Add volume filter: only signal if volume > N-day average volume
- [ ] Add trend filter: only buy if price is above 200-day SMA
- [ ] Define stop-loss rule: exit if price falls X% below entry
- [ ] Define take-profit rule: exit when price returns to SMA (middle band)
- [ ] Backtest all rules against historical GSIT data

---

## Open Questions

### RSI Thresholds — Revisit Later
**Current values:** `RSI_low = 30`, `RSI_high = 70`

These are Wilder's original empirical defaults (1978) and are the universal starting point — but they are **not mathematically derived**. They represent a rough historical observation that RSI rarely sustains above 70 or below 30 across broad market data.

**The problem:** these thresholds were calibrated on large-cap, liquid, diversified assets. GSIT is a small-cap biotech with high volatility and binary event risk. Its RSI distribution may behave very differently — extremes may be more frequent, or the meaningful threshold may sit at 60/40 rather than 70/30.

**Action item:** once enough historical signal data is available, analyze the actual RSI distribution for GSIT specifically and derive custom thresholds from that data rather than inheriting Wilder's defaults. The goal is thresholds that reflect *this asset's* behavior, not the average asset's behavior.

---

## Derivation Notes — Why R = N

### The core insight
Both RSI and Bollinger Bands are derived from the same underlying raw material: the sequence of daily gains U(t) and losses D(t) over a window of days. Since both indicators reduce to functions of the same data, they should operate over the same window to remain mathematically consistent.

### RSI reduced to its essence
```
RSI = 100 × Ū(R) / ( Ū(R) + D̄(R) )
    = 100 × (average gain) / (average absolute move)   over R days
```

| Symbol | Definition |
|--------|------------|
| `Ū(R)` | Average daily gain over R days |
| `D̄(R)` | Average daily loss over R days |
| `R` | Lookback window — set equal to N |

RSI answers: of all the price movement that occurred over R days, what fraction was upward?

### Bollinger Z-score reduced to its essence
```
C(t) − μ(N) = (1/N) × Σ ( C(t) − C(t-i) )   for i = 1 to N-1

Each term C(t) − C(t-i) = Σ Δ(t-j)           (cumulative change from day t-i to today)
                         = Σ ( U(t-j) − D(t-j) )
```

| Symbol | Definition |
|--------|------------|
| `C(t) − μ(N)` | Price displacement from the N-day mean |
| `C(t) − C(t-i)` | Cumulative price change from day t-i to today |
| `Δ(t-j)` | Daily change on day t-j |
| `U(t-j), D(t-j)` | Gain and loss components of that daily change |

So the Z-score is driven by the accumulated net gains and losses over the N-day window — the exact same U(t) and D(t) series that RSI uses.

### The window mismatch problem
When R ≠ N, the two indicators look at different slices of history:

```
Bollinger (N=50):  |-------------- 50 days --------------|
RSI (R=14):                                  |--- 14 ---|
```

Price can be statistically extended on the 50-day view (Bollinger fires) while the last 14 days are a quiet consolidation (RSI reads neutral). The conflict is not a market signal — it is an artifact of mismatched windows.

### The proof
When R = N, both indicators draw from the same set of {U(t-i), D(t-i)} values. Their covariance is maximized and their signals are naturally aligned. A buy or sell signal confirmed by both indicators is describing the same underlying phenomenon — not two different time horizons accidentally agreeing.

**Conclusion: R = N is the mathematically consistent choice. A fixed R introduces artificial decorrelation between indicators that are measuring the same thing.**

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-02 | Initial rules — Bollinger Band crossover signals only |
| 1.1 | 2026-06-02 | Changed RSI period from fixed R=14 to R=N. Added full variable definitions and derivation notes. |
| 1.2 | 2026-06-02 | Added Open Questions section. Flagged RSI thresholds 70/30 for future GSIT-specific calibration. |
| 1.3 | 2026-06-02 | Added inline variable definition tables below every equation throughout the document. |
