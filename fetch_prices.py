"""Henter kursdata fra Yahoo Finance og lagrer i databasen."""

import yfinance as yf
from datetime import date
from db import get_conn, init_db
from tickers import TICKERS


def fetch_and_store(period: str = "3mo"):
    init_db()
    with get_conn() as conn:
        for ticker in TICKERS:
            try:
                df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
                if df.empty:
                    print(f"  {ticker}: ingen data")
                    continue
                rows = []
                for dt, row in df.iterrows():
                    rows.append((
                        ticker,
                        str(dt.date()),
                        float(row["Open"].iloc[0]) if hasattr(row["Open"], "iloc") else float(row["Open"]),
                        float(row["High"].iloc[0]) if hasattr(row["High"], "iloc") else float(row["High"]),
                        float(row["Low"].iloc[0])  if hasattr(row["Low"],  "iloc") else float(row["Low"]),
                        float(row["Close"].iloc[0]) if hasattr(row["Close"], "iloc") else float(row["Close"]),
                        int(row["Volume"].iloc[0]) if hasattr(row["Volume"], "iloc") else int(row["Volume"]),
                    ))
                conn.executemany("""
                    INSERT OR REPLACE INTO prices (ticker, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, rows)
                latest = rows[-1]
                print(f"  {ticker}: {len(rows)} dager lagret. Siste kurs: {latest[5]:.2f} NOK ({latest[1]})")
            except Exception as e:
                print(f"  {ticker}: FEIL — {e}")


if __name__ == "__main__":
    print("Henter kursdata for Oslo Børs...\n")
    fetch_and_store()
    print("\nFerdig.")
