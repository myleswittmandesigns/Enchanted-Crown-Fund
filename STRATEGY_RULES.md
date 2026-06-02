# Enchanted Crown Fund — Mean Reversion Strategy Rules

## Overview
A mean reversion strategy assumes that price, after deviating significantly from its historical average, will tend to return to that average. Buy signals fire when price is statistically too low; sell signals fire when price is statistically too high.

---

## Inputs

| Parameter | Symbol | Default | Description |
|-----------|--------|---------|-------------|
| Lookback period | `N` | 20 | Number of trading days used to calculate the mean and standard deviation |
| Standard deviation multiplier | `K` | 2 | How many std deviations from the mean constitute an extreme |
| RSI period | `R` | 14 | Number of days used to calculate RSI |
| RSI oversold threshold | `RSI_low` | 30 | RSI below this = oversold |
| RSI overbought threshold | `RSI_high` | 70 | RSI above this = overbought |

---

## Indicator Definitions

### Simple Moving Average (SMA)
```
SMA(t) = ( Close(t) + Close(t-1) + ... + Close(t-N+1) ) / N
```
The mean price over the last N days. This is the "equilibrium" the strategy expects price to revert to.

### Bollinger Bands
```
Middle Band(t)  = SMA(t)
Upper Band(t)   = SMA(t) + K × StdDev(t)
Lower Band(t)   = SMA(t) - K × StdDev(t)

StdDev(t) = standard deviation of Close over the last N days
```
The bands define the expected range of normal price movement. Price outside the bands is statistically unusual.

### Relative Strength Index (RSI)
```
RSI(t) = 100 - ( 100 / ( 1 + RS ) )

RS          = Average Gain / Average Loss  (over R days)
Average Gain = EWM of daily gains over R days
Average Loss = EWM of daily losses over R days
```
RSI measures momentum on a 0–100 scale. Values below 30 suggest oversold conditions; above 70 suggests overbought.

---

## Signal Rules (Current)

### Buy Signal ▲
All of the following must be true:

```
1. Close(t)   < Lower Band(t)      ← price has broken below the lower band TODAY
2. Close(t-1) ≥ Lower Band(t-1)    ← price was still inside the band YESTERDAY
```
This fires only on the **first day** price crosses below the lower Bollinger Band. It does not repeat while price remains below the band.

### Sell Signal ▼
All of the following must be true:

```
1. Close(t)   > Upper Band(t)      ← price has broken above the upper band TODAY
2. Close(t-1) ≤ Upper Band(t-1)    ← price was still inside the band YESTERDAY
```
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

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-06-02 | Initial rules — Bollinger Band crossover signals only |
