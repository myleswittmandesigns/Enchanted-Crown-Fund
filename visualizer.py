import re
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enchanted Crown Fund",
    page_icon="ECF",
    layout="centered",
)

st.markdown("""
<style>
/* ── Professional fintech theme ──────────────────────────────────────────── */

/* Import Inter font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important; }

/* Main container */
.block-container {
    padding: 1.25rem 1.5rem 2rem 1.5rem !important;
    max-width: 100% !important;
}

/* Title */
h1 {
    font-size: 1.4rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: #0f172a !important;
}
h2 { font-size: 1.05rem !important; font-weight: 600 !important; color: #1e293b !important; }
h3 { font-size: 0.92rem !important; font-weight: 600 !important; color: #334155 !important; letter-spacing: 0.03em !important; text-transform: uppercase !important; }

/* Subheader */
[data-testid="stSubheader"] { color: #64748b !important; font-size: 0.85rem !important; font-weight: 400 !important; }

/* Metric cards — clean fintech style */
[data-testid="metric-container"] {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 6px !important;
    padding: 0.65rem 0.85rem !important;
    margin-bottom: 0.5rem !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.67rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: #64748b !important;
}
[data-testid="stMetricValue"] {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.01em !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.72rem !important;
    font-weight: 500 !important;
}

/* Tabs — clean underline style */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important;
    border-bottom: 2px solid #e2e8f0 !important;
    background: transparent !important;
    overflow-x: auto !important;
    overflow-y: hidden !important;
    -webkit-overflow-scrolling: touch !important;
    flex-wrap: nowrap !important;
    scrollbar-width: none !important;
}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none !important; }
.stTabs [data-baseweb="tab"] {
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
    color: #64748b !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    padding: 0.6rem 1rem !important;
    background: transparent !important;
    white-space: nowrap !important;
}
.stTabs [aria-selected="true"] {
    color: #0f172a !important;
    border-bottom: 2px solid #0f172a !important;
    font-weight: 600 !important;
}

/* Expanders */
.streamlit-expanderHeader {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: #475569 !important;
    padding: 0.6rem 0.75rem !important;
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 4px !important;
}

/* Dividers */
hr { border-color: #e2e8f0 !important; margin: 1rem 0 !important; }

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.72rem !important;
    color: #94a3b8 !important;
    line-height: 1.5 !important;
}

/* Info/warning boxes — cleaner */
[data-testid="stInfo"] {
    background: #f0f9ff !important;
    border-left: 3px solid #0ea5e9 !important;
    border-radius: 0 4px 4px 0 !important;
    font-size: 0.82rem !important;
}
[data-testid="stWarning"] {
    background: #fffbeb !important;
    border-left: 3px solid #f59e0b !important;
    border-radius: 0 4px 4px 0 !important;
    font-size: 0.82rem !important;
}

/* Buttons */
.stButton button {
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    text-transform: uppercase !important;
    border-radius: 4px !important;
    padding: 0.35rem 0.75rem !important;
    border: 1px solid #cbd5e1 !important;
    background: #f8fafc !important;
    color: #334155 !important;
}
.stButton button:hover {
    background: #f1f5f9 !important;
    border-color: #94a3b8 !important;
}

/* Dataframes */
[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 6px !important;
    overflow: hidden !important;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
}

/* Number input */
[data-testid="stNumberInput"] input {
    font-size: 0.85rem !important;
    border-radius: 4px !important;
}

/* Selectbox */
[data-testid="stSelectbox"] { font-size: 0.85rem !important; }

/* Radio */
[data-testid="stRadio"] label { font-size: 0.82rem !important; }

/* ── Mobile — portrait phones (≤ 768 px) ─────────────────────────────────── */
@media screen and (max-width: 768px) {
    .block-container { padding: 0.75rem 0.75rem 1.25rem !important; }

    .stTabs [data-baseweb="tab"] {
        font-size: 0.68rem !important;
        padding: 0.5rem 0.6rem !important;
    }

    .stHorizontalBlock {
        flex-wrap: wrap !important;
        gap: 0.4rem 0.5rem !important;
    }
    [data-testid="column"] {
        min-width: calc(50% - 0.5rem) !important;
        flex: 1 1 calc(50% - 0.5rem) !important;
        box-sizing: border-box !important;
    }

    [data-testid="metric-container"] { padding: 0.4rem 0.5rem !important; margin-bottom: 0.3rem !important; }
    [data-testid="stMetricValue"] { font-size: 0.9rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.6rem !important; }
    [data-testid="stMetricDelta"] svg { display: none !important; }

    h1 { font-size: 1.1rem !important; }
    h2 { font-size: 0.9rem !important; }
    h3 { font-size: 0.8rem !important; }

    [data-testid="stPlotlyChart"] { overflow-x: auto !important; max-width: 100vw !important; }
    [data-testid="stNumberInput"] { width: 100% !important; }
    .stCaption, [data-testid="stCaptionContainer"] { font-size: 0.68rem !important; }
    .stButton button { font-size: 0.72rem !important; padding: 0.3rem 0.5rem !important; }
}

@media screen and (max-width: 420px) {
    .stTabs [data-baseweb="tab"] { font-size: 0.6rem !important; padding: 0.4rem 0.45rem !important; }
    [data-testid="stMetricValue"] { font-size: 0.82rem !important; }
}
</style>
""", unsafe_allow_html=True)

st.title("Enchanted Crown Fund")
st.subheader("Mean Reversion Strategy")

# ── Top-level tabs ─────────────────────────────────────────────────────────────
tab_daily, tab_viz, tab_bt, tab_ml, tab_cs, tab_rs, tab_rules = st.tabs([
    "Signal", "Bollinger", "Backtest", "Multi-LB",
    "Cross-Sec", "Resp Surface", "Rules"
])
# ARCHIVED tabs (KC + Combined — low confidence, re-enable when ready):
# tab_kc_viz, tab_combined, tab_kc_bt

