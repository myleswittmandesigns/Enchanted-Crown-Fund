"""
Backtester page — runs the headless backtester and renders the HTML report inline.
"""

import subprocess
import sys
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from datetime import date

REPO_DIR    = Path(__file__).parent.parent
REPORTS_DIR = REPO_DIR / "reports"
BACKTESTER  = REPO_DIR / "backtester.py"

st.set_page_config(page_title="Backtester — Enchanted Crown Fund", layout="wide")
st.title("⚙️ Backtester")
st.caption("Grid-searches N × K combinations and validates via walk-forward analysis.")

# ── Run button ────────────────────────────────────────────────────────────────
run_col, spacer = st.columns([1, 5])
with run_col:
    run_clicked = st.button("▶ Run Backtest", type="primary", use_container_width=True)

if run_clicked:
    with st.spinner("Running grid search + walk-forward analysis… this takes ~30 seconds"):
        result = subprocess.run(
            [sys.executable, str(BACKTESTER)],
            capture_output=True,
            text=True,
            cwd=str(REPO_DIR),
        )
    if result.returncode != 0:
        st.error("Backtester failed.")
        st.code(result.stderr, language="text")
        st.stop()
    else:
        st.success("Backtest complete.")
        st.code(result.stdout.strip(), language="text")

# ── Load latest report ────────────────────────────────────────────────────────
reports = sorted(REPORTS_DIR.glob("backtest_*.html"), reverse=True)

if not reports:
    st.info("No report found. Click **▶ Run Backtest** to generate one.")
    st.stop()

latest = reports[0]
run_date = latest.stem.replace("backtest_", "")

st.markdown(f"**Showing report:** `{latest.name}`")

if len(reports) > 1:
    names = [r.name for r in reports]
    chosen = st.selectbox("Load a different report:", names, index=0)
    latest = REPORTS_DIR / chosen

# ── Render HTML inline ────────────────────────────────────────────────────────
html_content = latest.read_text(encoding="utf-8")
components.html(html_content, height=2400, scrolling=True)
