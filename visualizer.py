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
tab_viz, tab_bt, tab_rules = st.tabs([
    "📈 Bollinger", "⚙️ BB Backtest", "📋 Strategy Rules"
])
# ARCHIVED tabs (KC + Combined — low confidence, re-enable when ready):
# tab_kc_viz, tab_combined, tab_kc_bt

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
        std   = close.rolling(n).std()
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
    _, _sim_trades, _ = simulate_portfolio(df, upper_bb, lower_bb, 5000.0, STOP_PCT)
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
                _tp_at = upper_full.iloc[_fi]
                _i1, _i2, _i3, _i4, _i5 = st.columns(5)
                _i1.metric("Entry Price",           f"${_sig['price']:.2f}")
                _i2.metric("Stop Loss",             f"${_sig['price'] * (1 - STOP_PCT):.2f}")
                _i3.metric("Take Profit (BB Upper)", f"${_tp_at:.2f}" if not pd.isna(_tp_at) else "—")
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

    final_balance, trades, eq_series = simulate_portfolio(df, upper_bb, lower_bb, initial_investment, STOP_PCT)

    if not trades:
        st.info("No completed trades in the selected date range.")
    else:
        total_return_pct = (final_balance / initial_investment - 1) * 100
        closed = [t for t in trades if t["Exit Reason"] != "Still Open 🟡"]
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
    reports = sorted(
        [r for r in REPORTS_DIR.glob("backtest_*.html") if "keltner" not in r.name],
        reverse=True
    )

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

        st.markdown("## 📊 Bollinger Band Strategy")
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

        st.markdown("## ⚡ Keltner Channel Strategy")
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
