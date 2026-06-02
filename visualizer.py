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

# ── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container {
        padding: 1rem 1rem 2rem 1rem !important;
        max-width: 100% !important;
    }
    .stMultiSelect, .stDateInput { font-size: 1rem !important; }
    [data-testid="metric-container"] {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.5rem;
    }
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.1rem !important; }
    .streamlit-expanderHeader {
        font-size: 1rem !important;
        padding: 0.75rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("👑 Enchanted Crown Fund")
st.subheader("Candlestick Chart")

# ── Load tickers ──────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
csv_files = sorted(DATA_DIR.glob("*_daily_high_low.csv"))
tickers = [f.stem.replace("_daily_high_low", "") for f in csv_files]

if not tickers:
    st.error("No ticker CSVs found in the data/ directory.")
    st.stop()

# ── Date range across all tickers ────────────────────────────────────────────
all_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    all_dates += [df["Date"].min(), df["Date"].max()]
global_min = min(all_dates).date()
global_max = max(all_dates).date()

# ── Controls ──────────────────────────────────────────────────────────────────
with st.expander("⚙️ Settings", expanded=False):
    btn_col1, btn_col2, _ = st.columns([1, 1, 4])
    if btn_col1.button("Select All"):
        st.session_state["selected_tickers"] = tickers
    if btn_col2.button("Deselect All"):
        st.session_state["selected_tickers"] = []

    selected = st.multiselect(
        "Tickers",
        options=tickers,
        default=st.session_state.get("selected_tickers", tickers),
        key="selected_tickers",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
    with col_b:
        end_date = st.date_input("To", value=global_max, min_value=global_min, max_value=global_max)

if not selected:
    st.info("Tap ⚙️ Settings above and select at least one ticker.")
    st.stop()

# ── Ticker colors ─────────────────────────────────────────────────────────────
PALETTE = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
COLORS = {ticker: PALETTE[i % len(PALETTE)] for i, ticker in enumerate(tickers)}

# ── Build overlaid candlestick chart ─────────────────────────────────────────
fig = go.Figure()

for ticker in selected:
    df = pd.read_csv(DATA_DIR / f"{ticker}_daily_high_low.csv", parse_dates=["Date"])
    df = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
    df = df.sort_values("Date")

    if df.empty:
        st.warning(f"{ticker}: no data in selected range.")
        continue

    color = COLORS.get(ticker, "#636EFA")

    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name=ticker,
        increasing=dict(line=dict(color=color), fillcolor=color),
        decreasing=dict(line=dict(color=color), fillcolor="rgba(0,0,0,0)"),
    ))

fig.update_layout(
    xaxis=dict(
        rangeslider=dict(visible=True, thickness=0.06),
        type="date",
        tickformat="%b %Y",
        rangeselector=dict(
            buttons=[
                dict(count=1,  label="1M",  step="month", stepmode="backward"),
                dict(count=6,  label="6M",  step="month", stepmode="backward"),
                dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                dict(count=5,  label="5Y",  step="year",  stepmode="backward"),
                dict(step="all", label="All"),
            ],
            bgcolor="#f0f0f0",
            activecolor="#636EFA",
            font=dict(size=11),
        ),
    ),
    yaxis=dict(tickprefix="$", automargin=True, fixedrange=False),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=450,
    margin=dict(l=10, r=10, t=40, b=10),
    dragmode="pan",
)

st.plotly_chart(fig, use_container_width=True)

# ── Per-ticker summary stats ──────────────────────────────────────────────────
for ticker in selected:
    df = pd.read_csv(DATA_DIR / f"{ticker}_daily_high_low.csv", parse_dates=["Date"])
    df = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
    df = df.sort_values("Date")
    if df.empty:
        continue

    st.markdown(f"**{ticker}**")
    col1, col2 = st.columns(2)
    col1.metric("All-Time High",   f"${df['High'].max():.2f}")
    col2.metric("All-Time Low",    f"${df['Low'].min():.2f}")
    col1.metric("Avg Daily Range", f"${(df['High'] - df['Low']).mean():.2f}")
    latest = df.iloc[-1]
    delta = latest["Close"] - latest["Open"]
    col2.metric("Latest Close", f"${latest['Close']:.2f}", f"{delta:+.2f}")
    st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────
latest_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    latest_dates.append(df["Date"].max())
most_recent = max(latest_dates).strftime("%B %d, %Y")

st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")
