#!/usr/bin/env python3
"""
Update ticker OHLC CSVs with the latest data from the Massive API (formerly Polygon.io).
Reads each CSV, finds the last date, fetches new rows, appends, and commits to git.
"""

import os
import subprocess
from datetime import datetime, timedelta

import pandas as pd
from massive import RESTClient

REPO_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(REPO_DIR, "data")
TICKERS   = [
    # Original 11
    "GSIT",
    "RMBS", "CDE", "SMTC", "DY", "SANM",
    "AEIS", "VIAV", "MOD", "TTMI", "STRL",
    # +39 random Russell 2000 picks (IWM holdings 2026-05-18, random.seed(42))
    "ABX", "AFRI", "AGM", "AI", "AIP", "ATYR", "AVNW", "BATRK",
    "BDN", "BRSL", "CNNE", "CRSR", "CSR", "CTEV", "CVLT", "DC",
    "EGHT", "ELMD", "III", "ILPT", "JJSF", "LXFR", "MRVI", "NB",
    "NTB", "NTLA", "NXXT", "PCRX", "PGC", "PRSU", "RELY", "ROCK",
    "SBH", "SD", "SDRL", "SITM", "TCBX", "VABK", "WABC",
]
COLUMNS   = ["Date", "Open", "High", "Low", "Close", "Volume"]


def get_client() -> RESTClient:
    api_key = os.environ.get("MASSIVE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "MASSIVE_API_KEY environment variable is not set. "
            "Add it to your GitHub Actions secrets or local environment."
        )
    return RESTClient(api_key=api_key)


def git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", REPO_DIR] + args,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def update_ticker(client: RESTClient, ticker: str) -> int:
    path = os.path.join(DATA_DIR, f"{ticker}_daily_high_low.csv")

    existing      = pd.read_csv(path, parse_dates=["Date"])
    existing       = existing.sort_values("Date").reset_index(drop=True)
    last_date      = existing["Date"].max()
    fetch_from     = last_date + timedelta(days=1)
    today          = datetime.today()

    if fetch_from.date() >= today.date():
        print(f"  {ticker}: already up to date (last row: {last_date.date()})")
        return 0

    from_str = fetch_from.strftime("%Y-%m-%d")
    to_str   = today.strftime("%Y-%m-%d")
    print(f"  {ticker}: fetching {from_str} → {to_str} ...")

    aggs = []
    for a in client.list_aggs(
        ticker     = ticker,
        multiplier = 1,
        timespan   = "day",
        from_      = from_str,
        to         = to_str,
        limit      = 50000,
        adjusted   = True,
    ):
        aggs.append(a)

    if not aggs:
        print(f"  {ticker}: no new data returned")
        return 0

    rows = []
    for a in aggs:
        # Massive returns timestamp in milliseconds UTC
        date = pd.Timestamp(a.timestamp, unit="ms", tz="UTC").normalize().tz_localize(None)
        rows.append({
            "Date":   date,
            "Open":   a.open,
            "High":   a.high,
            "Low":    a.low,
            "Close":  a.close,
            "Volume": a.volume,
        })

    new_rows = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)

    # Drop any overlap just in case
    new_rows = new_rows[new_rows["Date"] > last_date]
    if new_rows.empty:
        print(f"  {ticker}: no new rows after dedup")
        return 0

    # Preserve only columns that exist in the existing file
    existing_cols = list(existing.columns)
    for col in new_rows.columns:
        if col not in existing_cols:
            existing_cols.append(col)

    updated = pd.concat([existing, new_rows], ignore_index=True)

    # Keep only columns present in existing file (forward-compatible)
    keep_cols = [c for c in existing_cols if c in updated.columns]
    updated   = updated[keep_cols]
    updated.to_csv(path, index=False)

    added = len(new_rows)
    print(f"  {ticker}: appended {added} row(s), now through {new_rows['Date'].max().date()}")
    return added


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Massive API update run")

    client = get_client()

    # Pull latest before updating
    git(["pull", "--ff-only"])

    total_added      = 0
    updated_tickers  = []

    for ticker in TICKERS:
        added = update_ticker(client, ticker)
        if added > 0:
            total_added += added
            updated_tickers.append(ticker)

    if not updated_tickers:
        print("Nothing to commit.")
        return

    for ticker in updated_tickers:
        git(["add", f"data/{ticker}_daily_high_low.csv"])

    today_str = datetime.today().strftime("%Y-%m-%d")
    msg = f"Update OHLC data through {today_str} ({', '.join(updated_tickers)})"
    git(["commit", "-m", msg])
    git(["push", "origin", "main"])

    print(f"Pushed: {total_added} new row(s) across {len(updated_tickers)} ticker(s).")


if __name__ == "__main__":
    main()
