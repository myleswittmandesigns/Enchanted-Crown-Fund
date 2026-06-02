import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enchanted Crown Fund — Data Visualizer",
    page_icon="👑",
    layout="wide",
)

st.title("👑 Enchanted Crown Fund")
st.subheader("Daily High / Low Visualizer")

# ── Load tickers from data/ ───────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
csv_files = sorted(DATA_DIR.glob("*_daily_high_low.csv"))
tickers = [f.stem.replace("_daily_high_low", "") for f in csv_files]

if not tickers:
    st.error("No ticker CSVs found in the data/ directory.")
    st.stop()

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    selected = st.multiselect("Tickers", tickers, default=tickers)

    st.divider()
    st.markdown("**Date Range**")
    all_dates = []
    for t in tickers:
        df = pd.read_csv(DATA_DIR / f"{t}_daily_high_low.csv", parse_dates=["Date"])
        all_dates += [df["Date"].min(), df["Date"].max()]

    global_min = min(all_dates).date()
    global_max = max(all_dates).date()

    start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
    end_date   = st.date_input("To",   value=global_max, min_value=global_min, max_value=global_max)

if not selected:
    st.info("Select at least one ticker from the sidebar.")
    st.stop()

# ── Build charts ──────────────────────────────────────────────────────────────
for ticker in selected:
    df = pd.read_csv(DATA_DIR / f"{ticker}_daily_high_low.csv", parse_dates=["Date"])
    df = df[(df["Date"].dt.date >= start_date) & (df["Date"].dt.date <= end_date)]
    df = df.sort_values("Date")

    if df.empty:
        st.warning(f"{ticker}: no data in selected range.")
        continue

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
        line=dict(color="rgba(99, 110, 250, 0.8)", width=1),
        name="High",
        hovertemplate="%{x|%Y-%m-%d}<br>High: $%{y:.2f}<extra></extra>",
    ))

    # Low line
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Low"],
        mode="lines",
        line=dict(color="rgba(239, 85, 59, 0.8)", width=1),
        name="Low",
        hovertemplate="%{x|%Y-%m-%d}<br>Low: $%{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"{ticker} — Daily High/Low Range", font=dict(size=18)),
        xaxis=dict(
            title="Date",
            rangeslider=dict(visible=True),
            type="date",
        ),
        yaxis=dict(title="Price (USD)", tickprefix="$"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("All-Time High",  f"${df['High'].max():.2f}")
    col2.metric("All-Time Low",   f"${df['Low'].min():.2f}")
    col3.metric("Avg Daily Range",f"${(df['High'] - df['Low']).mean():.2f}")
    col4.metric("Latest Close*",  f"${df['Low'].iloc[-1]:.2f} – ${df['High'].iloc[-1]:.2f}")

    st.caption(f"Showing {len(df):,} trading days · {df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")
    st.divider()

st.caption("Data source: Yahoo Finance · Updates daily at 6pm ET on weekdays")
