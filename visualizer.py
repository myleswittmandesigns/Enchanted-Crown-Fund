import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

    def extract(symbol: str, fallback):
        # Match table rows like: | Lookback period | `N` | 20 |
        pattern = rf"\|\s*`{symbol}`\s*\|\s*\*{{0,2}}([0-9]+)\*{{0,2}}\s*\|"
        match = re.search(pattern, text)
        return int(match.group(1)) if match else fallback

    N       = extract("N",        20)
    K       = extract("K",        2)
    rsi_low = extract("RSI_low",  30)
    rsi_high= extract("RSI_high", 70)
    # R = N by definition in the rules
    return {"N": N, "K": K, "R": N, "RSI_low": rsi_low, "RSI_high": rsi_high}

params = load_strategy_params()
N        = params["N"]
K        = params["K"]
R        = params["R"]
RSI_LOW  = params["RSI_low"]
RSI_HIGH = params["RSI_high"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


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


# ── Load GSIT ─────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
df_full  = pd.read_csv(DATA_DIR / "GSIT_daily_high_low.csv", parse_dates=["Date"])
df_full  = df_full.sort_values("Date").reset_index(drop=True)

global_min = df_full["Date"].min().date()
global_max = df_full["Date"].max().date()

# ── Active strategy parameters (read-only display) ───────────────────────────
with st.expander("📋 Active Strategy Parameters", expanded=False):
    st.caption("Parameters are defined in `STRATEGY_RULES.md` and cannot be changed here.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("N (Lookback)", N)
    c2.metric("K (Std Dev ×)", K)
    c3.metric("R (RSI Period)", f"= N ({R})")
    c4.metric("RSI Oversold",  RSI_LOW)
    c5.metric("RSI Overbought",RSI_HIGH)

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
sma, upper_bb, lower_bb = compute_bollinger(df_full["Close"], N, K)
rsi                      = compute_rsi(df_full["Close"], period=R)
buy_signals, sell_signals= compute_signals(df_full["Close"], upper_bb, lower_bb)

mask         = (df_full["Date"].dt.date >= start_date) & (df_full["Date"].dt.date <= end_date)
sma          = sma[mask].reset_index(drop=True)
upper_bb     = upper_bb[mask].reset_index(drop=True)
lower_bb     = lower_bb[mask].reset_index(drop=True)
rsi          = rsi[mask].reset_index(drop=True)
buy_signals  = buy_signals[mask].reset_index(drop=True)
sell_signals = sell_signals[mask].reset_index(drop=True)

# ── Chart ─────────────────────────────────────────────────────────────────────
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.68, 0.32],
    vertical_spacing=0.04,
)

fig.add_trace(go.Candlestick(
    x=df["Date"],
    open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
    name="Price",
    increasing=dict(line=dict(color="#636EFA"), fillcolor="#636EFA"),
    decreasing=dict(line=dict(color="#636EFA"), fillcolor="rgba(0,0,0,0)"),
    showlegend=False,
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=df["Date"], y=sma,
    mode="lines", name=f"SMA({N})",
    line=dict(color="orange", width=1.5),
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=df["Date"], y=upper_bb,
    mode="lines", name=f"BB Upper (×{K}σ)",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
), row=1, col=1)

fig.add_trace(go.Scatter(
    x=df["Date"], y=lower_bb,
    mode="lines", name=f"BB Lower (×{K}σ)",
    line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
    fill="tonexty", fillcolor="rgba(150,150,150,0.07)",
), row=1, col=1)

if show_signals:
    fig.add_trace(go.Scatter(
        x=df["Date"][buy_signals], y=df["Low"][buy_signals] * 0.98,
        mode="markers", name="Buy",
        marker=dict(symbol="triangle-up", size=10, color="lime", line=dict(color="green", width=1)),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Date"][sell_signals], y=df["High"][sell_signals] * 1.02,
        mode="markers", name="Sell",
        marker=dict(symbol="triangle-down", size=10, color="red", line=dict(color="darkred", width=1)),
    ), row=1, col=1)

fig.add_trace(go.Scatter(
    x=df["Date"], y=rsi,
    mode="lines", name=f"RSI({R})",
    line=dict(color="purple", width=1.5),
    showlegend=False,
), row=2, col=1)

for level, label in [(RSI_HIGH, "Overbought"), (RSI_LOW, "Oversold")]:
    fig.add_hline(
        y=level, row=2, col=1,
        line=dict(color="gray", width=1, dash="dash"),
        annotation_text=label,
        annotation_position="right",
        annotation_font=dict(size=10, color="gray"),
    )

fig.update_layout(
    xaxis2=dict(
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
            bgcolor="#f0f0f0", activecolor="#636EFA", font=dict(size=10), y=1.18,
        ),
    ),
    yaxis=dict(tickprefix="$", automargin=True),
    yaxis2=dict(title=f"RSI({R})", range=[0, 100], automargin=True),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1, font=dict(size=11)),
    height=580,
    margin=dict(l=10, r=10, t=60, b=10),
    dragmode="pan",
)

st.plotly_chart(fig, use_container_width=True)

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

# ── Footer ────────────────────────────────────────────────────────────────────
most_recent = df_full["Date"].max().strftime("%B %d, %Y")
st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")
