import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enchanted Crown Fund",
    page_icon="👑",
    layout="centered",
)

st.markdown("""
<style>
    .block-container { padding: 1rem 1rem 2rem 1rem !important; max-width: 100% !important; }
    .stDateInput { font-size: 1rem !important; }
    [data-testid="metric-container"] {
        background: #f8f9fa; border-radius: 10px;
        padding: 0.6rem 0.8rem; margin-bottom: 0.5rem;
    }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.1rem !important; }
    .streamlit-expanderHeader { font-size: 1rem !important; padding: 0.75rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("👑 Enchanted Crown Fund")
st.subheader("GSIT — Mean Reversion Strategy")

# ── Load parameters from STRATEGY_RULES.md ───────────────────────────────────
def load_strategy_params() -> dict:
    rules_path = Path(__file__).parent / "STRATEGY_RULES.md"
    text = rules_path.read_text()

    def extract(symbol: str):
        pattern = rf"\|\s*`{symbol}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
        match = re.search(pattern, text)
        if not match:
            st.error(f"❌ Cannot find parameter `{symbol}` in STRATEGY_RULES.md. Please check the file.")
            st.stop()
        val = match.group(1)
        return float(val) if "." in val else int(val)

    N        = extract("N")
    K        = extract("K")
    StopPct  = extract("StopPct") / 100
    return {"N": N, "K": K, "StopPct": StopPct}

params   = load_strategy_params()
N        = params["N"]
K        = params["K"]
STOP_PCT = params["StopPct"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_bollinger(close: pd.Series, n: int, k: int):
    sma   = close.rolling(n).mean()
    std   = close.rolling(n).std()
    upper = sma + k * std
    lower = sma - k * std
    return sma, upper, lower


def compute_signals(close: pd.Series, upper: pd.Series, lower: pd.Series):
    buy  = (close < lower) & (close.shift(1) >= lower.shift(1))
    sell = (close > upper) & (close.shift(1) <= upper.shift(1))
    return buy, sell


def simulate_portfolio(df: pd.DataFrame, sma: pd.Series, lower_bb: pd.Series,
                       initial: float, stop_pct: float):
    balance  = initial
    in_trade = False
    entry_price = entry_date = shares = None
    trades = []

    for i in range(1, len(df)):
        close        = df["Close"].iloc[i]
        prev_close   = df["Close"].iloc[i - 1]
        cur_sma      = sma.iloc[i]
        cur_lower    = lower_bb.iloc[i]
        prev_lower   = lower_bb.iloc[i - 1]
        date         = df["Date"].iloc[i]

        if pd.isna(cur_sma) or pd.isna(cur_lower) or pd.isna(prev_lower):
            continue

        if not in_trade:
            if close < cur_lower and prev_close >= prev_lower:
                shares      = balance / close
                entry_price = close
                entry_date  = date
                in_trade    = True
        else:
            stop_price = entry_price * (1 - stop_pct)
            if close >= cur_sma:
                balance = shares * close
                trades.append({
                    "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                    "Entry $":     round(entry_price, 2),
                    "Exit Date":   date.strftime("%Y-%m-%d"),
                    "Exit $":      round(close, 2),
                    "Exit Reason": "Take Profit ✅",
                    "Return %":    round((close / entry_price - 1) * 100, 1),
                    "Balance $":   round(balance, 2),
                })
                in_trade = False
            elif close <= stop_price:
                balance = shares * close
                trades.append({
                    "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                    "Entry $":     round(entry_price, 2),
                    "Exit Date":   date.strftime("%Y-%m-%d"),
                    "Exit $":      round(close, 2),
                    "Exit Reason": "Stop Loss 🛑",
                    "Return %":    round((close / entry_price - 1) * 100, 1),
                    "Balance $":   round(balance, 2),
                })
                in_trade = False

    if in_trade:
        close   = df["Close"].iloc[-1]
        balance = shares * close
        trades.append({
            "Entry Date":  entry_date.strftime("%Y-%m-%d"),
            "Entry $":     round(entry_price, 2),
            "Exit Date":   "—",
            "Exit $":      round(close, 2),
            "Exit Reason": "Still Open 🟡",
            "Return %":    round((close / entry_price - 1) * 100, 1),
            "Balance $":   round(balance, 2),
        })

    return round(balance, 2), trades


# ── Load GSIT ─────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
df_full  = pd.read_csv(DATA_DIR / "GSIT_daily_high_low.csv", parse_dates=["Date"])
df_full  = df_full.sort_values("Date").reset_index(drop=True)

global_min = df_full["Date"].min().date()
global_max = df_full["Date"].max().date()

# ── Active strategy parameters (read-only display) ───────────────────────────
with st.expander("📋 Active Strategy Parameters", expanded=False):
    st.caption("Parameters are defined in `STRATEGY_RULES.md` and cannot be changed here.")
    c1, c2 = st.columns(2)
    c1.metric("N (Lookback)", N)
    c2.metric("K (Std Dev ×)", K)

# ── Date range + signal toggle ────────────────────────────────────────────────
with st.expander("⚙️ View Settings", expanded=False):
    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
    with col_b:
        end_date = st.date_input("To", value=global_max, min_value=global_min, max_value=global_max)
    show_signals = st.toggle("Show buy/sell signals", value=True)

# ── Filter to date range ──────────────────────────────────────────────────────
df = df_full[(df_full["Date"].dt.date >= start_date) & (df_full["Date"].dt.date <= end_date)].reset_index(drop=True)

if df.empty:
    st.warning("No data in selected date range.")
    st.stop()

# ── Compute indicators (full history for accuracy, slice after) ───────────────
sma, upper_bb, lower_bb  = compute_bollinger(df_full["Close"], N, K)
buy_signals, sell_signals = compute_signals(df_full["Close"], upper_bb, lower_bb)

mask         = (df_full["Date"].dt.date >= start_date) & (df_full["Date"].dt.date <= end_date)
sma          = sma[mask].reset_index(drop=True)
upper_bb     = upper_bb[mask].reset_index(drop=True)
lower_bb     = lower_bb[mask].reset_index(drop=True)
buy_signals  = buy_signals[mask].reset_index(drop=True)
sell_signals = sell_signals[mask].reset_index(drop=True)

# ── Main chart ────────────────────────────────────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df["Date"],
    open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
    name="Price",
    increasing=dict(line=dict(color="#636EFA"), fillcolor="#636EFA"),
    decreasing=dict(line=dict(color="#636EFA"), fillcolor="rgba(0,0,0,0)"),
    showlegend=False,
))

fig.add_trace(go.Scatter(
    x=df["Date"], y=sma,
    mode="lines", name=f"SMA({N})",
    line=dict(color="orange", width=1.5),
))

fig.add_trace(go.Scatter(
    x=df["Date"], y=upper_bb,
    mode="lines", name=f"BB Upper (×{K}σ)",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
))

fig.add_trace(go.Scatter(
    x=df["Date"], y=lower_bb,
    mode="lines", name=f"BB Lower (×{K}σ)",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
    fill="tonexty", fillcolor="rgba(150,150,150,0.07)",
))

if show_signals:
    fig.add_trace(go.Scatter(
        x=df["Date"][buy_signals], y=df["Low"][buy_signals] * 0.98,
        mode="markers", name="Buy",
        marker=dict(symbol="triangle-up", size=10, color="lime", line=dict(color="green", width=1)),
    ))

    fig.add_trace(go.Scatter(
        x=df["Date"][sell_signals], y=df["High"][sell_signals] * 1.02,
        mode="markers", name="Sell",
        marker=dict(symbol="triangle-down", size=10, color="red", line=dict(color="darkred", width=1)),
    ))

fig.update_layout(
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.05),
        type="date", tickformat="%b %Y",
        rangeselector=dict(
            buttons=[
                dict(count=1,  label="1M", step="month", stepmode="backward"),
                dict(count=6,  label="6M", step="month", stepmode="backward"),
                dict(count=1,  label="1Y", step="year",  stepmode="backward"),
                dict(count=5,  label="5Y", step="year",  stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#f0f0f0", activecolor="#636EFA", font=dict(size=10), y=1.08,
        ),
    ),
    yaxis=dict(tickprefix="$", automargin=True),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
    height=520,
    margin=dict(l=10, r=10, t=60, b=10),
    dragmode="pan",
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Summary stats ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
col1.metric("All-Time High",   f"${df['High'].max():.2f}")
col2.metric("All-Time Low",    f"${df['Low'].min():.2f}")
col1.metric("Avg Daily Range", f"${(df['High'] - df['Low']).mean():.2f}")
latest = df.iloc[-1]
delta  = latest["Close"] - latest["Open"]
col2.metric("Latest Close",    f"${latest['Close']:.2f}", f"{delta:+.2f}")

if show_signals:
    st.caption(f"Signals in range: {buy_signals.sum()} buy ▲  ·  {sell_signals.sum()} sell ▼")

st.caption(f"{len(df):,} trading days · {df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")

# ── Portfolio simulation ──────────────────────────────────────────────────────
st.divider()
st.markdown("### 💰 Portfolio Simulation")
st.caption(f"Buys on BB lower crossover · Exits at SMA (take profit) or −{int(STOP_PCT*100)}% (stop loss) · Full balance reinvested each trade")

initial_investment = st.number_input(
    "Initial investment ($)",
    min_value=1.0, value=5000.0, step=100.0, format="%.2f"
)

final_balance, trades = simulate_portfolio(df, sma, lower_bb, initial_investment, STOP_PCT)

if not trades:
    st.info("No completed trades in the selected date range.")
else:
    total_return_pct = (final_balance / initial_investment - 1) * 100
    closed = [t for t in trades if t["Exit Reason"] != "Still Open 🟡"]
    wins   = [t for t in closed if t["Return %"] > 0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Final Balance",  f"${final_balance:,.2f}")
    m2.metric("Total Return",   f"{total_return_pct:+.1f}%")
    m3.metric("Trades",         len(trades))
    m4.metric("Win Rate",       f"{len(wins)/len(closed)*100:.0f}%" if closed else "—")

    trade_df = pd.DataFrame(trades)
    trade_df.insert(0, "#", range(1, len(trade_df) + 1))
    st.dataframe(trade_df, use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
most_recent = df_full["Date"].max().strftime("%B %d, %Y")
st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")
