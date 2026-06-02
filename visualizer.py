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
    .stMultiSelect, .stDateInput, .stNumberInput { font-size: 1rem !important; }
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
st.subheader("Mean Reversion Strategy Visualizer")

# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_bollinger(close: pd.Series, n: int):
    sma   = close.rolling(n).mean()
    std   = close.rolling(n).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    return sma, upper, lower


def compute_signals(close: pd.Series, upper: pd.Series, lower: pd.Series):
    prev_close = close.shift(1)
    buy  = (close < lower) & (prev_close >= lower.shift(1))   # crossed below lower band
    sell = (close > upper) & (prev_close <= upper.shift(1))   # crossed above upper band
    return buy, sell


# ── Load tickers ──────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
csv_files = sorted(DATA_DIR.glob("*_daily_high_low.csv"))
tickers = [f.stem.replace("_daily_high_low", "") for f in csv_files]

if not tickers:
    st.error("No ticker CSVs found in the data/ directory.")
    st.stop()

all_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    all_dates += [df["Date"].min(), df["Date"].max()]
global_min = min(all_dates).date()
global_max = max(all_dates).date()

# ── Settings ──────────────────────────────────────────────────────────────────
with st.expander("⚙️ Settings", expanded=False):

    # Ticker selector
    btn1, btn2, _ = st.columns([1, 1, 4])
    if btn1.button("Select All"):
        st.session_state["selected_tickers"] = tickers
    if btn2.button("Deselect All"):
        st.session_state["selected_tickers"] = []

    selected = st.multiselect(
        "Tickers",
        options=tickers,
        default=st.session_state.get("selected_tickers", tickers),
        key="selected_tickers",
    )

    # Date range
    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
    with col_b:
        end_date = st.date_input("To", value=global_max, min_value=global_min, max_value=global_max)

    st.divider()

    # Indicator settings
    st.markdown("**Lookback period (days)**")
    p1, p2, p3, p4 = st.columns(4)
    if p1.button("10"):
        st.session_state["n_days"] = 10
    if p2.button("20"):
        st.session_state["n_days"] = 20
    if p3.button("50"):
        st.session_state["n_days"] = 50
    if p4.button("200"):
        st.session_state["n_days"] = 200

    col_c, col_d = st.columns(2)
    with col_c:
        n_days = st.number_input(
            "Or type a value",
            min_value=5, max_value=500,
            value=st.session_state.get("n_days", 20),
            step=1,
            key="n_days",
        )
    with col_d:
        show_signals = st.toggle("Show buy/sell signals", value=True)

if not selected:
    st.info("Tap ⚙️ Settings above and select at least one ticker.")
    st.stop()

PALETTE = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
COLORS  = {ticker: PALETTE[i % len(PALETTE)] for i, ticker in enumerate(tickers)}

