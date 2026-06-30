"""
Oppdaterer aktive Oslo Børs-tickers i Supabase.
Tester en bred seed-liste mot Yahoo Finance og beholder
tickers med snittvolum over terskelen.
Kjøres ukentlig via GitHub Actions (mandag kl 08:00).
"""

import yfinance as yf
import threading
import time
from db import get_client

MIN_AVG_VOLUME = 50_000   # laveste akseptable snittvolum per dag

# Tickers som er delistet eller utilgjengelige — aldri legg til disse igjen
BLACKLIST = {"RECSI.OL"}

# Bred seed-liste — kjente Oslo Børs-tickers
SEED = [
    # Energi / olje og gass
    "EQNR.OL","AKRBP.OL","SUBC.OL","TGS.OL","PGS.OL","SDRL.OL",
    "BORR.OL","FLNG.OL","COOL.OL","ODL.OL","SCATC.OL","BWE.OL",
    "OKEA.OL","SOFF.OL","BWO.OL","DOF.OL","PANORO.OL","ELKEM.OL",
    # Finans
    "DNB.OL","STB.OL","GJF.OL","NONG.OL","ABG.OL","SVEG.OL",
    "SPOL.OL","SRBANK.OL","MEDI.OL","PROTCT.OL",
    # Telecom / Tech
    "TEL.OL","OPERA.OL","ATEA.OL","BOUVET.OL","NEXT.OL","PHO.OL",
    "PEXIP.OL","IDEX.OL","EMGS.OL","LINK.OL","ITERA.OL","CRAYN.OL",
    "NORBIT.OL","NORDIC.OL",
    # Sjømat / Havbruk
    "MOWI.OL","SALM.OL","LSG.OL","AUSS.OL","NRS.OL","GRIEG.OL",
    "AKVA.OL","BEWI.OL","SMOP.OL",
    # Shipping / Frakt
    "HAFNI.OL","BWLPG.OL","MPCC.OL","GOGL.OL","2020.OL","HAVI.OL",
    "BELSHIPS.OL","FRONTLINE.OL","STOLT.OL","AMSC.OL","HBC.OL",
    "KMCP.OL","FOE.OL",
    # Industri / Konglomerat
    "ORK.OL","AKER.OL","KOG.OL","NRC.OL","NSKOG.OL","BWO.OL",
    "KIT.OL","MING.OL","TOM.OL","SCANA.OL","HYARD.OL","AFG.OL",
    # Gjødsel / Kjemi / Materialer
    "YAR.OL","NHY.OL","REC.OL",
    # Eiendom
    "ENTRA.OL","OLT.OL","SELF.OL",
    # Forbruk / Tjenester
    "SATS.OL","XXL.OL","KAHOT.OL","KVAER.OL",
    # Diverse
    "THIN.OL","WSTEP.OL","VARPE.OL","MULTI.OL","BELCO.OL",
]

# Dedupliser og fjern svartelistede
SEED = sorted(set(SEED) - BLACKLIST)

_semaphore = threading.Semaphore(3)


def _fetch_ticker(ticker: str) -> dict | None:
    """Henter 20-dagers historikk via Ticker.history() med retry ved 401."""
    for attempt in range(4):
        try:
            with _semaphore:
                df = yf.Ticker(ticker).history(period="20d", auto_adjust=True)
            if df is not None and not df.empty:
                return df
            time.sleep(1 + attempt)
        except Exception as e:
            err = str(e)
            if "401" in err or "Unauthorized" in err or "crumb" in err.lower():
                time.sleep(3 * (attempt + 1))
                continue
            return None
    return None


def discover():
    sb = get_client()
    print(f"Tester {len(SEED)} seed-tickers mot Yahoo Finance...\n")

    valid = []
    invalid = []

    for ticker in SEED:
        df = _fetch_ticker(ticker)
        if df is None or df.empty:
            invalid.append(ticker)
            print(f"  ✗ {ticker:<15} ingen data")
            continue

        avg_vol = float(df["Volume"].mean())
        close   = float(df["Close"].iloc[-1])

        if avg_vol >= MIN_AVG_VOLUME:
            valid.append({
                "ticker":     ticker,
                "avg_volume": int(avg_vol),
                "last_close": round(close, 2),
            })
            print(f"  ✓ {ticker:<15} kurs={close:>8.2f} NOK  vol={avg_vol:>12,.0f}")
        else:
            invalid.append(ticker)
            print(f"  ✗ {ticker:<15} for lavt volum ({avg_vol:,.0f})")

    print(f"\n{len(valid)} godkjente tickers, {len(invalid)} forkastet.")

    # Erstatt hele listen i Supabase
    sb.table("active_tickers").delete().neq("ticker", "").execute()
    if valid:
        sb.table("active_tickers").insert(valid).execute()

    print(f"✓ Supabase oppdatert med {len(valid)} aktive tickers.")
    return [v["ticker"] for v in valid]


if __name__ == "__main__":
    discover()
