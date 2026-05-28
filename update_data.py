#!/usr/bin/env python3
"""
Update ticker High/Low CSVs with the latest data from Yahoo Finance.
Reads each CSV, finds the last date, fetches new rows, appends, and commits to git.
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_DIR, "data")
TICKERS = ["ASMB", "GSIT"]


def git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", REPO_DIR] + args,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def update_ticker(ticker: str) -> int:
    path = os.path.join(DATA_DIR, f"{ticker}_daily_high_low.csv")

    existing = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    last_date = existing.index.max()
    fetch_from = last_date + timedelta(days=1)
    today = datetime.today()

    if fetch_from.date() >= today.date():
        print(f"  {ticker}: already up to date (last row: {last_date.date()})")
        return 0

    print(f"  {ticker}: fetching {fetch_from.date()} → {today.date()} ...")
    df = yf.download(
        ticker,
        start=fetch_from.strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        print(f"  {ticker}: no new data returned")
        return 0

    df.columns = [col[0] for col in df.columns]
    new_rows = df[["High", "Low"]].copy()
    new_rows.index.name = "Date"

    # Drop any overlap just in case
    new_rows = new_rows[new_rows.index > last_date]
    if new_rows.empty:
        print(f"  {ticker}: no new rows after dedup")
        return 0

    updated = pd.concat([existing, new_rows])
    updated.to_csv(path)

    added = len(new_rows)
    print(f"  {ticker}: appended {added} row(s), now through {new_rows.index.max().date()}")
    return added


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting update run")

    # Pull latest before updating
    git(["pull", "--ff-only"])

    total_added = 0
    updated_tickers = []

    for ticker in TICKERS:
        added = update_ticker(ticker)
        if added > 0:
            total_added += added
            updated_tickers.append(ticker)

    if not updated_tickers:
        print("Nothing to commit.")
        return

    for ticker in updated_tickers:
        git(["add", f"data/{ticker}_daily_high_low.csv"])

    today_str = datetime.today().strftime("%Y-%m-%d")
    msg = f"Update High/Low data through {today_str} ({', '.join(updated_tickers)})"
    git(["commit", "-m", msg])
    git(["push", "origin", "main"])

    print(f"Pushed: {total_added} new row(s) across {len(updated_tickers)} ticker(s).")


if __name__ == "__main__":
    main()