# ── Per-ticker charts ─────────────────────────────────────────────────────────
for ticker in selected:
    df = pd.read_csv(DATA_DIR / f"{ticker}_daily_high_low.csv", parse_dates=["Date"])
    df = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
    df = df.sort_values("Date").reset_index(drop=True)

    if df.empty:
        st.warning(f"{ticker}: no data in selected range.")
        continue

    color = COLORS.get(ticker, "#636EFA")

    # Compute indicators
    sma, upper_bb, lower_bb = compute_bollinger(df["Close"], int(n_days))
    rsi = compute_rsi(df["Close"])
    buy_signals, sell_signals = compute_signals(df["Close"], upper_bb, lower_bb)

    # ── Subplot: 2 rows (candlestick + RSI) ──────────────────────────────────
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.04,
    )

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price",
        increasing=dict(line=dict(color=color), fillcolor=color),
        decreasing=dict(line=dict(color=color), fillcolor="rgba(0,0,0,0)"),
        showlegend=False,
    ), row=1, col=1)

    # SMA
    fig.add_trace(go.Scatter(
        x=df["Date"], y=sma,
        mode="lines",
        name=f"SMA({n_days})",
        line=dict(color="orange", width=1.5, dash="solid"),
    ), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(
        x=df["Date"], y=upper_bb,
        mode="lines",
        name=f"BB Upper",
        line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
        showlegend=True,
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["Date"], y=lower_bb,
        mode="lines",
        name=f"BB Lower",
        line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(150,150,150,0.07)",
        showlegend=True,
    ), row=1, col=1)

    # Buy/sell signals
    if show_signals:
        fig.add_trace(go.Scatter(
            x=df["Date"][buy_signals],
            y=df["Low"][buy_signals] * 0.98,
            mode="markers",
            name="Buy signal",
            marker=dict(symbol="triangle-up", size=10, color="lime", line=dict(color="green", width=1)),
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=df["Date"][sell_signals],
            y=df["High"][sell_signals] * 1.02,
            mode="markers",
            name="Sell signal",
            marker=dict(symbol="triangle-down", size=10, color="red", line=dict(color="darkred", width=1)),
        ), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=df["Date"], y=rsi,
        mode="lines",
        name="RSI(14)",
        line=dict(color="purple", width=1.5),
        showlegend=False,
    ), row=2, col=1)

    # RSI overbought/oversold lines
    for level, label in [(70, "Overbought"), (30, "Oversold")]:
        fig.add_hline(
            y=level, row=2, col=1,
            line=dict(color="gray", width=1, dash="dash"),
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(size=10, color="gray"),
        )

    fig.update_layout(
        title=dict(text=f"{ticker} — Mean Reversion", font=dict(size=16)),
        xaxis2=dict(
            rangeslider=dict(visible=True, thickness=0.05),
            type="date",
            tickformat="%b %Y",
            rangeselector=dict(
                buttons=[
                    dict(count=1,  label="1M", step="month", stepmode="backward"),
                    dict(count=6,  label="6M", step="month", stepmode="backward"),
                    dict(count=1,  label="1Y", step="year",  stepmode="backward"),
                    dict(count=5,  label="5Y", step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor="#f0f0f0",
                activecolor="#636EFA",
                font=dict(size=10),
                y=1.18,
            ),
        ),
        yaxis=dict(tickprefix="$", automargin=True, domain=[0.32, 1.0]),
        yaxis2=dict(title="RSI", range=[0, 100], automargin=True),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1, font=dict(size=11)),
        height=580,
        margin=dict(l=10, r=10, t=80, b=10),
        dragmode="pan",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary stats
    col1, col2 = st.columns(2)
    col1.metric("All-Time High",   f"${df['High'].max():.2f}")
    col2.metric("All-Time Low",    f"${df['Low'].min():.2f}")
    col1.metric("Avg Daily Range", f"${(df['High'] - df['Low']).mean():.2f}")
    latest = df.iloc[-1]
    delta  = latest["Close"] - latest["Open"]
    col2.metric("Latest Close",    f"${latest['Close']:.2f}", f"{delta:+.2f}")

    if show_signals:
        n_buys  = buy_signals.sum()
        n_sells = sell_signals.sum()
        st.caption(f"Signals in range: {n_buys} buy ▲  ·  {n_sells} sell ▼")

    st.caption(f"{len(df):,} trading days · {df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")
    st.divider()

# ── 3D Surface Explorer ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🧊 3D Surface Explorer — GSIT (Last Month)")
st.caption("Axes: Date (X) · Lookback Period N (Y) · Value (Z) — rotate, zoom, hover to explore layer by layer")

layer = st.radio(
    "Select layer",
    ["RSI", "SMA", "% vs SMA"],
    horizontal=True,
)

file_map = {
    "RSI":      ("GSIT_3D_RSI.csv",       "RSI Value",            "RdYlGn",  None),
    "SMA":      ("GSIT_3D_SMA.csv",        "SMA Price ($)",        "Blues",   None),
    "% vs SMA": ("GSIT_3D_PCT_vs_SMA.csv", "% Above/Below SMA",   "RdYlGn",  None),
}

fname, zlabel, colorscale, _ = file_map[layer]
mat = pd.read_csv(DATA_DIR / fname, index_col="Date")

# Axes
x_dates  = mat.index.tolist()                          # 21 dates
y_n      = [int(c.split("_")[1]) for c in mat.columns] # N values
z_values = mat.values                                   # 21 × 46

fig3d = go.Figure(data=[go.Surface(
    x=x_dates,
    y=y_n,
    z=z_values,
    colorscale=colorscale,
    colorbar=dict(title=zlabel, thickness=15),
    hovertemplate="Date: %{x}<br>N: %{y}<br>" + zlabel + ": %{z:.2f}<extra></extra>",
)])

fig3d.update_layout(
    scene=dict(
        xaxis=dict(title="Date", tickangle=45),
        yaxis=dict(title="Lookback N (days)"),
        zaxis=dict(title=zlabel),
        camera=dict(eye=dict(x=1.6, y=-1.6, z=0.8)),
    ),
    height=550,
    margin=dict(l=0, r=0, t=30, b=0),
)

st.plotly_chart(fig3d, use_container_width=True)

# Flat table view — slice by date or N
st.markdown("### 📋 Slice the data")
slice_by = st.radio("Slice by", ["Date (fix a day, see all N)", "N (fix a lookback, see all days)"], horizontal=True)

if slice_by.startswith("Date"):
    chosen_date = st.selectbox("Select date", x_dates, index=len(x_dates)-1)
    row = mat.loc[chosen_date].rename("Value").reset_index()
    row.columns = ["Lookback N", zlabel]
    row["Lookback N"] = y_n
    st.dataframe(row.set_index("Lookback N").style.format("{:.2f}"), use_container_width=True)
else:
    chosen_n = st.selectbox("Select N", y_n, index=5)
    col_name  = [c for c in mat.columns if c.endswith(f"_{chosen_n}")][0]
    col_data  = mat[[col_name]].copy()
    col_data.columns = [zlabel]
    st.dataframe(col_data.style.format("{:.2f}"), use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
latest_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    latest_dates.append(df["Date"].max())
most_recent = max(latest_dates).strftime("%B %d, %Y")
st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")