# ══════════════════════════════════════════════════════════════════════════════
# DAILY SIGNAL TAB  — live z-score ranking, current position, buy candidate
# ══════════════════════════════════════════════════════════════════════════════
with tab_daily:

    DAILY_DATA_DIR     = Path(__file__).parent / "data"
    DAILY_REPORTS_DIR  = Path(__file__).parent / "reports"

    @st.cache_data(ttl=300)
    def load_daily_signal():
        """Load current CS signal and model params from latest summary files."""
        sig_files = sorted(DAILY_REPORTS_DIR.glob("cs_signal_*.csv"),   reverse=True)
        sum_files = sorted(DAILY_REPORTS_DIR.glob("cs_summary_*.csv"),  reverse=True)
        trd_files = sorted(DAILY_REPORTS_DIR.glob("cs_trades_*.csv"),   reverse=True)
        if not sig_files or not sum_files:
            return None, None, None
        try:
            sig = pd.read_csv(sig_files[0])
            smr = pd.read_csv(sum_files[0])
            trd = pd.read_csv(trd_files[0]) if trd_files else pd.DataFrame()
            return sig, smr, trd
        except Exception:
            return None, None, None

    @st.cache_data(ttl=300)
    def compute_zscores_live(n1: int, n2: int, n3: int):
        """Read all ticker CSVs and compute today's composite z-score ranking."""
        rows = []
        for p in sorted(DAILY_DATA_DIR.glob("*_daily_high_low.csv")):
            ticker = p.stem.replace("_daily_high_low", "")
            try:
                df    = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
                close = df["Close"].astype(float)
                if close.isna().all():
                    continue
                last_close = float(close.dropna().iloc[-1])
                last_date  = df["Date"].iloc[-1].strftime("%Y-%m-%d")
                zs, below = [], []
                valid = True
                for n in [n1, n2, n3]:
                    sma = close.rolling(n).mean()
                    std = close.rolling(n).std(ddof=0)
                    if pd.isna(sma.iloc[-1]) or pd.isna(std.iloc[-1]) or std.iloc[-1] == 0:
                        valid = False; break
                    z = (close.iloc[-1] - sma.iloc[-1]) / std.iloc[-1]
                    zs.append(float(z))
                    below.append(bool(z < 0))
                if not valid:
                    continue
                rows.append({
                    "Ticker":      ticker,
                    "Close":       round(last_close, 2),
                    "As Of":       last_date,
                    f"Z({n1})":    round(zs[0], 3),
                    f"Z({n2})":    round(zs[1], 3),
                    f"Z({n3})":    round(zs[2], 3),
                    "Composite Z": round(float(np.mean(zs)), 3),
                    "# Windows Below Mean": sum(below),
                })
            except Exception:
                continue

        df_z = pd.DataFrame(rows).sort_values("Composite Z").reset_index(drop=True)
        df_z.insert(0, "Rank", range(1, len(df_z) + 1))
        return df_z

    sig_df, smr_df, trd_df = load_daily_signal()

    if sig_df is None or smr_df is None:
        st.info("No cross-sectional results found. Run the backtester to generate a signal.")
    else:
        smr = smr_df.iloc[0]
        n1_cs = int(smr["N1"]); n2_cs = int(smr["N2"]); n3_cs = int(smr["N3"])
        k_cs  = float(smr["K"])
        sig   = sig_df.iloc[0]

        # ── Header ────────────────────────────────────────────────────────────
        from datetime import date as _date
        today_str = _date.today().strftime("%B %d, %Y")
        st.markdown(f"## Daily Signal — {today_str}")
        st.caption(
            f"Cross-sectional model · Windows N = {n1_cs}, {n2_cs}, {n3_cs} · "
            f"K = {k_cs} · Entry: lowest composite z-score across all windows"
        )

        # ── Compute live z-scores ─────────────────────────────────────────────
        df_z = compute_zscores_live(n1_cs, n2_cs, n3_cs)
        n_valid = len(df_z)

        # ── Current position block ────────────────────────────────────────────
        state  = str(sig.get("State", "FLAT")).upper()
        ticker = str(sig.get("Ticker", "—"))

        if state == "SELL":
            entry_price = sig.get("Entry $", 0.0)
            last_price  = sig.get("Last $",  0.0)
            reason      = sig.get("Reason",  "exit condition met")
            st.markdown("### Exit Signal — Sell Today")
            st.error(
                f"**SELL {ticker}** — {reason}. "
                f"Entry ${float(entry_price):.2f} → Last ${float(last_price):.2f}. "
                "The Alpaca trader will place a market sell order tonight."
            )
        elif state == "HOLDING":
            entry_date   = sig.get("Entry Date", "—")
            entry_price  = sig.get("Entry $",    0.0)
            last_price   = sig.get("Last $",     0.0)
            unreal_pct   = sig.get("Unrealized %", 0.0)
            cur_rank_row = df_z[df_z["Ticker"] == ticker]
            cur_rank     = int(cur_rank_row["Rank"].iloc[0]) if not cur_rank_row.empty else "?"
            cur_z        = float(cur_rank_row["Composite Z"].iloc[0]) if not cur_rank_row.empty else float("nan")

            st.markdown("### Current Position")
            p1, p2, p3, p4, p5 = st.columns(5)
            p1.metric("Ticker",       ticker)
            p2.metric("Entry Date",   entry_date if entry_date != "—" else "Via Alpaca")
            p3.metric("Entry Price",  f"${float(entry_price):.2f}")
            p4.metric("Last Price",   f"${float(last_price):.2f}",
                      delta=f"{float(unreal_pct):+.2f}%")
            p5.metric("Today's Rank", f"#{cur_rank} / {n_valid}",
                      help="Lower rank = more oversold = closer to entry signal")
            st.caption(
                f"Today's composite z-score for {ticker}: **{cur_z:.3f}**. "
                f"Ranked #{cur_rank} of {n_valid} tickers (1 = most oversold). "
                "The model holds until price crosses the upper band or stop loss triggers — "
                "a lower-ranked ticker today does **not** trigger a switch."
            )
        elif state == "BUY":
            st.markdown("### No Current Position — Buy Signal Active")
            st.info("The model is flat and a buy signal is active. The Alpaca trader will place a market order tonight.")
        else:
            st.markdown("### No Current Position")
            st.info("The model is flat. No ticker is currently below the entry threshold.")

        st.divider()

        # ── Today's top candidate ─────────────────────────────────────────────
        st.markdown("### Top Buy Candidate")

        top = df_z.iloc[0]
        top_ticker = top["Ticker"]
        top_z      = top["Composite Z"]
        z_col1     = f"Z({n1_cs})"
        z_col2     = f"Z({n2_cs})"
        z_col3     = f"Z({n3_cs})"
        entry_threshold = -k_cs

        if top_z <= entry_threshold:
            signal_label = "ACTIVE BUY SIGNAL"
        elif top_z <= entry_threshold * 0.7:
            signal_label = "APPROACHING ENTRY"
        else:
            signal_label = "WATCHING — no signal yet"

        badge_styles = {
            "ACTIVE BUY SIGNAL":            ("background:#fef2f2;color:#b91c1c;border:1px solid #fca5a5;",),
            "APPROACHING ENTRY":     ("background:#fffbeb;color:#b45309;border:1px solid #fcd34d;",),
            "WATCHING — no signal yet": ("background:#f8fafc;color:#475569;border:1px solid #cbd5e1;",),
        }
        _bs = badge_styles.get(signal_label, ("background:#f8fafc;color:#475569;border:1px solid #cbd5e1;",))[0]
        st.markdown(
            f"<div style='display:inline-block;{_bs}padding:4px 12px;border-radius:4px;"
            f"font-size:0.72rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;"
            f"margin-bottom:0.75rem;'>{signal_label}</div>",
            unsafe_allow_html=True,
        )

        t1, t2, t3, t4, t5, t6 = st.columns(6)
        t1.metric("Ticker",         top_ticker)
        t2.metric("Close",          f"${top['Close']:.2f}")
        t3.metric("Composite Z",    f"{top_z:.3f}",
                  help="Average z-score across all 3 lookback windows. More negative = more oversold.")
        t4.metric(f"Z({n1_cs})",    f"{top[z_col1]:.3f}")
        t5.metric(f"Z({n2_cs})",    f"{top[z_col2]:.3f}")
        t6.metric(f"Z({n3_cs})",    f"{top[z_col3]:.3f}")

        # Why explanation
        windows_below = top["# Windows Below Mean"]
        why_parts = []
        if top_z < entry_threshold:
            why_parts.append(f"composite z-score of **{top_z:.3f}** is below the entry threshold of **{entry_threshold:.2f}**")
        if windows_below == 3:
            why_parts.append("price is **below the mean on all 3 lookback windows** (strongest possible consensus)")
        elif windows_below == 2:
            why_parts.append("price is below the mean on 2 of 3 lookback windows")
        else:
            why_parts.append("it has the lowest composite z-score in the universe today")
        why_parts.append(f"ranked **#1 of {n_valid} valid tickers**")

        st.markdown("**Why:** " + ", and ".join(why_parts) + ".")

        st.divider()

        # ── Full ranking chart ─────────────────────────────────────────────────
        st.markdown("### Universe Ranking")
        st.caption(
            "Lower composite z-score = more oversold. "
            f"Entry threshold = {entry_threshold:.2f} (K = {k_cs}). "
            "Tickers left of the red line are at or beyond the entry threshold."
        )

        # Color bars: red gradient for oversold, blue for neutral/overbought
        colors = []
        for z in df_z["Composite Z"]:
            if z <= entry_threshold:
                colors.append("#d62728")       # entry threshold crossed — red
            elif z <= 0:
                colors.append("#ff9896")        # below mean — light red
            elif z <= 1.0:
                colors.append("#aec7e8")        # neutral — light blue
            else:
                colors.append("#1f77b4")        # overbought — blue

        # Annotate current holding
        bar_labels = []
        for _, row in df_z.iterrows():
            t = row["Ticker"]
            if state == "HOLDING" and t == ticker:
                bar_labels.append(f"{t}  [held]")
            else:
                bar_labels.append(t)

        fig_rank = go.Figure(go.Bar(
            y=bar_labels,
            x=df_z["Composite Z"],
            orientation="h",
            marker_color=colors,
            text=[f"{z:.2f}" for z in df_z["Composite Z"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Composite Z: %{x:.3f}<extra></extra>",
        ))

        # Entry threshold vertical line
        fig_rank.add_vline(
            x=entry_threshold,
            line_dash="dash", line_color="#d62728", line_width=1.5,
            annotation_text=f"Entry ({entry_threshold:.2f})",
            annotation_position="top right",
            annotation_font_color="#d62728",
        )
        # Zero line
        fig_rank.add_vline(x=0, line_dash="dot", line_color="#aaa", line_width=1)

        chart_height = max(400, n_valid * 22)
        fig_rank.update_layout(
            xaxis_title="Composite Z-Score (lower = more oversold)",
            yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
            margin=dict(t=30, b=50, l=80, r=60),
            height=chart_height,
            showlegend=False,
        )
        st.plotly_chart(fig_rank, use_container_width=True)

        st.divider()

        # ── Recent trade history ──────────────────────────────────────────────
        if trd_df is not None and not trd_df.empty:
            st.markdown("### Recent Trades")
            recent = trd_df.tail(10).iloc[::-1].reset_index(drop=True)
            recent.index += 1
            st.dataframe(recent, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# VISUALIZER TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_viz:

    # ── Load parameters from STRATEGY_RULES.md ───────────────────────────────
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

        N         = extract("N")
        K         = extract("K")
        StopPct   = extract("StopPct") / 100
        return {"N": N, "K": K, "StopPct": StopPct}

    params    = load_strategy_params()
    N         = params["N"]
    K         = params["K"]
    STOP_PCT  = params["StopPct"]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def compute_bollinger(close: pd.Series, n: int, k: int):
        sma   = close.rolling(n).mean()
        std   = close.rolling(n).std(ddof=0)
        upper = sma + k * std
        lower = sma - k * std
        return sma, upper, lower

    def compute_signals(close: pd.Series, upper: pd.Series, lower: pd.Series):
        buy  = (close < lower) & (close.shift(1) >= lower.shift(1))
        sell = (close > upper) & (close.shift(1) <= upper.shift(1))
        return buy, sell


    def simulate_portfolio(df: pd.DataFrame, upper_bb: pd.Series, lower_bb: pd.Series,
                           initial: float, stop_pct: float):
        balance  = initial
        shares   = 0.0
        in_trade = False
        entry_price = entry_date = None
        trades = []
        eq_dates, eq_vals = [], []

        for i in range(1, len(df)):
            close      = df["Close"].iloc[i]
            prev_close = df["Close"].iloc[i - 1]
            cur_upper  = upper_bb.iloc[i]
            cur_lower  = lower_bb.iloc[i]
            prev_upper = upper_bb.iloc[i - 1]
            prev_lower = lower_bb.iloc[i - 1]
            date       = df["Date"].iloc[i]

            if pd.isna(cur_upper) or pd.isna(cur_lower) or pd.isna(prev_lower):
                eq_dates.append(date); eq_vals.append(balance)
                continue

            if not in_trade:
                if close < cur_lower and prev_close >= prev_lower:
                    shares      = balance / close
                    entry_price = close
                    entry_date  = date
                    in_trade    = True
            else:
                stop_price = entry_price * (1 - stop_pct)
                tp = close > cur_upper and prev_close <= prev_upper
                sl = close <= stop_price
                if tp or sl:
                    balance = shares * close
                    trades.append({
                        "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                        "Entry $":     round(entry_price, 2),
                        "Exit Date":   date.strftime("%Y-%m-%d"),
                        "Exit $":      round(close, 2),
                        "Exit Reason": "Take Profit" if tp else "Stop Loss",
                        "Return %":    round((close / entry_price - 1) * 100, 1),
                        "Balance $":   round(balance, 2),
                    })
                    shares   = 0.0
                    in_trade = False

            eq_dates.append(date)
            eq_vals.append(shares * close if in_trade else balance)

        if in_trade:
            close   = df["Close"].iloc[-1]
            balance = shares * close
            trades.append({
                "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                "Entry $":     round(entry_price, 2),
                "Exit Date":   "—",
                "Exit $":      round(close, 2),
                "Exit Reason": "Open",
                "Return %":    round((close / entry_price - 1) * 100, 1),
                "Balance $":   round(balance, 2),
            })

        eq_series = pd.Series(eq_vals, index=eq_dates)
        return round(balance, 2), trades, eq_series


    # ── Ticker selector ───────────────────────────────────────────────────────
    DATA_DIR     = Path(__file__).parent / "data"
    viz_tickers  = sorted(p.stem.replace("_daily_high_low", "") for p in DATA_DIR.glob("*_daily_high_low.csv"))
    if not viz_tickers:
        st.error("No ticker data files found in data/. Run the bootstrap workflow first.")
        st.stop()
    viz_ticker = st.selectbox("Ticker:", viz_tickers, key="viz_ticker_sel")

    # ── Load selected ticker ──────────────────────────────────────────────────
    df_full  = pd.read_csv(DATA_DIR / f"{viz_ticker}_daily_high_low.csv", parse_dates=["Date"])
    df_full  = df_full.sort_values("Date").reset_index(drop=True)

    global_min = df_full["Date"].min().date()
    global_max = df_full["Date"].max().date()

    # ── Active strategy parameters (read-only display) ────────────────────────
    with st.expander("Active Strategy Parameters", expanded=False):
        st.caption("Parameters are defined in `STRATEGY_RULES.md` and cannot be changed here.")
        c1, c2 = st.columns(2)
        c1.metric("N (Lookback)", N)
        c2.metric("K (Std Dev ×)", K)

    # ── Date range + signal toggle ─────────────────────────────────────────────
    with st.expander("View Settings", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            start_date = st.date_input("From", value=global_min, min_value=global_min, max_value=global_max)
        with col_b:
            end_date = st.date_input("To", value=global_max, min_value=global_min, max_value=global_max)
        show_signals = st.toggle("Show buy/sell signals", value=True)

    # ── Filter to date range ───────────────────────────────────────────────────
    df = df_full[(df_full["Date"].dt.date >= start_date) & (df_full["Date"].dt.date <= end_date)].reset_index(drop=True)

    if df.empty:
        st.warning("No data in selected date range.")
        st.stop()

    # ── Compute indicators (full history for accuracy, slice after) ────────────
    sma, upper_bb, lower_bb  = compute_bollinger(df_full["Close"], N, K)
    buy_signals, sell_signals = compute_signals(df_full["Close"], upper_bb, lower_bb)

    mask         = (df_full["Date"].dt.date >= start_date) & (df_full["Date"].dt.date <= end_date)
    sma          = sma[mask].reset_index(drop=True)
    upper_bb     = upper_bb[mask].reset_index(drop=True)
    lower_bb     = lower_bb[mask].reset_index(drop=True)
    buy_signals  = buy_signals[mask].reset_index(drop=True)
    sell_signals = sell_signals[mask].reset_index(drop=True)

    # ── Main chart ─────────────────────────────────────────────────────────────
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

    # ── Pre-compute trade outcomes (used by navigator + portfolio simulation) ──
    sma_full, upper_full, lower_full = compute_bollinger(df_full["Close"], N, K)
    _, _sim_trades, _ = simulate_portfolio(df, upper_bb, lower_bb, 5000.0, STOP_PCT)
    _outcome_map   = {t["Entry Date"]: t for t in _sim_trades}

    # ── Signal Navigator ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### Signal Navigator")

    _all_signals = []
    for _d, _p in zip(df["Date"][buy_signals], df["Close"][buy_signals]):
        _all_signals.append({
            "type":    "Buy ▲",
            "date":    _d,
            "price":   _p,
            "outcome": _outcome_map.get(_d.strftime("%Y-%m-%d"), {}),
        })
    for _d, _p in zip(df["Date"][sell_signals], df["Close"][sell_signals]):
        _all_signals.append({
            "type":    "Sell ▼",
            "date":    _d,
            "price":   _p,
            "outcome": {},
        })
    _all_signals.sort(key=lambda x: x["date"])

    if not _all_signals:
        st.info("No signals in the selected date range.")
    else:
        if "nav_idx" not in st.session_state:
            st.session_state.nav_idx = 0
        st.session_state.nav_idx = min(st.session_state.nav_idx, len(_all_signals) - 1)

        _sig = _all_signals[st.session_state.nav_idx]

        # Signal info above buttons — works at any screen width
        st.markdown(
            f"<div style='text-align:center;padding:0.25rem 0 0.5rem 0;font-size:0.9rem;'>"
            f"Signal <strong>{st.session_state.nav_idx + 1}</strong> of <strong>{len(_all_signals)}</strong>"
            f" &nbsp;·&nbsp; <strong>{_sig['type']}</strong>"
            f" &nbsp;·&nbsp; {_sig['date'].strftime('%b %d, %Y')}"
            f" &nbsp;·&nbsp; ${_sig['price']:.2f}"
            f"</div>", unsafe_allow_html=True
        )
        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("← Prev", disabled=st.session_state.nav_idx == 0, use_container_width=True):
                st.session_state.nav_idx -= 1
                st.rerun()
        with _c2:
            if st.button("Next →", disabled=st.session_state.nav_idx == len(_all_signals) - 1, use_container_width=True):
                st.session_state.nav_idx += 1
                st.rerun()

        _WIN    = 30
        _fi     = df_full[df_full["Date"] == _sig["date"]].index
        if len(_fi):
            _fi        = _fi[0]
            _zs        = max(0, _fi - _WIN)
            _ze        = min(len(df_full), _fi + _WIN + 1)
            _zdf       = df_full.iloc[_zs:_ze].reset_index(drop=True)
            _z_sma     = sma_full.iloc[_zs:_ze].reset_index(drop=True)
            _z_upper   = upper_full.iloc[_zs:_ze].reset_index(drop=True)
            _z_lower   = lower_full.iloc[_zs:_ze].reset_index(drop=True)

            _fn = go.Figure()
            _fn.add_trace(go.Candlestick(
                x=_zdf["Date"], open=_zdf["Open"], high=_zdf["High"],
                low=_zdf["Low"], close=_zdf["Close"], name="Price",
                increasing=dict(line=dict(color="#636EFA"), fillcolor="#636EFA"),
                decreasing=dict(line=dict(color="#636EFA"), fillcolor="rgba(0,0,0,0)"),
                showlegend=False,
            ))
            _fn.add_trace(go.Scatter(x=_zdf["Date"], y=_z_sma, mode="lines",
                name=f"SMA({N})", line=dict(color="orange", width=1.5)))
            _fn.add_trace(go.Scatter(x=_zdf["Date"], y=_z_upper, mode="lines",
                name="BB Upper", line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot")))
            _fn.add_trace(go.Scatter(x=_zdf["Date"], y=_z_lower, mode="lines",
                name="BB Lower", line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(150,150,150,0.07)"))

            _is_buy    = "Buy" in _sig["type"]
            _fn.add_trace(go.Scatter(
                x=[_sig["date"]], y=[_sig["price"] * (0.97 if _is_buy else 1.03)],
                mode="markers", showlegend=False,
                marker=dict(
                    symbol="triangle-up" if _is_buy else "triangle-down",
                    size=14, color="lime" if _is_buy else "red",
                    line=dict(color="green" if _is_buy else "darkred", width=1.5),
                ),
            ))

            _fn.add_vline(x=_sig["date"], line_dash="dash",
                          line_color="rgba(100,100,100,0.35)", line_width=1)

            if _is_buy:
                _stop_px = _sig["price"] * (1 - STOP_PCT)
                _fn.add_hline(y=_stop_px, line_dash="dot",
                              line_color="rgba(220,50,50,0.5)", line_width=1.5,
                              annotation_text=f"Stop ${_stop_px:.2f}",
                              annotation_position="bottom right",
                              annotation_font_size=10)
                _oc = _sig["outcome"]
                if _oc and _oc.get("Exit Date") and _oc["Exit Date"] != "—":
                    _exit_dt  = pd.to_datetime(_oc["Exit Date"])
                    _exit_px  = _oc["Exit $"]
                    _is_tp    = _oc["Exit Reason"] == "Take Profit"
                    _ex_color = "rgba(0,160,0,0.45)" if _is_tp else "rgba(200,0,0,0.45)"
                    _fn.add_vline(x=_exit_dt, line_dash="dot",
                                  line_color=_ex_color, line_width=1.5)
                    _fn.add_annotation(
                        x=_exit_dt, y=_exit_px,
                        text=f"{'TP' if _is_tp else 'SL'} ${_exit_px:.2f}",
                        showarrow=True, arrowhead=2, arrowsize=1,
                        font=dict(size=10, color="green" if _is_tp else "red"),
                        arrowcolor="green" if _is_tp else "red",
                        bgcolor="rgba(255,255,255,0.8)",
                    )

            _fn.update_layout(
                xaxis=dict(type="date", tickformat="%b %d", rangeslider=dict(visible=False)),
                yaxis=dict(tickprefix="$", automargin=True),
                hovermode="x unified",
                height=360,
                margin=dict(l=10, r=10, t=30, b=10),
                dragmode="pan",
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1, font=dict(size=10)),
            )
            st.plotly_chart(_fn, use_container_width=True)

            if _is_buy:
                _oc  = _sig["outcome"]
                _tp_at = upper_full.iloc[_fi]
                _i1, _i2, _i3, _i4, _i5 = st.columns(5)
                _i1.metric("Entry Price",           f"${_sig['price']:.2f}")
                _i2.metric("Stop Loss",             f"${_sig['price'] * (1 - STOP_PCT):.2f}")
                _i3.metric("Take Profit (BB Upper)", f"${_tp_at:.2f}" if not pd.isna(_tp_at) else "—")
                _i4.metric("Exit Price",        f"${_oc['Exit $']:.2f}"      if _oc else "—")
                _i5.metric("Return",            f"{_oc['Return %']:+.1f}%"   if _oc else "—",
                           delta=f"{_oc['Exit Reason']}" if _oc else None,
                           delta_color="normal" if _oc and _oc.get("Exit Reason","") == "Take Profit" else "inverse")
            else:
                _i1, _i2 = st.columns(2)
                _i1.metric("Signal Price", f"${_sig['price']:.2f}")
                _i2.metric("Date",         _sig["date"].strftime("%B %d, %Y"))

    st.divider()

    # ── Summary stats ──────────────────────────────────────────────────────────
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

    # ── Portfolio simulation ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### Portfolio Simulation")
    st.caption(f"Buys on BB lower crossover · Exits at SMA (take profit) or −{int(STOP_PCT*100)}% (stop loss) · Full balance reinvested each trade")

    initial_investment = st.number_input(
        "Initial investment ($)",
        min_value=1.0, value=5000.0, step=100.0, format="%.2f"
    )

    final_balance, trades, eq_series = simulate_portfolio(df, upper_bb, lower_bb, initial_investment, STOP_PCT)

    if not trades:
        st.info("No completed trades in the selected date range.")
    else:
        total_return_pct = (final_balance / initial_investment - 1) * 100
        closed = [t for t in trades if t["Exit Reason"] != "Open"]
        wins   = [t for t in closed if t["Return %"] > 0]

        # Max drawdown from daily equity curve
        if not eq_series.empty:
            _eq_peak = eq_series.cummax()
            _max_dd  = float((_eq_peak - eq_series).max())
            _max_dd_pct = _max_dd / _eq_peak.max() * 100 if _eq_peak.max() > 0 else 0.0
        else:
            _max_dd = _max_dd_pct = 0.0

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Final Balance",  f"${final_balance:,.2f}")
        m2.metric("Total Return",   f"{total_return_pct:+.1f}%")
        m3.metric("Trades",         len(trades))
        m4.metric("Win Rate",       f"{len(wins)/len(closed)*100:.0f}%" if closed else "—")
        m5.metric("Max Drawdown",   f"${_max_dd:,.0f}  ({_max_dd_pct:.1f}%)")

        # Equity curve
        if not eq_series.empty:
            _fig_eq = go.Figure()
            _fig_eq.add_trace(go.Scatter(
                x=eq_series.index, y=eq_series.values,
                mode="lines", name="Portfolio Value",
                line=dict(color="#636EFA", width=2),
                fill="tozeroy", fillcolor="rgba(99,110,250,0.08)",
            ))
            _bnh_eq = initial_investment / df["Close"].iloc[0] * df.set_index("Date")["Close"]
            _fig_eq.add_trace(go.Scatter(
                x=_bnh_eq.index, y=_bnh_eq.values,
                mode="lines", name="Buy & Hold",
                line=dict(color="rgba(150,150,150,0.6)", width=1.5, dash="dash"),
            ))
            _fig_eq.update_layout(
                xaxis=dict(type="date", tickformat="%b %Y"),
                yaxis=dict(tickprefix="$"),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                height=280, margin=dict(l=10, r=10, t=30, b=10),
            )
            st.plotly_chart(_fig_eq, use_container_width=True)

        trade_df = pd.DataFrame(trades)
        trade_df.insert(0, "#", range(1, len(trade_df) + 1))
        st.dataframe(trade_df, use_container_width=True, hide_index=True)

    # ── Footer ─────────────────────────────────────────────────────────────────
    most_recent = df_full["Date"].max().strftime("%B %d, %Y")
    st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")


# ══════════════════════════════════════════════════════════════════════════════
# KELTNER CHANNEL VISUALIZER TAB  [ARCHIVED]
# ══════════════════════════════════════════════════════════════════════════════
if False:  # ARCHIVED — re-enable by restoring tab_kc_viz to st.tabs() call

    # ── Load KC parameters from STRATEGY_RULES.md ────────────────────────────
    def load_kc_params_viz() -> dict:
        rules_path = Path(__file__).parent / "STRATEGY_RULES.md"
        text = rules_path.read_text()

        def extract_kc(symbol: str):
            pattern = rf"\|\s*`KC_{symbol}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
            match = re.search(pattern, text)
            if not match:
                st.error(f"❌ Cannot find parameter `KC_{symbol}` in STRATEGY_RULES.md. Please check the file.")
                st.stop()
            val = match.group(1)
            return float(val) if "." in val else int(val)

        N         = extract_kc("N")
        K         = extract_kc("K")
        StopPct   = extract_kc("StopPct") / 100
        LR_PERIOD = extract_kc("LR_PERIOD")
        return {"N": N, "K": K, "StopPct": StopPct, "LR_PERIOD": LR_PERIOD}

    kc_params    = load_kc_params_viz()
    KC_N         = kc_params["N"]
    KC_K         = kc_params["K"]
    KC_STOP_PCT  = kc_params["StopPct"]
    KC_LR_PERIOD = kc_params["LR_PERIOD"]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def compute_keltner(close: pd.Series, high: pd.Series, low: pd.Series, n: int, k: float):
        ema = close.ewm(span=n, adjust=False).mean()
        tr  = pd.concat([high - low,
                         (high - close.shift(1)).abs(),
                         (low  - close.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.rolling(n).mean()
        return ema, ema + k * atr, ema - k * atr

    def compute_lr_slope_viz(close: pd.Series, period: int) -> pd.Series:
        import numpy as np
        x = np.arange(period, dtype=float)
        x -= x.mean()
        return close.rolling(period).apply(lambda y: np.dot(x, y) / np.dot(x, x), raw=True)

    def compute_kc_signals(close: pd.Series, upper: pd.Series, lower: pd.Series, lr_period: int):
        kc_cross = (close < lower) & (close.shift(1) >= lower.shift(1))
        if lr_period > 0:
            slope = compute_lr_slope_viz(close, lr_period)
            buy   = kc_cross & (slope > 0)
        else:
            buy   = kc_cross
        sell = (close > upper) & (close.shift(1) <= upper.shift(1))
        return buy, sell

    def simulate_kc_portfolio(df: pd.DataFrame, ema: pd.Series, upper_kc: pd.Series, lower_kc: pd.Series,
                              initial: float, stop_pct: float):
        balance  = initial
        shares   = 0.0
        in_trade = False
        entry_price = entry_date = None
        trades = []
        eq_dates, eq_vals = [], []

        for i in range(1, len(df)):
            close      = df["Close"].iloc[i]
            prev_close = df["Close"].iloc[i - 1]
            cur_upper  = upper_kc.iloc[i]
            cur_lower  = lower_kc.iloc[i]
            prev_upper = upper_kc.iloc[i - 1]
            prev_lower = lower_kc.iloc[i - 1]
            date       = df["Date"].iloc[i]

            if pd.isna(cur_upper) or pd.isna(cur_lower) or pd.isna(prev_lower):
                eq_dates.append(date); eq_vals.append(balance)
                continue

            if not in_trade:
                if close < cur_lower and prev_close >= prev_lower:
                    shares      = balance / close
                    entry_price = close
                    entry_date  = date
                    in_trade    = True
            else:
                stop_price = entry_price * (1 - stop_pct)
                tp = close > cur_upper and prev_close <= prev_upper
                sl = close <= stop_price
                if tp or sl:
                    balance = shares * close
                    trades.append({
                        "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                        "Entry $":     round(entry_price, 2),
                        "Exit Date":   date.strftime("%Y-%m-%d"),
                        "Exit $":      round(close, 2),
                        "Exit Reason": "Take Profit ✅" if tp else "Stop Loss 🛑",
                        "Return %":    round((close / entry_price - 1) * 100, 1),
                        "Balance $":   round(balance, 2),
                    })
                    shares   = 0.0
                    in_trade = False

            eq_dates.append(date)
            eq_vals.append(shares * close if in_trade else balance)

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

        eq_series = pd.Series(eq_vals, index=eq_dates)
        return round(balance, 2), trades, eq_series

    # ── Load GSIT ─────────────────────────────────────────────────────────────
    KC_DATA_DIR = Path(__file__).parent / "data"
    kc_df_full  = pd.read_csv(KC_DATA_DIR / "GSIT_daily_high_low.csv", parse_dates=["Date"])
    kc_df_full  = kc_df_full.sort_values("Date").reset_index(drop=True)

    kc_global_min = kc_df_full["Date"].min().date()
    kc_global_max = kc_df_full["Date"].max().date()

    # ── Active strategy parameters (read-only display) ────────────────────────
    with st.expander("📋 Active KC Strategy Parameters", expanded=False):
        st.caption("Parameters are defined in `STRATEGY_RULES.md` (KC_ prefixed) and cannot be changed here.")
        kc_c1, kc_c2, kc_c3 = st.columns(3)
        kc_c1.metric("KC_N (Lookback)", KC_N)
        kc_c2.metric("KC_K (ATR ×)", KC_K)
        kc_c3.metric("KC_LR_PERIOD", KC_LR_PERIOD)

    # ── Date range + signal toggle ─────────────────────────────────────────────
    with st.expander("⚙️ View Settings", expanded=False):
        kc_col_a, kc_col_b = st.columns(2)
        with kc_col_a:
            kc_start_date = st.date_input("From", value=kc_global_min, min_value=kc_global_min, max_value=kc_global_max, key="kc_start")
        with kc_col_b:
            kc_end_date = st.date_input("To", value=kc_global_max, min_value=kc_global_min, max_value=kc_global_max, key="kc_end")
        kc_show_signals = st.toggle("Show buy/sell signals", value=True, key="kc_signals")

    # ── Filter to date range ───────────────────────────────────────────────────
    kc_df = kc_df_full[(kc_df_full["Date"].dt.date >= kc_start_date) & (kc_df_full["Date"].dt.date <= kc_end_date)].reset_index(drop=True)

    if kc_df.empty:
        st.warning("No data in selected date range.")
        st.stop()

    # ── Compute indicators (full history for accuracy, slice after) ────────────
    kc_ema_full, kc_upper_full, kc_lower_full = compute_keltner(
        kc_df_full["Close"], kc_df_full["High"], kc_df_full["Low"], KC_N, KC_K
    )
    kc_buy_signals, kc_sell_signals = compute_kc_signals(
        kc_df_full["Close"], kc_upper_full, kc_lower_full, KC_LR_PERIOD
    )

    kc_mask         = (kc_df_full["Date"].dt.date >= kc_start_date) & (kc_df_full["Date"].dt.date <= kc_end_date)
    kc_ema          = kc_ema_full[kc_mask].reset_index(drop=True)
    kc_upper        = kc_upper_full[kc_mask].reset_index(drop=True)
    kc_lower        = kc_lower_full[kc_mask].reset_index(drop=True)
    kc_buy_sig      = kc_buy_signals[kc_mask].reset_index(drop=True)
    kc_sell_sig     = kc_sell_signals[kc_mask].reset_index(drop=True)

    # ── Main chart ─────────────────────────────────────────────────────────────
    kc_fig = go.Figure()

    kc_fig.add_trace(go.Candlestick(
        x=kc_df["Date"],
        open=kc_df["Open"], high=kc_df["High"], low=kc_df["Low"], close=kc_df["Close"],
        name="Price",
        increasing=dict(line=dict(color="#636EFA"), fillcolor="#636EFA"),
        decreasing=dict(line=dict(color="#636EFA"), fillcolor="rgba(0,0,0,0)"),
        showlegend=False,
    ))

    kc_fig.add_trace(go.Scatter(
        x=kc_df["Date"], y=kc_ema,
        mode="lines", name=f"EMA({KC_N})",
        line=dict(color="orange", width=1.5),
    ))

    kc_fig.add_trace(go.Scatter(
        x=kc_df["Date"], y=kc_upper,
        mode="lines", name=f"KC Upper (×{KC_K} ATR)",
        line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
    ))

    kc_fig.add_trace(go.Scatter(
        x=kc_df["Date"], y=kc_lower,
        mode="lines", name=f"KC Lower (×{KC_K} ATR)",
        line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(150,150,150,0.07)",
    ))

    if kc_show_signals:
        kc_fig.add_trace(go.Scatter(
            x=kc_df["Date"][kc_buy_sig], y=kc_df["Low"][kc_buy_sig] * 0.98,
            mode="markers", name="Buy",
            marker=dict(symbol="triangle-up", size=10, color="lime", line=dict(color="green", width=1)),
        ))

        kc_fig.add_trace(go.Scatter(
            x=kc_df["Date"][kc_sell_sig], y=kc_df["High"][kc_sell_sig] * 1.02,
            mode="markers", name="Sell",
            marker=dict(symbol="triangle-down", size=10, color="red", line=dict(color="darkred", width=1)),
        ))

    kc_fig.update_layout(
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

    st.plotly_chart(kc_fig, use_container_width=True)

    # ── Pre-compute trade outcomes (used by navigator + portfolio simulation) ──
    _, _kc_sim_trades, _ = simulate_kc_portfolio(kc_df, kc_ema, kc_upper, kc_lower, 5000.0, KC_STOP_PCT)
    _kc_outcome_map   = {t["Entry Date"]: t for t in _kc_sim_trades}

    # ── Signal Navigator ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔍 Signal Navigator")

    _kc_all_signals = []
    for _d, _p in zip(kc_df["Date"][kc_buy_sig], kc_df["Close"][kc_buy_sig]):
        _kc_all_signals.append({
            "type":    "Buy ▲",
            "date":    _d,
            "price":   _p,
            "outcome": _kc_outcome_map.get(_d.strftime("%Y-%m-%d"), {}),
        })
    for _d, _p in zip(kc_df["Date"][kc_sell_sig], kc_df["Close"][kc_sell_sig]):
        _kc_all_signals.append({
            "type":    "Sell ▼",
            "date":    _d,
            "price":   _p,
            "outcome": {},
        })
    _kc_all_signals.sort(key=lambda x: x["date"])

    if not _kc_all_signals:
        st.info("No signals in the selected date range.")
    else:
        if "kc_nav_idx" not in st.session_state:
            st.session_state.kc_nav_idx = 0
        st.session_state.kc_nav_idx = min(st.session_state.kc_nav_idx, len(_kc_all_signals) - 1)

        _kc_sig = _kc_all_signals[st.session_state.kc_nav_idx]

        _kc1, _kc2, _kc3 = st.columns([1, 5, 1])
        with _kc1:
            if st.button("← Prev", disabled=st.session_state.kc_nav_idx == 0, use_container_width=True, key="kc_prev"):
                st.session_state.kc_nav_idx -= 1
                st.rerun()
        with _kc3:
            if st.button("Next →", disabled=st.session_state.kc_nav_idx == len(_kc_all_signals) - 1, use_container_width=True, key="kc_next"):
                st.session_state.kc_nav_idx += 1
                st.rerun()
        with _kc2:
            st.markdown(
                f"<div style='text-align:center;padding-top:0.35rem'>"
                f"Signal <strong>{st.session_state.kc_nav_idx + 1}</strong> of <strong>{len(_kc_all_signals)}</strong>"
                f" &nbsp;·&nbsp; <strong>{_kc_sig['type']}</strong>"
                f" &nbsp;·&nbsp; {_kc_sig['date'].strftime('%b %d, %Y')}"
                f" &nbsp;·&nbsp; ${_kc_sig['price']:.2f}"
                f"</div>", unsafe_allow_html=True
            )

        _KC_WIN = 30
        _kc_fi  = kc_df_full[kc_df_full["Date"] == _kc_sig["date"]].index
        if len(_kc_fi):
            _kc_fi    = _kc_fi[0]
            _kc_zs    = max(0, _kc_fi - _KC_WIN)
            _kc_ze    = min(len(kc_df_full), _kc_fi + _KC_WIN + 1)
            _kc_zdf   = kc_df_full.iloc[_kc_zs:_kc_ze].reset_index(drop=True)
            _kc_z_ema    = kc_ema_full.iloc[_kc_zs:_kc_ze].reset_index(drop=True)
            _kc_z_upper  = kc_upper_full.iloc[_kc_zs:_kc_ze].reset_index(drop=True)
            _kc_z_lower  = kc_lower_full.iloc[_kc_zs:_kc_ze].reset_index(drop=True)

            _kc_fn = go.Figure()
            _kc_fn.add_trace(go.Candlestick(
                x=_kc_zdf["Date"], open=_kc_zdf["Open"], high=_kc_zdf["High"],
                low=_kc_zdf["Low"], close=_kc_zdf["Close"], name="Price",
                increasing=dict(line=dict(color="#636EFA"), fillcolor="#636EFA"),
                decreasing=dict(line=dict(color="#636EFA"), fillcolor="rgba(0,0,0,0)"),
                showlegend=False,
            ))
            _kc_fn.add_trace(go.Scatter(x=_kc_zdf["Date"], y=_kc_z_ema, mode="lines",
                name=f"EMA({KC_N})", line=dict(color="orange", width=1.5)))
            _kc_fn.add_trace(go.Scatter(x=_kc_zdf["Date"], y=_kc_z_upper, mode="lines",
                name="KC Upper", line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot")))
            _kc_fn.add_trace(go.Scatter(x=_kc_zdf["Date"], y=_kc_z_lower, mode="lines",
                name="KC Lower", line=dict(color="rgba(150,150,150,0.6)", width=1, dash="dot"),
                fill="tonexty", fillcolor="rgba(150,150,150,0.07)"))

            _kc_is_buy = "Buy" in _kc_sig["type"]
            _kc_fn.add_trace(go.Scatter(
                x=[_kc_sig["date"]], y=[_kc_sig["price"] * (0.97 if _kc_is_buy else 1.03)],
                mode="markers", showlegend=False,
                marker=dict(
                    symbol="triangle-up" if _kc_is_buy else "triangle-down",
                    size=14, color="lime" if _kc_is_buy else "red",
                    line=dict(color="green" if _kc_is_buy else "darkred", width=1.5),
                ),
            ))

            _kc_fn.add_vline(x=_kc_sig["date"], line_dash="dash",
                             line_color="rgba(100,100,100,0.35)", line_width=1)

            if _kc_is_buy:
                _kc_stop_px = _kc_sig["price"] * (1 - KC_STOP_PCT)
                _kc_fn.add_hline(y=_kc_stop_px, line_dash="dot",
                                 line_color="rgba(220,50,50,0.5)", line_width=1.5,
                                 annotation_text=f"Stop ${_kc_stop_px:.2f}",
                                 annotation_position="bottom right",
                                 annotation_font_size=10)
                _kc_oc = _kc_sig["outcome"]
                if _kc_oc and _kc_oc.get("Exit Date") and _kc_oc["Exit Date"] != "—":
                    _kc_exit_dt  = pd.to_datetime(_kc_oc["Exit Date"])
                    _kc_exit_px  = _kc_oc["Exit $"]
                    _kc_is_tp    = _kc_oc["Exit Reason"] == "Take Profit ✅"
                    _kc_ex_color = "rgba(0,160,0,0.45)" if _kc_is_tp else "rgba(200,0,0,0.45)"
                    _kc_fn.add_vline(x=_kc_exit_dt, line_dash="dot",
                                     line_color=_kc_ex_color, line_width=1.5)
                    _kc_fn.add_annotation(
                        x=_kc_exit_dt, y=_kc_exit_px,
                        text=f"{'TP' if _kc_is_tp else 'SL'} ${_kc_exit_px:.2f}",
                        showarrow=True, arrowhead=2, arrowsize=1,
                        font=dict(size=10, color="green" if _kc_is_tp else "red"),
                        arrowcolor="green" if _kc_is_tp else "red",
                        bgcolor="rgba(255,255,255,0.8)",
                    )

            _kc_fn.update_layout(
                xaxis=dict(type="date", tickformat="%b %d", rangeslider=dict(visible=False)),
                yaxis=dict(tickprefix="$", automargin=True),
                hovermode="x unified",
                height=360,
                margin=dict(l=10, r=10, t=30, b=10),
                dragmode="pan",
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="right", x=1, font=dict(size=10)),
            )
            st.plotly_chart(_kc_fn, use_container_width=True)

            if _kc_is_buy:
                _kc_oc   = _kc_sig["outcome"]
                _kc_upper_at = kc_upper_full.iloc[_kc_fi]
                _kc_i1, _kc_i2, _kc_i3, _kc_i4, _kc_i5 = st.columns(5)
                _kc_i1.metric("Entry Price",            f"${_kc_sig['price']:.2f}")
                _kc_i2.metric("Stop Loss",              f"${_kc_sig['price'] * (1 - KC_STOP_PCT):.2f}")
                _kc_i3.metric("Take Profit (KC Upper)", f"${_kc_upper_at:.2f}" if not pd.isna(_kc_upper_at) else "—")
                _kc_i4.metric("Exit Price",             f"${_kc_oc['Exit $']:.2f}"     if _kc_oc else "—")
                _kc_i5.metric("Return",                 f"{_kc_oc['Return %']:+.1f}%"  if _kc_oc else "—",
                              delta=f"{_kc_oc['Exit Reason']}" if _kc_oc else None,
                              delta_color="normal" if _kc_oc and "✅" in _kc_oc.get("Exit Reason","") else "inverse")
            else:
                _kc_i1, _kc_i2 = st.columns(2)
                _kc_i1.metric("Signal Price", f"${_kc_sig['price']:.2f}")
                _kc_i2.metric("Date",         _kc_sig["date"].strftime("%B %d, %Y"))

    st.divider()

    # ── Summary stats ──────────────────────────────────────────────────────────
    kc_col1, kc_col2 = st.columns(2)
    kc_col1.metric("All-Time High",   f"${kc_df['High'].max():.2f}")
    kc_col2.metric("All-Time Low",    f"${kc_df['Low'].min():.2f}")
    kc_col1.metric("Avg Daily Range", f"${(kc_df['High'] - kc_df['Low']).mean():.2f}")
    kc_latest = kc_df.iloc[-1]
    kc_delta  = kc_latest["Close"] - kc_latest["Open"]
    kc_col2.metric("Latest Close",    f"${kc_latest['Close']:.2f}", f"{kc_delta:+.2f}")

    if kc_show_signals:
        st.caption(f"Signals in range: {kc_buy_sig.sum()} buy ▲  ·  {kc_sell_sig.sum()} sell ▼")

    st.caption(f"{len(kc_df):,} trading days · {kc_df['Date'].iloc[0].date()} → {kc_df['Date'].iloc[-1].date()}")

    # ── Portfolio simulation ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### 💰 Portfolio Simulation")
    st.caption(f"Buys on KC lower crossover · Exits at KC upper (take profit) or −{int(KC_STOP_PCT*100)}% (stop loss) · Full balance reinvested each trade")

    kc_initial_investment = st.number_input(
        "Initial investment ($)",
        min_value=1.0, value=5000.0, step=100.0, format="%.2f",
        key="kc_initial"
    )

    kc_final_balance, kc_trades, kc_eq_series = simulate_kc_portfolio(kc_df, kc_ema, kc_upper, kc_lower, kc_initial_investment, KC_STOP_PCT)

    if not kc_trades:
        st.info("No completed trades in the selected date range.")
    else:
        kc_total_return_pct = (kc_final_balance / kc_initial_investment - 1) * 100
        kc_closed = [t for t in kc_trades if t["Exit Reason"] != "Still Open 🟡"]
        kc_wins   = [t for t in kc_closed if t["Return %"] > 0]

        if not kc_eq_series.empty:
            _kc_eq_peak  = kc_eq_series.cummax()
            _kc_max_dd   = float((_kc_eq_peak - kc_eq_series).max())
            _kc_max_dd_pct = _kc_max_dd / _kc_eq_peak.max() * 100 if _kc_eq_peak.max() > 0 else 0.0
        else:
            _kc_max_dd = _kc_max_dd_pct = 0.0

        kc_m1, kc_m2, kc_m3, kc_m4, kc_m5 = st.columns(5)
        kc_m1.metric("Final Balance",  f"${kc_final_balance:,.2f}")
        kc_m2.metric("Total Return",   f"{kc_total_return_pct:+.1f}%")
        kc_m3.metric("Trades",         len(kc_trades))
        kc_m4.metric("Win Rate",       f"{len(kc_wins)/len(kc_closed)*100:.0f}%" if kc_closed else "—")
        kc_m5.metric("Max Drawdown",   f"${_kc_max_dd:,.0f}  ({_kc_max_dd_pct:.1f}%)")

        if not kc_eq_series.empty:
            _kc_fig_eq = go.Figure()
            _kc_fig_eq.add_trace(go.Scatter(
                x=kc_eq_series.index, y=kc_eq_series.values,
                mode="lines", name="Portfolio Value",
                line=dict(color="#FF7F0E", width=2),
                fill="tozeroy", fillcolor="rgba(255,127,14,0.08)",
            ))
            _kc_bnh = kc_initial_investment / kc_df["Close"].iloc[0] * kc_df.set_index("Date")["Close"]
            _kc_fig_eq.add_trace(go.Scatter(
                x=_kc_bnh.index, y=_kc_bnh.values,
                mode="lines", name="Buy & Hold",
                line=dict(color="rgba(150,150,150,0.6)", width=1.5, dash="dash"),
            ))
            _kc_fig_eq.update_layout(
                xaxis=dict(type="date", tickformat="%b %Y"),
                yaxis=dict(tickprefix="$"),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                height=280, margin=dict(l=10, r=10, t=30, b=10),
            )
            st.plotly_chart(_kc_fig_eq, use_container_width=True)

        kc_trade_df = pd.DataFrame(kc_trades)
        kc_trade_df.insert(0, "#", range(1, len(kc_trade_df) + 1))
        st.dataframe(kc_trade_df, use_container_width=True, hide_index=True)

    # ── Footer ─────────────────────────────────────────────────────────────────
    kc_most_recent = kc_df_full["Date"].max().strftime("%B %d, %Y")
    st.caption(f"Data source: Yahoo Finance · Most recent data: {kc_most_recent} · Updates daily at 6pm ET on weekdays")


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED STRATEGY TAB  [ARCHIVED]
# ══════════════════════════════════════════════════════════════════════════════
if False:  # ARCHIVED — re-enable by restoring tab_combined to st.tabs() call

    # ── Load params from STRATEGY_RULES.md ───────────────────────────────────
    def _load_combined_params() -> dict:
        rules_path = Path(__file__).parent / "STRATEGY_RULES.md"
        text = rules_path.read_text()
        def _e(sym: str):
            pat = rf"\|\s*`{sym}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
            m = re.search(pat, text)
            if not m:
                st.error(f"❌ Cannot find `{sym}` in STRATEGY_RULES.md")
                st.stop()
            v = m.group(1)
            return float(v) if "." in v else int(v)
        return {
            "bb_n":   _e("N"),
            "bb_k":   _e("K"),
            "bb_stp": _e("StopPct") / 100,
            "kc_n":   _e("KC_N"),
            "kc_k":   _e("KC_K"),
            "kc_stp": _e("KC_StopPct") / 100,
            "kc_lr":  _e("KC_LR_PERIOD"),
        }

    _cp = _load_combined_params()

    # ── Legend callout ────────────────────────────────────────────────────────
    st.info(
        "**How regime switching works:** When Bollinger Bands sit *inside* Keltner Channels "
        "(the squeeze), volatility is compressed and the market is ranging — BB signals are used. "
        "When BB expands *outside* KC, the market is trending or breaking out — KC signals (with "
        "linear-regression trend filter) are used instead.\n\n"
        "🔵 **Blue background** = Ranging → BB active &nbsp;&nbsp; "
        "🟠 **Orange background** = Trending → KC active"
    )

    # ── Active params (read-only) ─────────────────────────────────────────────
    with st.expander("📋 Active Combined Strategy Parameters", expanded=False):
        st.caption("Both parameter sets are read from `STRATEGY_RULES.md`.")
        _pc1, _pc2, _pc3, _pc4, _pc5 = st.columns(5)
        _pc1.metric("BB N", _cp["bb_n"])
        _pc2.metric("BB K", _cp["bb_k"])
        _pc3.metric("KC N", _cp["kc_n"])
        _pc4.metric("KC K", _cp["kc_k"])
        _pc5.metric("KC LR Period", _cp["kc_lr"])

    # ── Date range + display settings ────────────────────────────────────────
    _cb_df_full = pd.read_csv(
        Path(__file__).parent / "data" / "GSIT_daily_high_low.csv", parse_dates=["Date"]
    ).sort_values("Date").reset_index(drop=True)

    with st.expander("⚙️ View Settings", expanded=False):
        _cba, _cbb = st.columns(2)
        with _cba:
            _cb_start = st.date_input(
                "From",
                value=_cb_df_full["Date"].min().date(),
                min_value=_cb_df_full["Date"].min().date(),
                max_value=_cb_df_full["Date"].max().date(),
                key="cb_start",
            )
        with _cbb:
            _cb_end = st.date_input(
                "To",
                value=_cb_df_full["Date"].max().date(),
                min_value=_cb_df_full["Date"].min().date(),
                max_value=_cb_df_full["Date"].max().date(),
                key="cb_end",
            )
        _cb_show_sig = st.toggle("Show buy/sell signals", value=True, key="cb_signals")

    # ── Compute all indicators on FULL history (for warm-up accuracy) ─────────
    _cl  = _cb_df_full["Close"]
    _hi  = _cb_df_full["High"]
    _lo  = _cb_df_full["Low"]

    # BB
    _bb_sma   = _cl.rolling(_cp["bb_n"]).mean()
    _bb_std   = _cl.rolling(_cp["bb_n"]).std(ddof=0)
    _bb_upper = _bb_sma + _cp["bb_k"] * _bb_std
    _bb_lower = _bb_sma - _cp["bb_k"] * _bb_std

    # KC
    _kc_ema = _cl.ewm(span=_cp["kc_n"], adjust=False).mean()
    _kc_tr  = pd.concat([
        _hi - _lo,
        (_hi - _cl.shift(1)).abs(),
        (_lo - _cl.shift(1)).abs(),
    ], axis=1).max(axis=1)
    _kc_atr   = _kc_tr.rolling(_cp["kc_n"]).mean()
    _kc_upper = _kc_ema + _cp["kc_k"] * _kc_atr
    _kc_lower = _kc_ema - _cp["kc_k"] * _kc_atr

    # Regime: squeeze ON = BB inside KC = ranging
    _squeeze = (_bb_upper < _kc_upper) & (_bb_lower > _kc_lower)

    # LR slope filter for KC
    if _cp["kc_lr"] > 0:
        _x_lr = np.arange(_cp["kc_lr"], dtype=float)
        _x_lr -= _x_lr.mean()
        _lr_slope = _cl.rolling(_cp["kc_lr"]).apply(
            lambda y: float(np.dot(_x_lr, y) / np.dot(_x_lr, _x_lr)), raw=True
        )
        _lr_ok = _lr_slope > 0
    else:
        _lr_ok = pd.Series(True, index=_cl.index)

    # Raw crossover signals
    _bb_cross_dn = (_cl < _bb_lower) & (_cl.shift(1) >= _bb_lower.shift(1))
    _kc_cross_dn = (_cl < _kc_lower) & (_cl.shift(1) >= _kc_lower.shift(1))

    # Combined buy signals gated by regime
    _buy_bb_full = _bb_cross_dn & _squeeze          # ranging → BB
    _buy_kc_full = _kc_cross_dn & (~_squeeze) & _lr_ok  # trending → KC

    # ── Generic simulation helper ──────────────────────────────────────────────
    def _run_sim(df_src, buy_sig, upper_exit, stop_pct, capital, label):
        """Entry on buy_sig, take profit at upper_exit crossing, stop loss at -stop_pct."""
        balance = capital
        in_trade = False
        entry_price = entry_date = shares = None
        trades = []
        eq_dates, eq_vals = [], []

        for i in range(1, len(df_src)):
            dt    = df_src["Date"].iloc[i]
            close = df_src["Close"].iloc[i]
            u_cur = upper_exit.iloc[i]
            u_prv = upper_exit.iloc[i - 1]

            if pd.isna(u_cur) or pd.isna(u_prv):
                eq_dates.append(dt); eq_vals.append(balance); continue

            if not in_trade:
                if buy_sig.iloc[i]:
                    shares = balance / close
                    entry_price, entry_date = close, dt
                    in_trade = True
            else:
                tp = close > u_cur and df_src["Close"].iloc[i - 1] <= u_prv
                sl = close <= entry_price * (1 - stop_pct)
                if tp or sl:
                    balance = shares * close
                    trades.append({
                        "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                        "Entry $":     round(entry_price, 2),
                        "Exit Date":   dt.strftime("%Y-%m-%d"),
                        "Exit $":      round(close, 2),
                        "Exit Reason": "Take Profit ✅" if tp else "Stop Loss 🛑",
                        "Return %":    round((close / entry_price - 1) * 100, 1),
                        "Balance $":   round(balance, 2),
                        "Strategy":    label,
                    })
                    in_trade = False

            eq_dates.append(dt)
            eq_vals.append(shares * close if in_trade else balance)

        if in_trade:
            close = df_src["Close"].iloc[-1]
            trades.append({
                "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                "Entry $":     round(entry_price, 2),
                "Exit Date":   "—",
                "Exit $":      round(close, 2),
                "Exit Reason": "Still Open 🟡",
                "Return %":    round((close / entry_price - 1) * 100, 1),
                "Balance $":   round(shares * close, 2),
                "Strategy":    label,
            })

        return round(balance, 2), trades, pd.Series(eq_vals, index=eq_dates)

    # ── Combined simulation (BB or KC exit depending on which triggered entry) ──
    def _run_combined_sim(df_src, buy_bb, buy_kc, bb_upper, kc_upper,
                          bb_stop, kc_stop, capital):
        balance = capital
        in_trade = False
        entry_price = entry_date = shares = active = None
        trades = []
        eq_dates, eq_vals = [], []

        for i in range(1, len(df_src)):
            dt    = df_src["Date"].iloc[i]
            close = df_src["Close"].iloc[i]
            bbu_c = bb_upper.iloc[i];   bbu_p = bb_upper.iloc[i - 1]
            kcu_c = kc_upper.iloc[i];   kcu_p = kc_upper.iloc[i - 1]

            if pd.isna(bbu_c) or pd.isna(kcu_c):
                eq_dates.append(dt); eq_vals.append(balance); continue

            if not in_trade:
                if buy_bb.iloc[i]:
                    shares = balance / close
                    entry_price, entry_date, active = close, dt, "BB"
                    in_trade = True
                elif buy_kc.iloc[i]:
                    shares = balance / close
                    entry_price, entry_date, active = close, dt, "KC"
                    in_trade = True
            else:
                stop_pct = bb_stop if active == "BB" else kc_stop
                u_c      = bbu_c   if active == "BB" else kcu_c
                u_p      = bbu_p   if active == "BB" else kcu_p
                tp = close > u_c and df_src["Close"].iloc[i - 1] <= u_p
                sl = close <= entry_price * (1 - stop_pct)
                if tp or sl:
                    balance = shares * close
                    trades.append({
                        "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                        "Entry $":     round(entry_price, 2),
                        "Exit Date":   dt.strftime("%Y-%m-%d"),
                        "Exit $":      round(close, 2),
                        "Exit Reason": "Take Profit ✅" if tp else "Stop Loss 🛑",
                        "Return %":    round((close / entry_price - 1) * 100, 1),
                        "Balance $":   round(balance, 2),
                        "Strategy":    active,
                    })
                    in_trade = False

            eq_dates.append(dt)
            eq_vals.append(shares * close if in_trade else balance)

        if in_trade:
            close = df_src["Close"].iloc[-1]
            trades.append({
                "Entry Date":  entry_date.strftime("%Y-%m-%d"),
                "Entry $":     round(entry_price, 2),
                "Exit Date":   "—",
                "Exit $":      round(close, 2),
                "Exit Reason": "Still Open 🟡",
                "Return %":    round((close / entry_price - 1) * 100, 1),
                "Balance $":   round(shares * close, 2),
                "Strategy":    active,
            })

        return round(balance, 2), trades, pd.Series(eq_vals, index=eq_dates)

    # ── Run all three sims on full history ─────────────────────────────────────
    _init_cap = 5_000.0

    _cb_final, _cb_trades, _cb_equity = _run_combined_sim(
        _cb_df_full, _buy_bb_full, _buy_kc_full,
        _bb_upper, _kc_upper, _cp["bb_stp"], _cp["kc_stp"], _init_cap,
    )
    _bb_final, _bb_trades, _bb_equity = _run_sim(
        _cb_df_full, _bb_cross_dn, _bb_upper, _cp["bb_stp"], _init_cap, "BB"
    )
    _kc_final, _kc_trades, _kc_equity = _run_sim(
        _cb_df_full, _kc_cross_dn & _lr_ok, _kc_upper, _cp["kc_stp"], _init_cap, "KC"
    )

    # ── Slice indicators and signals to selected date range ───────────────────
    _cb_mask = (
        (_cb_df_full["Date"].dt.date >= _cb_start) &
        (_cb_df_full["Date"].dt.date <= _cb_end)
    )
    _cb_df   = _cb_df_full[_cb_mask].reset_index(drop=True)

    def _s(series): return series[_cb_mask].reset_index(drop=True)

    _v_bb_upper = _s(_bb_upper);  _v_bb_lower = _s(_bb_lower);  _v_bb_sma = _s(_bb_sma)
    _v_kc_upper = _s(_kc_upper);  _v_kc_lower = _s(_kc_lower);  _v_kc_ema = _s(_kc_ema)
    _v_squeeze  = _s(_squeeze)
    _v_buy_bb   = _s(_buy_bb_full)
    _v_buy_kc   = _s(_buy_kc_full)

    if _cb_df.empty:
        st.warning("No data in selected date range.")
        st.stop()

    # ── Build regime background spans ──────────────────────────────────────────
    def _regime_spans(dates, mask):
        spans, in_span, t0 = [], False, None
        for i, (d, v) in enumerate(zip(dates, mask)):
            if v and not in_span:
                t0, in_span = d, True
            elif not v and in_span:
                spans.append((t0, dates.iloc[i - 1]))
                in_span = False
        if in_span:
            spans.append((t0, dates.iloc[-1]))
        return spans

    _ranging_spans  = _regime_spans(_cb_df["Date"], _v_squeeze)
    _trending_spans = _regime_spans(_cb_df["Date"], ~_v_squeeze)

    # ── Main price + regime chart ─────────────────────────────────────────────
    _fig_cb = go.Figure()

    # Regime shading
    for _s0, _s1 in _ranging_spans:
        _fig_cb.add_vrect(x0=_s0, x1=_s1,
                          fillcolor="rgba(99,110,250,0.07)", line_width=0, layer="below")
    for _s0, _s1 in _trending_spans:
        _fig_cb.add_vrect(x0=_s0, x1=_s1,
                          fillcolor="rgba(255,127,14,0.07)", line_width=0, layer="below")

    # Candlesticks
    _fig_cb.add_trace(go.Candlestick(
        x=_cb_df["Date"],
        open=_cb_df["Open"], high=_cb_df["High"],
        low=_cb_df["Low"],   close=_cb_df["Close"],
        name="Price",
        increasing=dict(line=dict(color="#555"), fillcolor="#555"),
        decreasing=dict(line=dict(color="#999"), fillcolor="rgba(0,0,0,0)"),
        showlegend=False,
    ))

    # BB bands (blue, dashed)
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_bb_upper, mode="lines",
        name=f"BB Upper (N={_cp['bb_n']}, K={_cp['bb_k']}σ)",
        line=dict(color="rgba(99,110,250,0.55)", width=1, dash="dot"),
    ))
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_bb_lower, mode="lines",
        name="BB Lower",
        line=dict(color="rgba(99,110,250,0.55)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(99,110,250,0.04)",
    ))
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_bb_sma, mode="lines",
        name=f"SMA({_cp['bb_n']})",
        line=dict(color="rgba(99,110,250,0.35)", width=1),
    ))

    # KC bands (orange, solid)
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_kc_upper, mode="lines",
        name=f"KC Upper (N={_cp['kc_n']}, K={_cp['kc_k']} ATR)",
        line=dict(color="rgba(255,127,14,0.65)", width=1.5),
    ))
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_kc_lower, mode="lines",
        name="KC Lower",
        line=dict(color="rgba(255,127,14,0.65)", width=1.5),
        fill="tonexty", fillcolor="rgba(255,127,14,0.04)",
    ))
    _fig_cb.add_trace(go.Scatter(
        x=_cb_df["Date"], y=_v_kc_ema, mode="lines",
        name=f"EMA({_cp['kc_n']})",
        line=dict(color="rgba(255,127,14,0.35)", width=1),
    ))

    # Buy signals — blue = from BB, orange = from KC
    if _cb_show_sig:
        if _v_buy_bb.any():
            _fig_cb.add_trace(go.Scatter(
                x=_cb_df["Date"][_v_buy_bb],
                y=_cb_df["Low"][_v_buy_bb] * 0.981,
                mode="markers", name="BB Buy ▲ (ranging)",
                marker=dict(symbol="triangle-up", size=11, color="#636EFA",
                            line=dict(color="navy", width=1)),
            ))
        if _v_buy_kc.any():
            _fig_cb.add_trace(go.Scatter(
                x=_cb_df["Date"][_v_buy_kc],
                y=_cb_df["Low"][_v_buy_kc] * 0.972,
                mode="markers", name="KC Buy ▲ (trending)",
                marker=dict(symbol="triangle-up", size=11, color="#FF7F0E",
                            line=dict(color="darkorange", width=1)),
            ))

    _fig_cb.update_layout(
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=10)),
        height=560,
        margin=dict(l=10, r=10, t=60, b=10),
        dragmode="pan",
    )
    st.plotly_chart(_fig_cb, use_container_width=True)

    # ── Regime stats ──────────────────────────────────────────────────────────
    _valid_mask  = _v_squeeze.notna()
    _total_days  = int(_valid_mask.sum())
    _ranging_d   = int(_v_squeeze[_valid_mask].sum())
    _trending_d  = _total_days - _ranging_d
    _cur_regime  = "🔵 Ranging → BB" if bool(_v_squeeze.dropna().iloc[-1]) else "🟠 Trending → KC"

    _rg1, _rg2, _rg3 = st.columns(3)
    _rg1.metric("Current Regime", _cur_regime)
    _rg2.metric("Ranging (BB active)",
                f"{_ranging_d}d  ({_ranging_d / _total_days * 100:.0f}%)")
    _rg3.metric("Trending (KC active)",
                f"{_trending_d}d  ({_trending_d / _total_days * 100:.0f}%)")

    st.divider()

    # ── Equity curve comparison ───────────────────────────────────────────────
    st.markdown("### 📈 Equity Curve Comparison")
    st.caption("All three strategies simulated from the same $5,000 starting capital over full history. "
               "Take profit = upper band crossing; stop loss = configured stop %.")

    # Slice equity curves to selected date range
    def _slice_equity(eq_series):
        if eq_series.empty:
            return pd.Series(dtype=float)
        eq_df = eq_series.reset_index()
        eq_df.columns = ["Date", "Value"]
        mask = (eq_df["Date"].dt.date >= _cb_start) & (eq_df["Date"].dt.date <= _cb_end)
        return eq_df[mask].set_index("Date")["Value"]

    _eq_cb_sliced = _slice_equity(_cb_equity)
    _eq_bb_sliced = _slice_equity(_bb_equity)
    _eq_kc_sliced = _slice_equity(_kc_equity)

    # Buy & hold baseline
    _bnh_start_price = _cb_df_full.loc[
        _cb_df_full["Date"].dt.date >= _cb_start, "Close"
    ].iloc[0] if (_cb_df_full["Date"].dt.date >= _cb_start).any() else _cb_df_full["Close"].iloc[0]

    _bnh_series = _cb_df.set_index("Date")["Close"] / _bnh_start_price * _init_cap

    _fig_eq = go.Figure()
    if not _eq_cb_sliced.empty:
        _fig_eq.add_trace(go.Scatter(
            x=_eq_cb_sliced.index, y=_eq_cb_sliced.values,
            mode="lines", name="Combined (BB+KC)",
            line=dict(color="#2ca02c", width=2.5),
        ))
    if not _eq_bb_sliced.empty:
        _fig_eq.add_trace(go.Scatter(
            x=_eq_bb_sliced.index, y=_eq_bb_sliced.values,
            mode="lines", name="BB Only",
            line=dict(color="#636EFA", width=1.5, dash="dot"),
        ))
    if not _eq_kc_sliced.empty:
        _fig_eq.add_trace(go.Scatter(
            x=_eq_kc_sliced.index, y=_eq_kc_sliced.values,
            mode="lines", name="KC Only",
            line=dict(color="#FF7F0E", width=1.5, dash="dot"),
        ))
    _fig_eq.add_trace(go.Scatter(
        x=_bnh_series.index, y=_bnh_series.values,
        mode="lines", name="Buy & Hold",
        line=dict(color="rgba(150,150,150,0.6)", width=1.5, dash="dash"),
    ))
    _fig_eq.update_layout(
        xaxis=dict(type="date", tickformat="%b %Y"),
        yaxis=dict(tickprefix="$", automargin=True),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=11)),
        height=360,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(_fig_eq, use_container_width=True)

    # ── 3-way performance comparison ──────────────────────────────────────────
    def _perf(final, trades_list, capital):
        closed = [t for t in trades_list if t["Exit Date"] != "—"]
        wins   = [t for t in closed if t["Return %"] > 0]
        ret_pct = (final / capital - 1) * 100
        wr = f"{len(wins)/len(closed)*100:.0f}%" if closed else "—"
        return ret_pct, len(trades_list), wr

    _r_cb, _n_cb, _w_cb = _perf(_cb_final, _cb_trades, _init_cap)
    _r_bb, _n_bb, _w_bb = _perf(_bb_final, _bb_trades, _init_cap)
    _r_kc, _n_kc, _w_kc = _perf(_kc_final, _kc_trades, _init_cap)
    _bnh_ret = (_cb_df_full["Close"].iloc[-1] / _cb_df_full["Close"].iloc[0] - 1) * 100

    _m1, _m2, _m3, _m4 = st.columns(4)
    _m1.metric("Combined Return",  f"{_r_cb:+.1f}%",
               f"${_cb_final:,.0f}  ·  {_n_cb} trades  ·  {_w_cb} win")
    _m2.metric("BB-Only Return",   f"{_r_bb:+.1f}%",
               f"${_bb_final:,.0f}  ·  {_n_bb} trades  ·  {_w_bb} win")
    _m3.metric("KC-Only Return",   f"{_r_kc:+.1f}%",
               f"${_kc_final:,.0f}  ·  {_n_kc} trades  ·  {_w_kc} win")
    _m4.metric("Buy & Hold",       f"{_bnh_ret:+.1f}%",
               f"${_cb_df_full['Close'].iloc[-1] / _cb_df_full['Close'].iloc[0] * _init_cap:,.0f}")

    st.divider()

    # ── Trade log ─────────────────────────────────────────────────────────────
    st.markdown("### 📋 Combined Strategy Trade Log")
    st.caption("Each trade shows which strategy (BB or KC) generated the signal based on the active regime at entry.")

    if not _cb_trades:
        st.info("No trades in the selected date range.")
    else:
        _cb_trade_df = pd.DataFrame(_cb_trades)
        _cb_trade_df.insert(0, "#", range(1, len(_cb_trade_df) + 1))
        # Re-order columns for readability
        _col_order = ["#", "Strategy", "Entry Date", "Entry $",
                      "Exit Date", "Exit $", "Exit Reason", "Return %", "Balance $"]
        _cb_trade_df = _cb_trade_df[[c for c in _col_order if c in _cb_trade_df.columns]]
        st.dataframe(_cb_trade_df, use_container_width=True, hide_index=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.caption(
        f"Data source: Yahoo Finance · "
        f"{len(_cb_df):,} trading days shown · "
        f"{_cb_df['Date'].iloc[0].date()} → {_cb_df['Date'].iloc[-1].date()}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# BB BACKTESTER TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_bt:
    REPORTS_DIR = Path(__file__).parent / "reports"

    # Per-ticker Bollinger reports: backtest_bb_<TICKER>.html (one per universe name)
    bb_reports = {
        r.stem.replace("backtest_bb_", ""): r
        for r in sorted(REPORTS_DIR.glob("backtest_bb_*.html"))
    }

    if bb_reports:
        st.caption("Single-ticker Bollinger Band mean-reversion grid search. "
                   "Pick any ticker in the universe — reports are precomputed in CI.")
        tickers_bb = sorted(bb_reports)
        chosen = st.selectbox("Ticker:", tickers_bb, index=0, key="bb_ticker_sel")
        report = bb_reports[chosen]
        html_content = report.read_text(encoding="utf-8")
        components.html(html_content, height=2400, scrolling=True)
    else:
        # Fallback to legacy single (dated) report naming if present
        legacy = sorted(
            [r for r in REPORTS_DIR.glob("backtest_*.html")
             if "keltner" not in r.name and not r.name.startswith("backtest_bb_")],
            reverse=True
        )
        if legacy:
            latest = legacy[0]
            st.markdown(f"**Report:** `{latest.name}`")
            if len(legacy) > 1:
                names  = [r.name for r in legacy]
                pick   = st.selectbox("Load a different report:", names, index=0)
                latest = REPORTS_DIR / pick
            components.html(latest.read_text(encoding="utf-8"), height=2400, scrolling=True)
        else:
            st.info("No Bollinger reports yet. The backtester generates one per "
                    "ticker (backtest_bb_<ticker>.html) on its next run.")


# ══════════════════════════════════════════════════════════════════════════════
# MULTI-LOOKBACK TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_ml:
    import plotly.subplots as psp

    ML_DIR = Path(__file__).parent / "reports"

    def _safe_read_csv(path):
        """Read a CSV, returning an empty DataFrame if the file is empty/headerless.

        Walk-forward files can be empty for post-IPO tickers that lack enough
        history for any window — pandas raises EmptyDataError on those.
        """
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    @st.cache_data(ttl=300)
    def load_ml_data():
        summary_files = sorted(ML_DIR.glob("ml_summary_*.csv"), reverse=True)
        if not summary_files:
            return None, {}, None
        latest      = summary_files[0]
        run_date_ml = latest.stem.replace("ml_summary_", "")
        summary     = pd.read_csv(latest)
        ticker_data = {}
        for ticker in summary["Ticker"]:
            gp = ML_DIR / f"ml_{ticker}_{run_date_ml}.csv"
            wp = ML_DIR / f"ml_wf_{ticker}_{run_date_ml}.csv"
            if gp.exists() and wp.exists():
                ticker_data[ticker] = {
                    "grid": _safe_read_csv(gp),
                    "wf":   _safe_read_csv(wp),
                }
        return summary, ticker_data, run_date_ml

    ml_summary, ml_ticker_data, ml_run_date = load_ml_data()

    if ml_summary is None or ml_summary.empty:
        st.info("No multi-lookback results yet. Run the backtester to generate them.")
    else:
        st.markdown(f"**Run:** `{ml_run_date}` &nbsp;·&nbsp; **Tickers:** {len(ml_summary)}", unsafe_allow_html=True)

        # ── Portfolio Overview table ──────────────────────────────────────────
        st.markdown("#### Portfolio Overview")

        disp = ml_summary[[
            "Ticker", "CAGR %", "Total Return %", "RDR", "Win %",
            "Max DD %", "Trades", "WF Profitable", "N1", "N2", "N3", "K", "Stop %",
        ]].copy()
        disp["Stop %"] = (disp["Stop %"] * 100).round(0).astype(int).astype(str) + "%"

        def _color_val(val, col):
            if col == "CAGR %":
                return "color:#1a7a3c" if isinstance(val, (int, float)) and val > 0 else "color:#c0392b"
            if col == "RDR":
                return "color:#1a7a3c" if isinstance(val, (int, float)) and val >= 5 else "color:#c0392b"
            if col == "Max DD %":
                return "color:#c0392b" if isinstance(val, (int, float)) and val > 30 else ""
            return ""

        styled = disp.style.format({
            "CAGR %":         "{:.1f}%",
            "Total Return %": "{:.1f}%",
            "RDR":            "{:.2f}",
            "Win %":          "{:.1f}%",
            "Max DD %":       "{:.1f}%",
            "K":              "{:.1f}",
        }).apply(
            lambda col: [_color_val(v, col.name) for v in col], axis=0
        )
        st.dataframe(styled, use_container_width=True, hide_index=True, height=min(400, 45 + 35 * len(disp)))

        # ── Ticker drill-down ─────────────────────────────────────────────────
        available_tickers = sorted(ml_ticker_data.keys())
        if not available_tickers:
            st.warning("Ticker-level CSV data not found — only summary is available.")
        else:
            selected_ml = st.selectbox("Drill into ticker:", available_tickers, key="ml_ticker_sel")
            grid_df = ml_ticker_data[selected_ml]["grid"]
            wf_df   = ml_ticker_data[selected_ml]["wf"]

            best_row = grid_df.loc[grid_df["Score"].idxmax()]

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("CAGR",        f"{best_row['CAGR %']:.1f}%")
            col2.metric("RDR",         f"{best_row['RDR']:.2f}")
            col3.metric("Win Rate",    f"{best_row['Win %']:.1f}%")
            col4.metric("Max DD",      f"{best_row['Max Drawdown %']:.1f}%")
            col5.metric("Trades",      f"{int(best_row['Trades'])}")

            sub_rs, sub_wf, sub_hm, sub_rr = st.tabs([
                "Response Surface", "Walk-Forward", "Heatmap", "Risk / Reward"
            ])

            # ── Response Surface ──────────────────────────────────────────────
            with sub_rs:
                st.caption("Smooth curve = generalized parameter. Spiky = overfit. Flat = irrelevant.")

                fig_rs = psp.make_subplots(
                    rows=2, cols=2,
                    subplot_titles=["N_base", "Gap", "K (std multiplier)", "Stop %"],
                    vertical_spacing=0.18, horizontal_spacing=0.12,
                )

                params_surface = [
                    ("N_base", "N_base", 1, 1),
                    ("Gap",    "Gap",    1, 2),
                    ("K",      "K",      2, 1),
                    ("Stop %", "Stop %", 2, 2),
                ]

                for col_name, _, row, col in params_surface:
                    grouped = grid_df.groupby(col_name)["Score"].max().reset_index()
                    x_vals  = grouped[col_name]
                    y_vals  = grouped["Score"]
                    if col_name == "Stop %":
                        x_vals = (x_vals * 100).round(0)
                    fig_rs.add_trace(
                        go.Scatter(
                            x=x_vals, y=y_vals,
                            mode="lines+markers",
                            line=dict(width=2),
                            marker=dict(size=6),
                            showlegend=False,
                            hovertemplate=f"{col_name}=%{{x}}<br>Max Score=%{{y:.1f}}<extra></extra>",
                        ),
                        row=row, col=col,
                    )

                fig_rs.update_layout(
                    height=480, margin=dict(t=50, b=30, l=40, r=20),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                )
                fig_rs.update_yaxes(title_text="Max Score")
                st.plotly_chart(fig_rs, use_container_width=True)

            # ── Walk-Forward ──────────────────────────────────────────────────
            with sub_wf:
                st.caption("Train return = in-sample best. Test return = out-of-sample. Proportionality = generalization.")

                if wf_df.empty or "Window" not in wf_df.columns:
                    st.info(
                        f"No walk-forward windows for **{selected_ml}** — likely a "
                        "post-2016 IPO with too little history to fill any "
                        "train/test window."
                    )
                else:
                    wf_plot = wf_df.copy()
                    wf_plot["Window"] = wf_plot["Window"].astype(str)
                    wf_plot["Test Label"] = wf_plot["Test Start"] + "–" + wf_plot["Test End"]

                    fig_wf = go.Figure()
                    fig_wf.add_trace(go.Bar(
                        x=wf_plot["Window"], y=wf_plot["Train Return %"],
                        name="In-sample (train)",
                        marker_color="#4c72b0",
                        hovertemplate="Window %{x}<br>Train: %{y:.1f}%<extra></extra>",
                    ))
                    fig_wf.add_trace(go.Bar(
                        x=wf_plot["Window"], y=wf_plot["Test Return %"],
                        name="Out-of-sample (test)",
                        marker_color=["#2ca02c" if v and v > 0 else "#d62728"
                                      for v in wf_plot["Test Return %"]],
                        hovertemplate="Window %{x}<br>Test: %{y:.1f}%<extra></extra>",
                    ))
                    fig_wf.add_hline(y=0, line_dash="dash", line_color="#999", line_width=1)
                    fig_wf.update_layout(
                        barmode="group", height=380,
                        xaxis_title="Window #", yaxis_title="Return %",
                        legend=dict(orientation="h", y=1.08),
                        margin=dict(t=30, b=40, l=50, r=20),
                        plot_bgcolor="#fafafa", paper_bgcolor="white",
                    )

                    # Annotate test CAGR above each bar
                    for _, r in wf_plot.iterrows():
                        if pd.notna(r.get("Test CAGR %")):
                            fig_wf.add_annotation(
                                x=r["Window"], y=max(r["Test Return %"] or 0, 0) + 1,
                                text=f"{r['Test CAGR %']:.1f}%",
                                showarrow=False, font=dict(size=9, color="#2ca02c"),
                                xanchor="center",
                            )

                    st.plotly_chart(fig_wf, use_container_width=True)

                    st.dataframe(
                        wf_df[["Window", "Train Start", "Train End", "Test Start", "Test End",
                                "Best N_base", "Best Gap", "Best K", "Best Stop",
                                "Train Return %", "Test Return %", "Test CAGR %", "Test Trades"]],
                        use_container_width=True, hide_index=True,
                    )

            # ── Heatmap (N_base × Gap) ────────────────────────────────────────
            with sub_hm:
                st.caption("Best Score for each (N_base, Gap) pair — holding K and Stop at their optimum.")

                hm_pivot = (
                    grid_df.groupby(["N_base", "Gap"])["Score"]
                    .max()
                    .reset_index()
                    .pivot(index="Gap", columns="N_base", values="Score")
                )

                fig_hm = go.Figure(go.Heatmap(
                    z=hm_pivot.values,
                    x=hm_pivot.columns.tolist(),
                    y=[str(g) for g in hm_pivot.index.tolist()],
                    colorscale="RdYlGn",
                    colorbar=dict(title="Score", thickness=14),
                    hovertemplate="N_base=%{x}<br>Gap=%{y}<br>Score=%{z:.1f}<extra></extra>",
                ))
                fig_hm.update_layout(
                    height=280,
                    xaxis=dict(title="N_base", tickfont=dict(size=10)),
                    yaxis=dict(title="Gap", tickfont=dict(size=11)),
                    margin=dict(t=20, b=50, l=50, r=20),
                    plot_bgcolor="white", paper_bgcolor="white",
                )
                st.plotly_chart(fig_hm, use_container_width=True)

            # ── Risk / Reward scatter ─────────────────────────────────────────
            with sub_rr:
                st.caption("Each point is one parameter combination. Top-right = high return + low drawdown (ideal).")

                sample = grid_df.sample(min(2000, len(grid_df)), random_state=42) if len(grid_df) > 2000 else grid_df

                fig_rr = go.Figure(go.Scatter(
                    x=sample["CAGR %"],
                    y=sample["Max Drawdown %"],
                    mode="markers",
                    marker=dict(
                        size=5,
                        color=sample["RDR"],
                        colorscale="RdYlGn",
                        cmin=0, cmax=min(20, sample["RDR"].quantile(0.95)),
                        colorbar=dict(title="RDR", thickness=14),
                        opacity=0.6,
                    ),
                    text=[f"N=({r.N1:.0f},{r.N2:.0f},{r.N3:.0f}) K={r.K} Stop={r['Stop %']:.0%}<br>"
                          f"CAGR={r['CAGR %']:.1f}% DD={r['Max Drawdown %']:.1f}% RDR={r['RDR']:.2f}"
                          for _, r in sample.iterrows()],
                    hoverinfo="text",
                ))

                # Mark the best combo
                fig_rr.add_trace(go.Scatter(
                    x=[best_row["CAGR %"]], y=[best_row["Max Drawdown %"]],
                    mode="markers",
                    marker=dict(size=14, color="gold", symbol="star",
                                line=dict(color="black", width=1)),
                    name="Best (Score)",
                    hovertemplate=(
                        f"Best combo<br>N=({int(best_row.N1)},{int(best_row.N2)},{int(best_row.N3)})"
                        f" K={best_row.K}<br>"
                        f"CAGR={best_row['CAGR %']:.1f}%  DD={best_row['Max Drawdown %']:.1f}%"
                        f"  RDR={best_row['RDR']:.2f}<extra></extra>"
                    ),
                ))

                fig_rr.update_layout(
                    height=420,
                    xaxis_title="CAGR %",
                    yaxis_title="Max Drawdown %",
                    legend=dict(orientation="h", y=1.05),
                    margin=dict(t=30, b=50, l=60, r=20),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                )
                st.plotly_chart(fig_rr, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# CROSS-SECTIONAL TAB  — single-position "biggest loser of the day" schedule
# ══════════════════════════════════════════════════════════════════════════════
with tab_cs:
    import plotly.subplots as psp_cs
    import plotly.express as px

    CS_DIR = Path(__file__).parent / "reports"

    @st.cache_data(ttl=300)
    def load_cs_data():
        summary_files = sorted(CS_DIR.glob("cs_summary_*.csv"), reverse=True)
        if not summary_files:
            return None
        latest   = summary_files[0]
        run_date = latest.stem.replace("cs_summary_", "")

        def _read(prefix):
            p = CS_DIR / f"{prefix}_{run_date}.csv"
            if not p.exists():
                return None
            try:
                return pd.read_csv(p)
            except pd.errors.EmptyDataError:
                return None

        return {
            "run_date": run_date,
            "summary":  pd.read_csv(latest),
            "trades":   _read("cs_trades"),
            "signal":   _read("cs_signal"),
            "equity":   _read("cs_equity"),
            "wf":       _read("cs_wf"),
            "grid":     _read("cs_grid"),
        }

    cs = load_cs_data()

    if cs is None or cs["summary"] is None or cs["summary"].empty:
        st.info("No cross-sectional results yet. Run `main_cross_sectional()` in the backtester to generate them.")
    else:
        srow      = cs["summary"].iloc[0]
        trades    = cs["trades"]
        signal    = cs["signal"]
        equity    = cs["equity"]
        wf_df     = cs["wf"]
        grid_df   = cs["grid"]
        run_date  = cs["run_date"]

        through   = str(srow.get("Data Through", run_date))
        n1, n2, n3 = int(srow["N1"]), int(srow["N2"]), int(srow["N3"])
        k_opt     = float(srow["K"])
        stop_opt  = float(srow["Stop %"])

        st.markdown(
            f"**Run:** `{run_date}` &nbsp;·&nbsp; **Data through:** `{through}` "
            f"&nbsp;·&nbsp; **Universe:** {int(srow['Universe'])} tickers "
            f"&nbsp;·&nbsp; **Global params:** N=({n1},{n2},{n3}) · K={k_opt:.1f} · "
            f"Stop={stop_opt*100:.0f}%",
            unsafe_allow_html=True,
        )

        # ── Today's action banner (the "biggest loser of the day" alert) ──────────
        if signal is not None and not signal.empty:
            sg    = signal.iloc[0]
            state = str(sg["State"]).upper()
            if state == "SELL":
                st.error(
                    f"**SELL SIGNAL — {sg['Ticker']}** — {sg.get('Reason', 'exit condition met')}. "
                    f"Entry ${float(sg.get('Entry $', 0)):.2f} → Last ${float(sg.get('Last $', 0)):.2f}. "
                    "Alpaca trader will place a market sell order tonight."
                )
            elif state == "HOLDING":
                entry_date = sg.get("Entry Date", "—")
                entry_info = f"entered {entry_date} @ " if entry_date != "—" else "entry via Alpaca @ "
                st.success(
                    f"**HOLDING {sg['Ticker']}** — {entry_info}"
                    f"${float(sg.get('Entry $', 0)):.2f}, last ${float(sg.get('Last $', 0)):.2f} "
                    f"(**{float(sg.get('Unrealized %', 0)):+.2f}%** unrealized). Hold until exit; ignore new signals."
                )
            elif state in ("BUY", "ENTER"):
                st.warning(
                    f"**BUY SIGNAL — {sg['Ticker']}** — most oversold in universe today. "
                    f"Last ${float(sg.get('Last $', 0)):.2f}. Alpaca trader will place a market buy order tonight."
                )
            else:
                st.info("**CASH** — no candidate is below the entry threshold today.")

        # True peak-to-trough drawdown from the daily equity curve (conventional
        # definition: each trough vs its own prior peak). The engine's CSV "Max DD %"
        # divides the worst *dollar* drawdown by the all-time peak, which understates
        # the felt percentage — so we recompute the honest figure here.
        true_dd_pct = None
        if equity is not None and not equity.empty:
            _eqv = equity["Equity"].astype(float)
            true_dd_pct = float((_eqv / _eqv.cummax() - 1).min() * 100)

        # ── Headline metrics ──────────────────────────────────────────────────────
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("CAGR",          f"{srow['CAGR %']:.1f}%")
        m2.metric("Total Return",  f"{srow['Total Return %']:.0f}%")
        m3.metric("RDR",           f"{srow['RDR']:.2f}")
        m4.metric("Win Rate",      f"{srow['Win %']:.1f}%")
        m5.metric("Max DD",
                  f"{true_dd_pct:.1f}%" if true_dd_pct is not None else f"-{srow['Max DD %']:.1f}%",
                  help="True peak-to-trough drawdown from the daily equity curve. "
                       f"(Engine CSV reports {srow['Max DD %']:.1f}%, which divides the "
                       "worst dollar drawdown by the all-time peak — display-only, does "
                       "not affect RDR/Score.)")
        m6.metric("WF Profitable", f"{srow['WF Profitable']}")

        st.caption(
            "Note: Schedule below uses the **full-period best-fit** params. Walk-forward "
            f"held up in only {srow['WF Profitable']} windows — treat as in-sample history, "
            "not an out-of-sample track record."
        )

        sub_sched, sub_eq, sub_wf, sub_rs = st.tabs([
            "Schedule", "Equity Curve", "Walk-Forward", "Response Surface"
        ])

        # ── 📅 SCHEDULE — the buy / hold / close timeline ─────────────────────────
        with sub_sched:
            if trades is None or trades.empty:
                st.warning("No trade log found for this run.")
            else:
                sched = trades.copy()
                sched["Entry Date"] = pd.to_datetime(sched["Entry Date"])
                sched["Exit Date"]  = pd.to_datetime(sched["Exit Date"])

                start_cap = (
                    float(equity["Equity"].iloc[0])
                    if equity is not None and not equity.empty else 5000.0
                )
                sched["Balance After $"] = start_cap * (1 + sched["Return %"] / 100.0).cumprod()
                sched["Cash Before (d)"] = (
                    sched["Entry Date"] - sched["Exit Date"].shift(1)
                ).dt.days.fillna(0).astype(int)

                # ── Gantt-style timeline: one lane per ticker, gaps = in cash ─────
                tl = sched[["Ticker", "Entry Date", "Exit Date", "Return %",
                            "Hold Days", "Reason"]].copy()
                tl["Outcome"] = np.where(tl["Return %"] >= 0, "Win", "Loss")

                # Append the currently-open position so the timeline shows live state
                if signal is not None and not signal.empty and \
                        str(signal.iloc[0]["State"]).upper() == "HOLDING":
                    sg = signal.iloc[0]
                    _entry_date_raw = sg.get("Entry Date", None)
                    if _entry_date_raw and str(_entry_date_raw) not in ("—", "nan", "None", ""):
                        _entry_dt = pd.to_datetime(_entry_date_raw)
                        tl = pd.concat([tl, pd.DataFrame([{
                            "Ticker":     sg["Ticker"],
                            "Entry Date": _entry_dt,
                            "Exit Date":  pd.to_datetime(through),
                            "Return %":   float(sg.get("Unrealized %", 0)),
                            "Hold Days":  (pd.to_datetime(through) - _entry_dt).days,
                            "Reason":     "open",
                            "Outcome":    "Open",
                        }])], ignore_index=True)

                lane_order = (
                    tl.groupby("Ticker")["Entry Date"].min().sort_values().index.tolist()
                )

                fig_tl = px.timeline(
                    tl, x_start="Entry Date", x_end="Exit Date", y="Ticker",
                    color="Outcome",
                    color_discrete_map={"Win": "#2ca02c", "Loss": "#d62728",
                                        "Open": "#f1c40f"},
                    category_orders={"Ticker": lane_order,
                                     "Outcome": ["Win", "Loss", "Open"]},
                    hover_data={"Return %": ":.1f", "Hold Days": True,
                                "Reason": True, "Entry Date": "|%Y-%m-%d",
                                "Exit Date": "|%Y-%m-%d", "Ticker": False},
                )
                fig_tl.update_yaxes(autorange="reversed", title=None)
                fig_tl.update_layout(
                    height=max(280, 28 * len(lane_order) + 90),
                    margin=dict(t=20, b=40, l=10, r=10),
                    legend=dict(orientation="h", y=1.06, title=None),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                    xaxis_title=None,
                )
                st.plotly_chart(fig_tl, use_container_width=True)
                st.caption(
                    "Each bar = one holding (single position at a time). Gaps between "
                    "bars = in cash. Green = win, red = loss, gold = currently open."
                )

                # ── The schedule table with running balance ───────────────────────
                disp = sched.copy()
                disp.insert(0, "#", range(1, len(disp) + 1))
                disp["Buy"]   = disp["Entry Date"].dt.strftime("%Y-%m-%d")
                disp["Close"] = disp["Exit Date"].dt.strftime("%Y-%m-%d")
                disp = disp[["#", "Buy", "Ticker", "Close", "Hold Days",
                             "Cash Before (d)", "Return %", "Balance After $", "Reason"]]

                styled_sched = disp.style.format({
                    "Return %":        "{:+.1f}%",
                    "Balance After $": "${:,.0f}",
                }).apply(
                    lambda col: [
                        ("color:#1a7a3c" if isinstance(v, (int, float)) and v >= 0
                         else "color:#c0392b")
                        if col.name == "Return %" else "" for v in col
                    ], axis=0
                )
                st.dataframe(
                    styled_sched, use_container_width=True, hide_index=True,
                    height=min(640, 45 + 35 * len(disp)),
                )

                csv_bytes = disp.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download schedule (CSV)", csv_bytes,
                    file_name=f"investment_schedule_{run_date}.csv",
                    mime="text/csv",
                )

        # ── 📈 EQUITY CURVE ───────────────────────────────────────────────────────
        with sub_eq:
            if equity is None or equity.empty:
                st.warning("No equity curve found for this run.")
            else:
                eq = equity.copy()
                eq["Date"] = pd.to_datetime(eq["Date"])
                start_cap  = float(eq["Equity"].iloc[0])
                running_max = eq["Equity"].cummax()
                dd_pct = (eq["Equity"] / running_max - 1) * 100

                fig_eq = psp_cs.make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.72, 0.28], vertical_spacing=0.06,
                    subplot_titles=["Portfolio equity (log scale)", "Drawdown %"],
                )
                fig_eq.add_trace(go.Scatter(
                    x=eq["Date"], y=eq["Equity"], mode="lines",
                    line=dict(color="#4c72b0", width=2), name="Equity",
                    hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.0f}<extra></extra>",
                ), row=1, col=1)
                fig_eq.add_hline(y=start_cap, line_dash="dash", line_color="#999",
                                 line_width=1, row=1, col=1)
                fig_eq.add_trace(go.Scatter(
                    x=eq["Date"], y=dd_pct, mode="lines",
                    line=dict(color="#d62728", width=1), fill="tozeroy",
                    fillcolor="rgba(214,39,40,0.15)", name="Drawdown",
                    hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}%<extra></extra>",
                ), row=2, col=1)
                fig_eq.update_yaxes(type="log", row=1, col=1)
                fig_eq.update_layout(
                    height=460, showlegend=False,
                    margin=dict(t=40, b=30, l=50, r=20),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                )
                st.plotly_chart(fig_eq, use_container_width=True)
                st.caption(
                    f"Started at ${start_cap:,.0f} → ended at "
                    f"${eq['Equity'].iloc[-1]:,.0f}. Log scale so early and late "
                    "moves are equally legible."
                )

        # ── 🔬 WALK-FORWARD ───────────────────────────────────────────────────────
        with sub_wf:
            if wf_df is None or wf_df.empty:
                st.warning("No walk-forward results found for this run.")
            else:
                st.caption(
                    "Train = in-sample best per window. Test = out-of-sample. "
                    "Red test bars / jumping best-params = overfitting signal."
                )
                wf_plot = wf_df.copy()
                wf_plot["Window"] = wf_plot["Window"].astype(str)

                fig_cswf = go.Figure()
                fig_cswf.add_trace(go.Bar(
                    x=wf_plot["Window"], y=wf_plot["Train Return %"],
                    name="In-sample (train)", marker_color="#4c72b0",
                    hovertemplate="Window %{x}<br>Train: %{y:.1f}%<extra></extra>",
                ))
                fig_cswf.add_trace(go.Bar(
                    x=wf_plot["Window"], y=wf_plot["Test Return %"],
                    name="Out-of-sample (test)",
                    marker_color=["#2ca02c" if v and v > 0 else "#d62728"
                                  for v in wf_plot["Test Return %"]],
                    hovertemplate="Window %{x}<br>Test: %{y:.1f}%<extra></extra>",
                ))
                fig_cswf.add_hline(y=0, line_dash="dash", line_color="#999", line_width=1)
                fig_cswf.update_layout(
                    barmode="group", height=360,
                    xaxis_title="Window #", yaxis_title="Return %",
                    legend=dict(orientation="h", y=1.1),
                    margin=dict(t=30, b=40, l=50, r=20),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                )
                st.plotly_chart(fig_cswf, use_container_width=True)
                st.dataframe(
                    wf_df[["Window", "Train Start", "Train End", "Test Start", "Test End",
                           "Best N_base", "Best Gap", "Best K", "Best Stop",
                           "Train Return %", "Test Return %", "Test CAGR %", "Test Trades"]],
                    use_container_width=True, hide_index=True,
                )

        # ── 🎛 RESPONSE SURFACE (global params) ────────────────────────────────────
        with sub_rs:
            if grid_df is None or grid_df.empty:
                st.warning("No grid-search results found for this run.")
            else:
                st.caption(
                    "Smooth curve = generalized parameter. Spiky = overfit. "
                    "Flat = irrelevant. (One global param set across the whole universe.)"
                )
                fig_csrs = psp_cs.make_subplots(
                    rows=2, cols=2,
                    subplot_titles=["N_base", "Gap", "K (std multiplier)", "Stop %"],
                    vertical_spacing=0.18, horizontal_spacing=0.12,
                )
                for col_name, row, col in [("N_base", 1, 1), ("Gap", 1, 2),
                                           ("K", 2, 1), ("Stop %", 2, 2)]:
                    grouped = grid_df.groupby(col_name)["Score"].max().reset_index()
                    x_vals  = grouped[col_name]
                    if col_name == "Stop %":
                        x_vals = (x_vals * 100).round(0)
                    fig_csrs.add_trace(go.Scatter(
                        x=x_vals, y=grouped["Score"], mode="lines+markers",
                        line=dict(width=2), marker=dict(size=6), showlegend=False,
                        hovertemplate=f"{col_name}=%{{x}}<br>Max Score=%{{y:.1f}}<extra></extra>",
                    ), row=row, col=col)
                fig_csrs.update_layout(
                    height=480, margin=dict(t=50, b=30, l=40, r=20),
                    plot_bgcolor="#fafafa", paper_bgcolor="white",
                )
                fig_csrs.update_yaxes(title_text="Max Score")
                st.plotly_chart(fig_csrs, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# KC BACKTESTER TAB  [ARCHIVED]
# ══════════════════════════════════════════════════════════════════════════════
if False:  # ARCHIVED — re-enable by restoring tab_kc_bt to st.tabs() call
    KC_REPORTS_DIR = Path(__file__).parent / "reports"
    kc_reports = sorted(KC_REPORTS_DIR.glob("backtest_keltner_*.html"), reverse=True)
    if not kc_reports:
        st.info("No Keltner backtest report found. Run `python backtester.py` to generate one.")
    else:
        latest = kc_reports[0]
        st.markdown(f"**Report:** `{latest.name}`")
        if len(kc_reports) > 1:
            names = [r.name for r in kc_reports]
            chosen = st.selectbox("Load a different KC report:", names, index=0)
            latest = KC_REPORTS_DIR / chosen
        html_content = latest.read_text(encoding="utf-8")
        components.html(html_content, height=2400, scrolling=True)


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE SURFACE TAB  — radio-knob overfitting diagnostic
# ══════════════════════════════════════════════════════════════════════════════
with tab_rs:

    RS_DIR = Path(__file__).parent / "reports"

    @st.cache_data(ttl=300)
    def load_rs_data():
        grid_files    = sorted(RS_DIR.glob("cs_grid_*.csv"),    reverse=True)
        summary_files = sorted(RS_DIR.glob("cs_summary_*.csv"), reverse=True)
        if not grid_files or not summary_files:
            return None, None
        try:
            df_g = pd.read_csv(grid_files[0])
            df_s = pd.read_csv(summary_files[0])
            return df_g, df_s
        except (pd.errors.EmptyDataError, Exception):
            return None, None

    df_grid_rs, df_sum_rs = load_rs_data()

    if df_grid_rs is None or df_grid_rs.empty:
        st.info("No cross-sectional grid data found. Run the backtester to generate results.")
    else:
        # ── Identify best combo ────────────────────────────────────────────────
        best_row_rs  = df_grid_rs.loc[df_grid_rs["Score"].idxmax()]
        best_n_base  = int(best_row_rs["N_base"])
        best_gap     = int(best_row_rs["Gap"])
        best_k       = float(best_row_rs["K"])
        best_stop    = float(best_row_rs["Stop %"])
        best_vals_rs = {
            "N_base":  best_n_base,
            "Gap":     best_gap,
            "K":       best_k,
            "Stop %":  best_stop,
        }

        # ── Parameter definitions ──────────────────────────────────────────────
        RS_PARAMS = [
            {"col": "N_base", "label": "N_base",  "title": "N_base — Base lookback (days)"},
            {"col": "Gap",    "label": "Gap",      "title": "Gap — Window spacing (days)"},
            {"col": "K",      "label": "K",        "title": "K — Band width (σ)"},
            {"col": "Stop %", "label": "Stop %",   "title": "Stop % — Stop loss"},
        ]

        def _ntv(series):
            """Normalized Total Variation: sum|Δy| / range(y).
            ~1 = smooth/monotone  |  >2.5 moderate  |  >5 spiky/overfit."""
            y = series.dropna().values
            if len(y) < 2:
                return float("nan")
            rng = float(y.max() - y.min())
            return float(np.abs(np.diff(y)).sum() / rng) if rng > 1e-9 else 0.0

        def _badge(ntv):
            if np.isnan(ntv):  return "N/A"
            if ntv < 0.001:    return "FLAT — negligible effect"
            if ntv < 2.5:      return "SMOOTH — well-generalized"
            if ntv < 5.0:      return "MODERATE — some roughness"
            return "SPIKY — overfit risk"

        # ── Header ────────────────────────────────────────────────────────────
        st.markdown("## Response Surface Analysis")
        st.caption(
            '**The radio-knob test** (from the gold standard): hold all parameters fixed at their '
            'optimal values and slowly vary one. **Smooth output = generalized.** '
            'Spiky output = likely overfit to unrepeatable events. Flat = irrelevant, consider removing.'
        )

        # ── Best combo metrics ─────────────────────────────────────────────────
        mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
        mc1.metric("N_base",  best_n_base)
        mc2.metric("Gap",     best_gap)
        mc3.metric("K",       f"{best_k:.1f}")
        mc4.metric("Stop %",  f"{best_stop*100:.0f}%")
        mc5.metric("CAGR %",  f"{best_row_rs['CAGR %']:.1f}%")
        mc6.metric("RDR",     f"{best_row_rs['RDR']:.2f}")
        st.divider()

        # ── Metric toggle ─────────────────────────────────────────────────────
        rs_metric = st.radio(
            "Objective metric for surface plots",
            ["RDR", "CAGR %", "Score"],
            horizontal=True, key="rs_metric",
            help="RDR = Return/Drawdown ratio (risk-adjusted). CAGR % = raw annualized return. Score = composite.",
        )

        st.divider()

        # ══ Section 1: 1D Slices ══════════════════════════════════════════════
        st.markdown("### 1D Parameter Slices — Radio Knob Test")
        st.caption(
            "**Blue solid + band** = marginal median ± IQR (averaged across all other param values — most robust view).  "
            "**Red dashed** = slice through the optimum (other 3 params pinned to best values).  "
            "**●** = optimal value."
        )

        diag_rows = []
        slice_cols = st.columns(2)

        for idx, param in enumerate(RS_PARAMS):
            col_name  = param["col"]
            title     = param["title"]
            best_val  = best_vals_rs[col_name]
            others    = [p for p in RS_PARAMS if p["col"] != col_name]

            # Marginal: group by this param, aggregate across everything else
            grp = df_grid_rs.groupby(col_name)[rs_metric]
            marginal = grp.agg(
                median="median",
                q25=lambda s: s.quantile(0.25),
                q75=lambda s: s.quantile(0.75),
            ).reset_index().sort_values(col_name)

            # Slice: pin other 3 params to their optimal values
            sl_mask = pd.Series([True] * len(df_grid_rs), index=df_grid_rs.index)
            for op in others:
                ov = best_vals_rs[op["col"]]
                if op["col"] in ("K", "Stop %"):
                    sl_mask &= (df_grid_rs[op["col"]] - ov).abs() < 1e-9
                else:
                    sl_mask &= df_grid_rs[op["col"]] == ov
            slice_df = df_grid_rs[sl_mask].sort_values(col_name)

            ntv   = _ntv(marginal["median"])
            badge = _badge(ntv)
            diag_rows.append({
                "Parameter":   title,
                "Optimal":     f"{best_val*100:.0f}%" if col_name == "Stop %" else str(best_val),
                "NTV":         round(ntv, 2),
                "Verdict":     badge,
            })

            # x-axis labels: format Stop % as %
            def _fmt_x(v):
                return f"{v*100:.0f}%" if col_name == "Stop %" else str(v)

            x_marg  = [_fmt_x(v) for v in marginal[col_name]]
            x_slice = [_fmt_x(v) for v in slice_df[col_name]]

            fig1d = go.Figure()

            # IQR band (filled)
            fig1d.add_trace(go.Scatter(
                x=x_marg + x_marg[::-1],
                y=list(marginal["q75"]) + list(marginal["q25"])[::-1],
                fill="toself",
                fillcolor="rgba(99,110,250,0.15)",
                line=dict(color="rgba(0,0,0,0)"),
                name="IQR (25–75%)",
                showlegend=True,
            ))

            # Marginal median
            fig1d.add_trace(go.Scatter(
                x=x_marg, y=list(marginal["median"]),
                mode="lines+markers",
                line=dict(color="#636EFA", width=2.5),
                marker=dict(size=6),
                name="Marginal median",
            ))

            # Optimal slice
            if not slice_df.empty:
                fig1d.add_trace(go.Scatter(
                    x=x_slice, y=list(slice_df[rs_metric]),
                    mode="lines+markers",
                    line=dict(color="#EF553B", width=1.5, dash="dash"),
                    marker=dict(size=4),
                    name="Slice @ optimum",
                ))

            # Star at optimal value
            opt_label = _fmt_x(best_val)
            if opt_label in x_marg:
                opt_y = float(marginal.loc[marginal[col_name] == best_val, "median"].iloc[0])
                fig1d.add_trace(go.Scatter(
                    x=[opt_label], y=[opt_y],
                    mode="markers",
                    marker=dict(symbol="star", size=18, color="#FFD700",
                                line=dict(color="#333", width=1)),
                    name="Optimal",
                ))

            fig1d.update_layout(
                title=dict(
                    text=f"{title}<br><sup>{badge} &nbsp;|&nbsp; NTV = {ntv:.2f}</sup>",
                    font=dict(size=13),
                ),
                xaxis_title=param["label"],
                yaxis_title=rs_metric,
                height=320,
                margin=dict(t=75, b=50, l=55, r=15),
                legend=dict(orientation="h", y=-0.35, font=dict(size=10)),
                hovermode="x unified",
            )

            with slice_cols[idx % 2]:
                st.plotly_chart(fig1d, use_container_width=True)

        st.divider()

        # ══ Section 2: Smoothness diagnostics table ════════════════════════════
        st.markdown("### Parameter Diagnostics")
        st.caption(
            "**NTV** (Normalized Total Variation) of the marginal median curve. "
            "~1 = smooth/monotone — safe. >2.5 = moderate roughness. >5 = overfit risk."
        )
        st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)

        st.divider()

        # ══ Section 3: 2D Heatmap ══════════════════════════════════════════════
        st.markdown("### 2D Response Surface Heatmap")
        st.caption(
            "Vary two parameters simultaneously; remaining two are pinned to optimal. "
            "A smooth, broad plateau = robust. A sharp spike = fragile / overfit."
        )

        hm_options = [p["title"] for p in RS_PARAMS]
        hm_c1, hm_c2 = st.columns(2)
        with hm_c1:
            x_title = st.selectbox("X axis", hm_options, index=0, key="rs_hm_x")
        with hm_c2:
            y_title = st.selectbox("Y axis", [o for o in hm_options if o != x_title],
                                   index=0, key="rs_hm_y")

        x_p = next(p for p in RS_PARAMS if p["title"] == x_title)
        y_p = next(p for p in RS_PARAMS if p["title"] == y_title)
        fixed_ps = [p for p in RS_PARAMS if p["title"] not in (x_title, y_title)]

        hm_mask = pd.Series([True] * len(df_grid_rs), index=df_grid_rs.index)
        for fp in fixed_ps:
            fv = best_vals_rs[fp["col"]]
            if fp["col"] in ("K", "Stop %"):
                hm_mask &= (df_grid_rs[fp["col"]] - fv).abs() < 1e-9
            else:
                hm_mask &= df_grid_rs[fp["col"]] == fv
        hm_df = df_grid_rs[hm_mask]

        if hm_df.empty:
            st.warning("No data for this parameter combination — try a different axis pair.")
        else:
            pivot = hm_df.pivot_table(
                index=y_p["col"], columns=x_p["col"],
                values=rs_metric, aggfunc="median",
            )

            # Format axis tick labels
            def _fmt_col(col, vals):
                if col == "Stop %":
                    return [f"{v*100:.0f}%" for v in vals]
                return [str(v) for v in vals]

            x_ticks = _fmt_col(x_p["col"], pivot.columns.tolist())
            y_ticks = _fmt_col(y_p["col"], pivot.index.tolist())

            fig_hm = go.Figure(go.Heatmap(
                z=pivot.values.tolist(),
                x=x_ticks,
                y=y_ticks,
                colorscale="RdYlGn",
                colorbar=dict(title=rs_metric, thickness=14),
                hoverongaps=False,
                hovertemplate=f"{x_p['label']}: %{{x}}<br>{y_p['label']}: %{{y}}<br>{rs_metric}: %{{z:.2f}}<extra></extra>",
            ))

            # Mark optimal point
            ox = _fmt_col(x_p["col"], [best_vals_rs[x_p["col"]]])[0]
            oy = _fmt_col(y_p["col"], [best_vals_rs[y_p["col"]]])[0]
            if ox in x_ticks and oy in y_ticks:
                fig_hm.add_trace(go.Scatter(
                    x=[ox], y=[oy],
                    mode="markers+text",
                    marker=dict(symbol="star", size=20, color="#FFD700",
                                line=dict(color="#333", width=1.5)),
                    text=["● best"],
                    textposition="top center",
                    textfont=dict(size=11, color="#333"),
                    name="Optimal",
                    showlegend=False,
                ))

            # Fixed params annotation
            fixed_label = "  |  ".join(
                f"{fp['label']} = {_fmt_col(fp['col'], [best_vals_rs[fp['col']]])[0]}"
                for fp in fixed_ps
            )
            fig_hm.update_layout(
                title=dict(
                    text=f"{rs_metric}: {y_p['label']} × {x_p['label']}<br>"
                         f"<sup>Fixed: {fixed_label}</sup>",
                    font=dict(size=13),
                ),
                xaxis_title=x_p["title"],
                yaxis_title=y_p["title"],
                height=480,
                margin=dict(t=90, b=70, l=80, r=20),
            )
            st.plotly_chart(fig_hm, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY RULES TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_rules:
    RULES_PATH = Path(__file__).parent / "STRATEGY_RULES.md"

    if not RULES_PATH.exists():
        st.error("❌ STRATEGY_RULES.md not found.")
    else:
        _rt = RULES_PATH.read_text()

        def _val(symbol: str, pct: bool = False, prefix: str = "") -> str:
            full = f"{prefix}{symbol}" if prefix else symbol
            pattern = rf"\|\s*`{full}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
            m = re.search(pattern, _rt)
            if not m:
                return "—"
            v = m.group(1)
            return f"**{v}%**" if pct else f"**{v}**"

        st.markdown("## Bollinger Band Strategy")
        st.markdown(f"""
**Strategy Inputs**

| Symbol | Value | Description |
|--------|-------|-------------|
| `N` | {_val("N")} | Lookback period (days) |
| `K` | {_val("K")} | Std deviation multiplier |
| `StopPct` | {_val("StopPct", pct=True)} | Stop loss threshold |
| Take Profit | Close crosses upper BB | Exit rule |

**Filters / Validation**

| Symbol | Value | Description |
|--------|-------|-------------|
| `RDR_THRESHOLD` | {_val("RDR_THRESHOLD")} | Minimum Return-to-Drawdown Ratio |
| `MIN_TRADES` | {_val("MIN_TRADES")} | Minimum completed trades |
| `CAGR_THRESHOLD` | {_val("CAGR_THRESHOLD", pct=True)} | Minimum annualized return |

**Walk-Forward Analysis**

| Symbol | Value | Description |
|--------|-------|-------------|
| `WF_TRAIN_YEARS` | {_val("WF_TRAIN_YEARS")} | Training window (years) |
| `WF_TEST_YEARS` | {_val("WF_TEST_YEARS")} | Out-of-sample test window (years) |
| `WF_STEP_MONTHS` | {_val("WF_STEP_MONTHS")} | Slide step (months) |
| `WF_MIN_TRADES` | {_val("WF_MIN_TRADES")} | Min trades required per training window |

**Hardcoded in backtester only**

| Variable | Value |
|----------|-------|
| `INITIAL_CAPITAL` | $5,000 |
| `SCORE_DIVISOR` | 100 |
| `N_VALUES` | 16–54 |
| `K_VALUES` | 1.5–3.2 |
""")

        st.divider()

        st.markdown("## Keltner Channel Strategy")
        st.markdown(f"""
| Symbol | Value | Description |
|--------|-------|-------------|
| `KC_N` | {_val("N", prefix="KC_")} | EMA/ATR lookback (days) |
| `KC_K` | {_val("K", prefix="KC_")} | ATR multiplier |
| `KC_StopPct` | {_val("StopPct", pct=True, prefix="KC_")} | Stop loss threshold |
| `KC_LR_PERIOD` | {_val("LR_PERIOD", prefix="KC_")} | Trend filter lookback (0 = disabled) |

**Filters / Validation**

| Symbol | Value | Description |
|--------|-------|-------------|
| `KC_RDR_THRESHOLD` | {_val("RDR_THRESHOLD", prefix="KC_")} | Minimum RDR |
| `KC_MIN_TRADES` | {_val("MIN_TRADES", prefix="KC_")} | Min completed trades |
| `KC_CAGR_THRESHOLD` | {_val("CAGR_THRESHOLD", pct=True, prefix="KC_")} | Min annualized return |

**Walk-Forward**

| Symbol | Value | Description |
|--------|-------|-------------|
| `KC_WF_TRAIN_YEARS` | {_val("WF_TRAIN_YEARS", prefix="KC_")} | Training window (years) |
| `KC_WF_TEST_YEARS` | {_val("WF_TEST_YEARS", prefix="KC_")} | Test window (years) |
| `KC_WF_STEP_MONTHS` | {_val("WF_STEP_MONTHS", prefix="KC_")} | Step (months) |
| `KC_WF_MIN_TRADES` | {_val("WF_MIN_TRADES", prefix="KC_")} | Min trades per WF window |

**Hardcoded in backtester only**

| Variable | Value |
|----------|-------|
| `KC N_VALUES` | 10–34 |
| `KC K_VALUES` | 1.0–2.5 |
""")
