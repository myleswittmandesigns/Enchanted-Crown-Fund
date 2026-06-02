import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enchanted Crown Fund",
    page_icon="👑",
    layout="centered",  # centered works better on mobile than wide
)

# ── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Tighter padding on small screens */
    .block-container {
        padding: 1rem 1rem 2rem 1rem !important;
        max-width: 100% !important;
    }
    /* Larger tap targets for inputs */
    .stMultiSelect, .stDateInput {
        font-size: 1rem !important;
    }
    /* Metric cards: wrap nicely on small screens */
    [data-testid="metric-container"] {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 0.6rem 0.8rem;
        margin-bottom: 0.5rem;
    }
    /* Smaller title on mobile */
    h1 { font-size: 1.6rem !important; }
    h2 { font-size: 1.1rem !important; }
    /* Make expander label bigger for easier tapping */
    .streamlit-expanderHeader {
        font-size: 1rem !important;
        padding: 0.75rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("👑 Enchanted Crown Fund")
st.subheader("Daily High / Low Visualizer")

# ── Load tickers from data/ ───────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
csv_files = sorted(DATA_DIR.glob("*_daily_high_low.csv"))
tickers = [f.stem.replace("_daily_high_low", "") for f in csv_files]

if not tickers:
    st.error("No ticker CSVs found in the data/ directory.")
    st.stop()

# ── Load date range across all tickers ───────────────────────────────────────
all_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    all_dates += [df["Date"].min(), df["Date"].max()]
global_min = min(all_dates).date()
global_max = max(all_dates).date()

# ── Controls in an expander (collapses on mobile to save space) ───────────────
with st.expander("⚙️ Settings", expanded=False):
    selected = st.multiselect("Tickers", tickers, default=tickers)
    col_a, col_b = st.columns(2)
    with col_a:
        start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
    with col_b:
        end_date = st.date_input("To", value=global_max, min_value=global_min, max_value=global_max)

if not selected:
    st.info("Tap ⚙️ Settings above and select at least one ticker.")
    st.stop()

# ── Build charts ──────────────────────────────────────────────────────────────
for ticker in selected:
    df = pd.read_csv(DATA_DIR / f"{ticker}_daily_high_low.csv", parse_dates=["Date"])
    df = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
    df = df.sort_values("Date")

    if df.empty:
        st.warning(f"{ticker}: no data in selected range.")
        continue

    st.markdown(f"### {ticker}")

    fig = go.Figure()

    # Shaded High/Low band
    fig.add_trace(go.Scatter(
        x=pd.concat([df["Date"], df["Date"][::-1]]),
        y=pd.concat([df["High"], df["Low"][::-1]]),
        fill="toself",
        fillcolor="rgba(99, 110, 250, 0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        hoverinfo="skip",
        name="High/Low Band",
    ))

    # High line
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["High"],
        mode="lines",
        line=dict(color="rgba(99, 110, 250, 0.9)", width=1.5),
        name="High",
        hovertemplate="%{x|%b %d %Y}<br>High: $%{y:.2f}<extra></extra>",
    ))

    # Low line
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Low"],
        mode="lines",
        line=dict(color="rgba(239, 85, 59, 0.9)", width=1.5),
        name="Low",
        hovertemplate="%{x|%b %d %Y}<br>Low: $%{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.08),
            type="date",
            tickformat="%b %Y",
        ),
        yaxis=dict(tickprefix="$", automargin=True),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=380,  # shorter height works better on mobile
        margin=dict(l=10, r=10, t=30, b=10),
        dragmode="pan",  # pan is easier than zoom on touch screens
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary stats — 2x2 grid instead of 4 columns (fits mobile)
    col1, col2 = st.columns(2)
    col1.metric("All-Time High",   f"${df['High'].max():.2f}")
    col2.metric("All-Time Low",    f"${df['Low'].min():.2f}")
    col1.metric("Avg Daily Range", f"${(df['High'] - df['Low']).mean():.2f}")
    col2.metric("Latest Range",    f"${df['Low'].iloc[-1]:.2f} – ${df['High'].iloc[-1]:.2f}")

    st.caption(f"{len(df):,} trading days · {df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")
    st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────
latest_dates = []
for t in tickers:
    df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
    latest_dates.append(df["Date"].max())
most_recent = max(latest_dates).strftime("%B %d, %Y")

st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")
