import re
import streamlit as st
import streamlit.components.v1 as components
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

# ── Top-level tabs ─────────────────────────────────────────────────────────────
tab_viz, tab_bt, tab_rules = st.tabs(["📈 Visualizer", "⚙️ Backtester", "📋 Strategy Rules"])

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

        N        = extract("N")
        K        = extract("K")
        StopPct  = extract("StopPct") / 100
        return {"N": N, "K": K, "StopPct": StopPct}

    params   = load_strategy_params()
    N        = params["N"]
    K        = params["K"]
    STOP_PCT = params["StopPct"]

    # ── Helpers ───────────────────────────────────────────────────────────────
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


    # ── Load GSIT ─────────────────────────────────────────────────────────────
    DATA_DIR = Path(__file__).parent / "data"
    df_full  = pd.read_csv(DATA_DIR / "GSIT_daily_high_low.csv", parse_dates=["Date"])
    df_full  = df_full.sort_values("Date").reset_index(drop=True)

    global_min = df_full["Date"].min().date()
    global_max = df_full["Date"].max().date()

    # ── Active strategy parameters (read-only display) ────────────────────────
    with st.expander("📋 Active Strategy Parameters", expanded=False):
        st.caption("Parameters are defined in `STRATEGY_RULES.md` and cannot be changed here.")
        c1, c2 = st.columns(2)
        c1.metric("N (Lookback)", N)
        c2.metric("K (Std Dev ×)", K)

    # ── Date range + signal toggle ─────────────────────────────────────────────
    with st.expander("⚙️ View Settings", expanded=False):
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
    _, _sim_trades = simulate_portfolio(df, sma, lower_bb, 5000.0, STOP_PCT)
    _outcome_map   = {t["Entry Date"]: t for t in _sim_trades}

    # ── Signal Navigator ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 🔍 Signal Navigator")

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

        _c1, _c2, _c3 = st.columns([1, 5, 1])
        with _c1:
            if st.button("← Prev", disabled=st.session_state.nav_idx == 0, use_container_width=True):
                st.session_state.nav_idx -= 1
                st.rerun()
        with _c3:
            if st.button("Next →", disabled=st.session_state.nav_idx == len(_all_signals) - 1, use_container_width=True):
                st.session_state.nav_idx += 1
                st.rerun()
        with _c2:
            st.markdown(
                f"<div style='text-align:center;padding-top:0.35rem'>"
                f"Signal <strong>{st.session_state.nav_idx + 1}</strong> of <strong>{len(_all_signals)}</strong>"
                f" &nbsp;·&nbsp; <strong>{_sig['type']}</strong>"
                f" &nbsp;·&nbsp; {_sig['date'].strftime('%b %d, %Y')}"
                f" &nbsp;·&nbsp; ${_sig['price']:.2f}"
                f"</div>", unsafe_allow_html=True
            )

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
                    _is_tp    = _oc["Exit Reason"] == "Take Profit ✅"
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
                _sma_at = sma_full.iloc[_fi]
                _i1, _i2, _i3, _i4, _i5 = st.columns(5)
                _i1.metric("Entry Price",       f"${_sig['price']:.2f}")
                _i2.metric("Stop Loss",         f"${_sig['price'] * (1 - STOP_PCT):.2f}")
                _i3.metric("Take Profit (SMA)", f"${_sma_at:.2f}" if not pd.isna(_sma_at) else "—")
                _i4.metric("Exit Price",        f"${_oc['Exit $']:.2f}"      if _oc else "—")
                _i5.metric("Return",            f"{_oc['Return %']:+.1f}%"   if _oc else "—",
                           delta=f"{_oc['Exit Reason']}" if _oc else None,
                           delta_color="normal" if _oc and "✅" in _oc.get("Exit Reason","") else "inverse")
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

    # ── Footer ─────────────────────────────────────────────────────────────────
    most_recent = df_full["Date"].max().strftime("%B %d, %Y")
    st.caption(f"Data source: Yahoo Finance · Most recent data: {most_recent} · Updates daily at 6pm ET on weekdays")


# ══════════════════════════════════════════════════════════════════════════════
# BACKTESTER TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_bt:
    REPORTS_DIR = Path(__file__).parent / "reports"
    reports = sorted(REPORTS_DIR.glob("backtest_*.html"), reverse=True)

    if not reports:
        st.info("No backtest report found. Run `python backtester.py` locally to generate one.")
    else:
        latest = reports[0]
        st.markdown(f"**Report:** `{latest.name}`")

        if len(reports) > 1:
            names  = [r.name for r in reports]
            chosen = st.selectbox("Load a different report:", names, index=0)
            latest = REPORTS_DIR / chosen

        html_content = latest.read_text(encoding="utf-8")
        components.html(html_content, height=2400, scrolling=True)


# ══════════════════════════════════════════════════════════════════════════════
# STRATEGY RULES TAB
# ══════════════════════════════════════════════════════════════════════════════
with tab_rules:
    RULES_PATH = Path(__file__).parent / "STRATEGY_RULES.md"

    if not RULES_PATH.exists():
        st.error("❌ STRATEGY_RULES.md not found.")
    else:
        _rt = RULES_PATH.read_text()

        def _val(symbol: str, pct: bool = False) -> str:
            pattern = rf"\|\s*`{symbol}`\s*\|\s*\*{{0,2}}([0-9]+(?:\.[0-9]+)?)%?\*{{0,2}}\s*\|"
            m = re.search(pattern, _rt)
            if not m:
                return "—"
            v = m.group(1)
            return f"**{v}%**" if pct else f"**{v}**"

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

**Hardcoded in backtester only (not in Strategy Rules)**

| Variable | Value |
|----------|-------|
| `INITIAL_CAPITAL` | $5,000 |
| `SCORE_DIVISOR` | 100 |
| `N_VALUES` | 16–54 |
| `K_VALUES` | 1.5–3.2 |
""")
