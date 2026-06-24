"""Henter kursdata fra Yahoo Finance og lagrer i Supabase."""

import yfinance as yf
from db import get_client
from tickers import TICKERS


def fetch_and_store(period: str = "3mo"):
    sb = get_client()
    for ticker in TICKERS:
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df.empty:
                print(f"  {ticker}: ingen data")
                continue
            rows = []
            for dt, row in df.iterrows():
                def val(col):
                    v = row[col]
                    return float(v.iloc[0]) if hasattr(v, "iloc") else float(v)
                rows.append({
                    "ticker": ticker,
                    "date":   str(dt.date()),
                    "open":   val("Open"),
                    "high":   val("High"),
                    "low":    val("Low"),
                    "close":  val("Close"),
                    "volume": int(val("Volume")),
                })
            sb.table("prices").upsert(rows).execute()
            latest = rows[-1]
            print(f"  {ticker}: {len(rows)} dager lagret. Siste kurs: {latest['close']:.2f} NOK ({latest['date']})")
        except Exception as e:
            print(f"  {ticker}: FEIL — {e}")


if __name__ == "__main__":
    print("Henter kursdata for Oslo Børs...\n")
    fetch_and_store()
    print("\nFerdig.")
