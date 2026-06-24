"""
Henter makroøkonomiske data og lagrer i Supabase:
- Norges Bank styringsrente (gratis, ingen autentisering)
- Brent-olje (via yfinance: BZ=F)
- OSEBX-indeksen (via yfinance: ^OSEBX)
- USD/NOK og EUR/NOK valutakurs (via yfinance)
- Laksepris-proxy (SalMar-aksjen som proxy)
"""

import yfinance as yf
import requests
from datetime import date
from db import get_client


def fetch_norges_bank_rate() -> float | None:
    """Henter siste styringsrente fra Norges Banks åpne API."""
    try:
        url = "https://data.norges-bank.no/api/data/IR/B.KPRA.SD.?format=sdmx-json&lastNObservations=1&locale=no"
        r = requests.get(url, timeout=10)
        data = r.json()
        # Naviger SDMX-JSON-strukturen
        obs = data["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
        latest = sorted(obs.keys())[-1]
        return float(obs[latest][0])
    except Exception as e:
        print(f"  Styringsrente: feil — {e}")
        return None


def fetch_yfinance(symbol: str, label: str) -> float | None:
    try:
        df = yf.download(symbol, period="2d", auto_adjust=True, progress=False)
        if df.empty:
            return None
        close = df["Close"]
        if close.ndim > 1:
            close = close.iloc[:, 0]
        return float(close.iloc[-1])
    except Exception as e:
        print(f"  {label}: feil — {e}")
        return None


def run():
    sb = get_client()
    today = str(date.today())

    print("Henter makrodata...\n")

    rate   = fetch_norges_bank_rate()
    brent  = fetch_yfinance("BZ=F",     "Brent-olje")
    osebx  = fetch_yfinance("OSEBX.OL", "OSEBX")
    usdnok = fetch_yfinance("USDNOK=X", "USD/NOK")
    eurnok = fetch_yfinance("EURNOK=X", "EUR/NOK")
    vix    = fetch_yfinance("^VIX",     "VIX")

    row = {
        "date":        today,
        "policy_rate": rate,
        "brent_usd":   brent,
        "osebx":       osebx,
        "usd_nok":     usdnok,
        "eur_nok":     eurnok,
        "vix":         vix,
    }

    # Fjern None-verdier
    row = {k: v for k, v in row.items() if v is not None}

    sb.table("macro").upsert(row).execute()

    print(f"  Styringsrente:  {rate}%"          if rate   else "  Styringsrente:  –")
    print(f"  Brent-olje:     {brent:.2f} USD"  if brent  else "  Brent-olje:     –")
    print(f"  OSEBX:          {osebx:.1f}"      if osebx  else "  OSEBX:          –")
    print(f"  USD/NOK:        {usdnok:.4f}"     if usdnok else "  USD/NOK:        –")
    print(f"  EUR/NOK:        {eurnok:.4f}"     if eurnok else "  EUR/NOK:        –")
    print(f"  VIX:            {vix:.1f}"        if vix    else "  VIX:            –")
    print(f"\n✓ Makrodata lagret for {today}.")


if __name__ == "__main__":
    run()
