#!/usr/bin/env python3
"""
send_summary_email.py
---------------------
Sends a daily signal summary email after the backtester completes.
Invoked as the final step of update_data.yml.

Required GitHub Actions secrets:
  RESEND_API_KEY   API key from resend.com
  RESEND_FROM      verified sender address, e.g. alerts@amerified.io
                   (must match a domain verified in your Resend account)

Optional:
  NOTIFY_EMAIL     recipient (defaults to myles@amerified.io)
"""

import os
import base64
import io
import resend
import textwrap
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_DIR    = Path(__file__).parent
DATA_DIR    = REPO_DIR / "data"
REPORTS_DIR = REPO_DIR / "reports"

RECIPIENT   = os.environ.get("NOTIFY_EMAIL", "myles@amerified.io")
SENDER      = os.environ.get("RESEND_FROM", "ECF Alerts <alerts@amerified.io>")

# ── Colors (matching app palette) ─────────────────────────────────────────────
BB_COLORS = [
    {"line": "#1f77b4", "fill": "rgba(31,119,180,0.10)",  "mpl_fill": (31/255, 119/255, 180/255, 0.12)},
    {"line": "#ff7f0e", "fill": "rgba(255,127,14,0.10)",  "mpl_fill": (255/255, 127/255, 14/255, 0.10)},
    {"line": "#2ca02c", "fill": "rgba(44,160,44,0.10)",   "mpl_fill": (44/255, 160/255, 44/255, 0.08)},
]


# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _latest(pattern: str):
    files = sorted(REPORTS_DIR.glob(pattern), reverse=True)
    if not files:
        return None
    try:
        return pd.read_csv(files[0])
    except Exception:
        return None


def load_signal_data():
    sig = _latest("cs_signal_*.csv")
    smr = _latest("cs_summary_*.csv")
    trd = _latest("cs_trades_*.csv")
    return sig, smr, trd


def compute_zscores(n1: int, n2: int, n3: int):
    rows = []
    for p in sorted(DATA_DIR.glob("*_daily_high_low.csv")):
        ticker = p.stem.replace("_daily_high_low", "")
        try:
            df    = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
            close = df["Close"].astype(float)
            if close.isna().all():
                continue
            zs, below = [], []
            valid = True
            for n in [n1, n2, n3]:
                sma = close.rolling(n).mean()
                std = close.rolling(n).std()
                if pd.isna(sma.iloc[-1]) or pd.isna(std.iloc[-1]) or std.iloc[-1] < 1e-9:
                    valid = False; break
                z = float((close.iloc[-1] - sma.iloc[-1]) / std.iloc[-1])
                zs.append(z)
                below.append(z < 0)
            if not valid:
                continue
            rows.append({
                "Rank":        0,
                "Ticker":      ticker,
                "Close":       round(float(close.iloc[-1]), 2),
                f"Z({n1})":    round(zs[0], 3),
                f"Z({n2})":    round(zs[1], 3),
                f"Z({n3})":    round(zs[2], 3),
                "Composite Z": round(float(np.mean(zs)), 3),
                "Consensus":   f"{sum(below)}/3",
            })
        except Exception:
            continue

    df_z = pd.DataFrame(rows).sort_values("Composite Z").reset_index(drop=True)
    df_z["Rank"] = range(1, len(df_z) + 1)
    return df_z


# ─────────────────────────────────────────────────────────────────────────────
# Chart generation
# ─────────────────────────────────────────────────────────────────────────────

