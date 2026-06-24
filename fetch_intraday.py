"""Henter 15-minutters intradag-kursdata og lagrer i Supabase."""

import yfinance as yf
from datetime import datetime, timezone, timedelta
from db import get_client
from tickers import TICKERS


def is_market_open() -> bool:
    """Oslo Børs er åpen 09:00–17:30 CET (07:00–15:30 UTC)."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    return 7 <= now.hour < 16


def fetch_and_store():
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    for ticker in TICKERS:
        try:
            df = yf.download(ticker, period="5d", interval="15m", auto_adjust=True, progress=False)
            if df.empty:
                print(f"  {ticker}: ingen intradag-data")
                continue

            rows = []
            for ts, row in df.iterrows():
                def val(col):
                    v = row[col]
                    return float(v.iloc[0]) if hasattr(v, "iloc") else float(v)
                rows.append({
                    "ticker": ticker,
                    "ts":     ts.isoformat(),
                    "open":   val("Open"),
                    "high":   val("High"),
                    "low":    val("Low"),
                    "close":  val("Close"),
                    "volume": int(val("Volume")),
                })

            sb.table("intraday_prices").upsert(rows).execute()

            # Rydd opp gamle rader (> 7 dager)
            sb.table("intraday_prices").delete().eq("ticker", ticker).lt("ts", cutoff).execute()

            latest = rows[-1]
            print(f"  {ticker}: {len(rows)} perioder. Siste: {latest['close']:.2f} NOK")
        except Exception as e:
            print(f"  {ticker}: FEIL — {e}")


if __name__ == "__main__":
    print("Henter 15-min intradag-data...\n")
    fetch_and_store()
    print("\nFerdig.")