def build_bb_chart(ticker: str, n1: int, n2: int, n3: int, k: float) -> str:
    """
    Generates a candlestick chart with 3 Bollinger Band overlays (N1, N2, N3).
    Returns the chart as a base64-encoded PNG string.
    """
    path = DATA_DIR / f"{ticker}_daily_high_low.csv"
    if not path.exists():
        return ""

    df = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    close = df["Close"].astype(float)

    # Compute BBs on full history for accuracy, then slice for display
    display_bars = max(130, n3 * 2)
    df_plot = df.tail(display_bars).reset_index(drop=True)
    close_full = close  # full series for rolling accuracy
    n_full = len(close_full)
    offset = n_full - len(df_plot)

    fig, ax = plt.subplots(figsize=(13, 6.5))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    xs = np.arange(len(df_plot))

    # ── Candlestick bars ──────────────────────────────────────────────────────
    for i, row in df_plot.iterrows():
        o, h, l, c = row["Open"], row["High"], row["Low"], row["Close"]
        up = c >= o
        body_color = "#26a69a" if up else "#ef5350"
        wick_color = "#26a69a" if up else "#ef5350"
        ax.plot([xs[i], xs[i]], [l, h], color=wick_color, linewidth=0.8, zorder=2)
        ax.add_patch(plt.Rectangle(
            (xs[i] - 0.35, min(o, c)),
            0.70,
            abs(c - o) if abs(c - o) > 0 else 0.01,
            color=body_color, zorder=3,
        ))

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    for idx, n in enumerate([n1, n2, n3]):
        sma  = close_full.rolling(n).mean()
        std  = close_full.rolling(n).std()
        upper = sma + k * std
        lower = sma - k * std

        # Slice to display window
        sma_d   = sma.iloc[offset:].values
        upper_d = upper.iloc[offset:].values
        lower_d = lower.iloc[offset:].values

        clr  = BB_COLORS[idx]
        lc   = clr["line"]
        fc   = clr["mpl_fill"]

        ax.plot(xs, sma_d,   color=lc, linewidth=2.0, label=f"SMA({n})",     zorder=4)
        ax.plot(xs, upper_d, color=lc, linewidth=1.0, linestyle="--", alpha=0.85, zorder=4)
        ax.plot(xs, lower_d, color=lc, linewidth=1.0, linestyle="--", alpha=0.85, zorder=4)
        ax.fill_between(xs, lower_d, upper_d, color=fc[:3], alpha=fc[3], zorder=1)

    # ── Entry threshold annotation ────────────────────────────────────────────
    # Mark the current (last) bar with a vertical line
    ax.axvline(x=xs[-1], color="#FFD700", linewidth=1.2, linestyle=":", alpha=0.8, zorder=5)

    # ── Styling ───────────────────────────────────────────────────────────────
    # x-axis: show ~8 date labels
    step  = max(1, len(df_plot) // 8)
    ticks = xs[::step]
    labels = [df_plot["Date"].iloc[i].strftime("%b %d") for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, color="#aaaaaa", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
    ax.tick_params(axis="y", colors="#aaaaaa")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.grid(axis="y", color="#1e1e1e", linewidth=0.5)

    legend = ax.legend(
        loc="upper left", fontsize=9,
        facecolor="#1e1e1e", edgecolor="#333333",
        labelcolor="#dddddd",
    )

    ax.set_title(
        f"{ticker}  —  Bollinger Bands  (N = {n1} / {n2} / {n3},  K = {k})",
        color="#ffffff", fontsize=13, fontweight="bold", pad=14,
    )
    ax.set_xlabel(f"Last {len(df_plot)} trading days", color="#888888", fontsize=9)

    # ── Encode ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.tight_layout(pad=1.5)
    fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# HTML email builder
# ─────────────────────────────────────────────────────────────────────────────

def _td(val, align="center", bold=False, color=None):
    style = f"padding:6px 12px; text-align:{align};"
    if bold:
        style += " font-weight:600;"
    if color:
        style += f" color:{color};"
    return f"<td style='{style}'>{val}</td>"


def build_html_email(sig, smr, df_z, chart_b64: str) -> tuple[str, str]:
    """Returns (subject, html_body)."""

    today = date.today().strftime("%B %d, %Y")
    state   = str(sig.get("State", "FLAT")).upper()
    ticker  = str(sig.get("Ticker", "—"))
    n1 = int(smr.get("N1", 38)); n2 = int(smr.get("N2", 50)); n3 = int(smr.get("N3", 62))
    k  = float(smr.get("K", 1.7))
    entry_threshold = -k

    top      = df_z.iloc[0]
    top_z    = top["Composite Z"]
    top_tick = top["Ticker"]
    n_valid  = len(df_z)

    # Subject
    if state == "HOLDING":
        unreal = float(sig.get("Unrealized %", 0))
        sign   = "+" if unreal >= 0 else ""
        subject = f"[ECF] Holding {ticker} ({sign}{unreal:.1f}%) | Top candidate: {top_tick} (Z={top_z:.3f})"
    elif top_z <= entry_threshold:
        subject = f"[ECF] 🚨 BUY SIGNAL — {top_tick}  (Composite Z = {top_z:.3f})"
    else:
        subject = f"[ECF] Daily Update {today} | No active signal | Top: {top_tick} Z={top_z:.3f}"

    # Signal status banner
    if top_z <= entry_threshold and state != "HOLDING":
        banner_bg    = "#7f1d1d"
        banner_color = "#fca5a5"
        banner_text  = f"🚨 BUY SIGNAL — {top_tick}"
    elif state == "HOLDING":
        unreal = float(sig.get("Unrealized %", 0))
        banner_bg    = "#1e3a5f" if unreal >= 0 else "#3b1f1f"
        banner_color = "#93c5fd" if unreal >= 0 else "#fca5a5"
        entry_date   = sig.get("Entry Date", "—")
        entry_price  = sig.get("Entry $", 0.0)
        last_price   = sig.get("Last $", 0.0)
        sign         = "+" if unreal >= 0 else ""
        banner_text  = (
            f"🟡 Holding {ticker} since {entry_date} &nbsp;·&nbsp; "
            f"${float(entry_price):.2f} → ${float(last_price):.2f} "
            f"({sign}{unreal:.1f}%)"
        )
    else:
        banner_bg    = "#1c1c1c"
        banner_color = "#9ca3af"
        banner_text  = "⚪ No current position"

    # Top 10 ranking table rows
    z_col1, z_col2, z_col3 = f"Z({n1})", f"Z({n2})", f"Z({n3})"
    rank_rows = ""
    for _, row in df_z.head(10).iterrows():
        is_top    = row["Ticker"] == top_tick
        is_held   = row["Ticker"] == ticker and state == "HOLDING"
        row_bg    = "#1a2a1a" if is_top and top_z <= entry_threshold else ("#1a1a2e" if is_held else "transparent")
        rank_rows += f"<tr style='background:{row_bg}'>"
        rank_rows += _td(int(row["Rank"]))
        t_bold     = is_top or is_held
        t_color    = "#fca5a5" if (is_top and top_z <= entry_threshold) else ("#93c5fd" if is_held else "#e5e7eb")
        rank_rows += _td(row["Ticker"], bold=t_bold, color=t_color)
        rank_rows += _td(f"${row['Close']:.2f}")
        rank_rows += _td(f"{row['Composite Z']:.3f}", color="#fca5a5" if row['Composite Z'] < entry_threshold else "#e5e7eb")
        rank_rows += _td(f"{row[z_col1]:.3f}")
        rank_rows += _td(f"{row[z_col2]:.3f}")
        rank_rows += _td(f"{row[z_col3]:.3f}")
        rank_rows += _td(row["Consensus"])
        rank_rows += "</tr>"

    # Chart block
    chart_block = ""
    if chart_b64:
        chart_block = f"""
        <tr><td colspan="2" style="padding:20px 0 8px 0;">
            <p style="color:#9ca3af; font-size:12px; margin:0 0 10px 0;">
                OHLC chart with Bollinger Bands — N = {n1} (blue) / {n2} (orange) / {n3} (green), K = {k}<br>
                Dashed lines = upper/lower bands &nbsp;·&nbsp; Solid lines = SMA &nbsp;·&nbsp;
                Entry threshold = composite Z &lt; {entry_threshold:.2f}
            </p>
            <img src="data:image/png;base64,{chart_b64}"
                 style="max-width:100%; border-radius:8px; border:1px solid #2d2d2d;" />
        </td></tr>
        """

    # Why block for top candidate
    why_parts = []
    if top_z <= entry_threshold:
        why_parts.append(f"composite Z <b>{top_z:.3f}</b> ≤ entry threshold <b>{entry_threshold:.2f}</b>")
    cons = top["Consensus"]
    if cons == "3/3":
        why_parts.append("below mean on <b>all 3 windows</b> (full consensus)")
    elif cons == "2/3":
        why_parts.append("below mean on 2/3 windows")
    why_parts.append(f"ranked <b>#1 of {n_valid}</b> tickers in the universe")
    why_str = " · ".join(why_parts) if why_parts else f"Lowest composite Z in the universe ({top_z:.3f})"

    # Model stats
    cagr     = smr.get("CAGR %", "—")
    rdr      = smr.get("RDR", "—")
    win      = smr.get("Win %", "—")
    maxdd    = smr.get("Max DD %", "—")
    trades   = smr.get("Trades", "—")
    wf       = smr.get("WF Profitable", "—")

    html = textwrap.dedent(f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;background:#0e1117;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#e5e7eb;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:780px;margin:0 auto;padding:20px;">

      <!-- Header -->
      <tr><td style="padding:0 0 20px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a2e;border-radius:12px;padding:20px 24px;">
          <tr>
            <td><span style="font-size:22px;font-weight:700;color:#FFD700;">👑 Enchanted Crown Fund</span></td>
            <td align="right" style="color:#6b7280;font-size:12px;">{today}</td>
          </tr>
          <tr><td colspan="2" style="padding-top:4px;color:#6b7280;font-size:11px;">
            Cross-sectional mean-reversion · N = {n1}/{n2}/{n3} · K = {k} · Universe = {n_valid} tickers
          </td></tr>
        </table>
      </td></tr>

      <!-- Signal banner -->
      <tr><td style="padding:0 0 20px 0;">
        <div style="background:{banner_bg};border-radius:10px;padding:16px 20px;font-size:15px;font-weight:600;color:{banner_color};">
          {banner_text}
        </div>
      </td></tr>

      <!-- Top candidate -->
      <tr><td style="padding:0 0 16px 0;">
        <table width="100%" style="background:#111827;border-radius:10px;padding:16px 20px;" cellpadding="0" cellspacing="0">
          <tr><td colspan="2" style="color:#9ca3af;font-size:11px;padding-bottom:8px;">TODAY'S TOP BUY CANDIDATE</td></tr>
          <tr>
            <td style="font-size:26px;font-weight:700;color:{'#fca5a5' if top_z <= entry_threshold else '#e5e7eb'};">{top_tick}</td>
            <td align="right" style="font-size:13px;color:#9ca3af;">
              Composite Z: <span style="color:{'#fca5a5' if top_z <= entry_threshold else '#e5e7eb'};font-weight:600;">{top_z:.3f}</span><br>
              {z_col1}: {top[z_col1]:.3f} &nbsp;·&nbsp; {z_col2}: {top[z_col2]:.3f} &nbsp;·&nbsp; {z_col3}: {top[z_col3]:.3f}
            </td>
          </tr>
          <tr><td colspan="2" style="padding-top:10px;font-size:12px;color:#9ca3af;border-top:1px solid #1f2937;margin-top:8px;">
            <b style="color:#d1d5db;">Why:</b> {why_str}
          </td></tr>
        </table>
      </td></tr>

      <!-- Chart (only if buy signal or top candidate near threshold) -->
      {f'<!-- chart --><tr><td style="padding:0 0 20px 0;"><table width="100%" style="background:#111827;border-radius:10px;padding:16px 20px;" cellpadding="0" cellspacing="0">{chart_block}</table></td></tr>' if chart_b64 else ''}

      <!-- Universe ranking top 10 -->
      <tr><td style="padding:0 0 20px 0;">
        <table width="100%" style="background:#111827;border-radius:10px;" cellpadding="0" cellspacing="0">
          <tr><td colspan="8" style="padding:14px 16px 8px;color:#9ca3af;font-size:11px;">
            TOP 10 MOST OVERSOLD — FULL UNIVERSE ({n_valid} tickers)
            &nbsp;·&nbsp; Entry threshold: Z ≤ {entry_threshold:.2f}
          </td></tr>
          <tr style="background:#1f2937;font-size:11px;color:#6b7280;">
            <td style="padding:6px 12px;">#</td>
            <td style="padding:6px 12px;">Ticker</td>
            <td style="padding:6px 12px;">Close</td>
            <td style="padding:6px 12px;">Comp Z</td>
            <td style="padding:6px 12px;">{z_col1}</td>
            <td style="padding:6px 12px;">{z_col2}</td>
            <td style="padding:6px 12px;">{z_col3}</td>
            <td style="padding:6px 12px;">Consensus</td>
          </tr>
          {rank_rows}
        </table>
      </td></tr>

      <!-- Model performance -->
      <tr><td style="padding:0 0 20px 0;">
        <table width="100%" style="background:#111827;border-radius:10px;padding:14px 16px;" cellpadding="0" cellspacing="0">
          <tr><td colspan="6" style="color:#9ca3af;font-size:11px;padding-bottom:10px;">BACKTEST MODEL PERFORMANCE (10-year)</td></tr>
          <tr style="font-size:13px;text-align:center;">
            <td style="padding:6px 16px;border-right:1px solid #1f2937;">
              <div style="color:#9ca3af;font-size:10px;">CAGR</div>
              <div style="font-weight:700;color:#34d399;">{cagr}%</div>
            </td>
            <td style="padding:6px 16px;border-right:1px solid #1f2937;">
              <div style="color:#9ca3af;font-size:10px;">RDR</div>
              <div style="font-weight:700;">{rdr}</div>
            </td>
            <td style="padding:6px 16px;border-right:1px solid #1f2937;">
              <div style="color:#9ca3af;font-size:10px;">Win %</div>
              <div style="font-weight:700;">{win}%</div>
            </td>
            <td style="padding:6px 16px;border-right:1px solid #1f2937;">
              <div style="color:#9ca3af;font-size:10px;">Max DD</div>
              <div style="font-weight:700;color:#f87171;">{maxdd}%</div>
            </td>
            <td style="padding:6px 16px;border-right:1px solid #1f2937;">
              <div style="color:#9ca3af;font-size:10px;">Trades</div>
              <div style="font-weight:700;">{trades}</div>
            </td>
            <td style="padding:6px 16px;">
              <div style="color:#9ca3af;font-size:10px;">WF Pass</div>
              <div style="font-weight:700;">{wf}</div>
            </td>
          </tr>
        </table>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:8px 0;text-align:center;color:#374151;font-size:10px;">
        Enchanted Crown Fund · auto-generated by GitHub Actions · data through yesterday's close
      </td></tr>

    </table>
    </body>
    </html>
    """).strip()

    return subject, html


# ─────────────────────────────────────────────────────────────────────────────
# SMTP sender
# ─────────────────────────────────────────────────────────────────────────────

def send_email(subject: str, html_body: str):
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        print("[email] Skipping — RESEND_API_KEY secret not set.")
        return

    resend.api_key = api_key
    resp = resend.Emails.send({
        "from":    SENDER,
        "to":      [RECIPIENT],
        "subject": subject,
        "html":    html_body,
    })
    print(f"[email] Sent → {RECIPIENT}  (id: {resp.get('id', '?')})")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"[email] Building daily summary ...")

    sig_df, smr_df, _ = load_signal_data()
    if sig_df is None or smr_df is None or sig_df.empty or smr_df.empty:
        print("[email] No signal/summary data found — skipping.")
        return

    sig = sig_df.iloc[0]
    smr = smr_df.iloc[0]
    n1, n2, n3 = int(smr["N1"]), int(smr["N2"]), int(smr["N3"])
    k   = float(smr["K"])
    entry_threshold = -k

    print(f"[email] Computing z-scores (N={n1}/{n2}/{n3}) ...")
    df_z = compute_zscores(n1, n2, n3)
    if df_z.empty:
        print("[email] No valid z-scores — skipping.")
        return

    top      = df_z.iloc[0]
    top_z    = top["Composite Z"]
    top_tick = top["Ticker"]
    state    = str(sig.get("State", "FLAT")).upper()

    # Generate chart if: active buy signal OR the top candidate is within 80% of the threshold
    should_chart = top_z <= entry_threshold or top_z <= entry_threshold * 0.7
    chart_b64 = ""
    if should_chart:
        print(f"[email] Generating BB chart for {top_tick} ...")
        try:
            chart_b64 = build_bb_chart(top_tick, n1, n2, n3, k)
            print(f"[email] Chart generated ({len(chart_b64) // 1024} KB)")
        except Exception as e:
            print(f"[email] Chart generation failed: {e}")

    subject, html = build_html_email(sig, smr, df_z, chart_b64)
    print(f"[email] Subject: {subject}")
    send_email(subject, html)


if __name__ == "__main__":
    main()
