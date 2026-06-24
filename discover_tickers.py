"""
Oppdaterer aktive Oslo Børs-tickers i Supabase.
Tester en bred seed-liste mot Yahoo Finance og beholder
tickers med snittvolum over terskelen.
Kjøres ukentlig via GitHub Actions.
"""

import yfinance as yf
import json
from db import get_client

MIN_AVG_VOLUME = 50_000   # laveste akseptable snittvolum per dag

# Bred seed-liste — alle kjente Oslo Børs-tickers
SEED = [
    # Energi
    "EQNR.OL","AKRBP.OL","SUBC.OL","TGS.OL","PGS.OL","SDRL.OL",
    "BORR.OL","FLNG.OL","COOL.OL","GOGL.OL","HAFNI.OL","HAVI.OL",
    "MHG.OL","ODL.OL","RECSI.OL","SCATC.OL","BWE.OL","OKEA.OL",
    "PANORO.OL","PEXIP.OL",
    # Finans
    "DNB.OL","STB.OL","GJF.OL","SVEG.OL","SPOL.OL","PROTCT.OL",
    "NONG.OL","NORBIT.OL","MEDI.OL","ADVANTM.OL",
    # Telecom / Tech
    "TEL.OL","OPERA.OL","CRAYN.OL","ATEA.OL","BOUVET.OL","INIFY.OL",
    "WSTEP.OL","NEXT.OL","NORDIC.OL","PHO.OL","SATS.OL",
    # Sjømat / Havbruk
    "MOWI.OL","SALM.OL","LSG.OL","BWLPG.OL","AUSS.OL","NRS.OL",
    "GRIEG.OL","AKVA.OL","BEWI.OL","SMOP.OL",
    # Industri / Konglomerat
    "ORK.OL","AKER.OL","KOG.OL","MULTI.OL","NRC.OL","NSKOG.OL",
    "AFG.OL","SCHB.OL","SCHC.OL","BWO.OL","IDEX.OL","MPCC.OL",
    "BELCO.OL","KIT.OL","SRBANK.OL","MING.OL",
    # Gjødsel / Kjemi
    "YAR.OL","REC.OL",
    # Shipping / Transport
    "2020.OL","BELSHIPS.OL","FRONTLINE.OL","STOLT.OL","ODFJELL.OL",
    "FOE.OL","AMSC.OL","HBC.OL","KMCP.OL","HKEX.OL",
    # Eiendom
    "ENTRA.OL","OLT.OL","SOLON.OL","PHO.OL","SELF.OL",
    # Helse
    "BIOTEC.OL","NANO.OL","PCIB.OL","TRVX.OL","ALGETA.OL",
    # Forbruk
    "XXL.OL","AEGA.OL","KAHOT.OL","KVAER.OL","NHY.OL",
    # Diverse
    "SCANA.OL","THIN.OL","LINK.OL","BWG.OL","FJORD.OL",
    "ITERA.OL","VARPE.OL","OTELLO.OL","HYARD.OL","ABG.OL",
    "TOM.OL","BØHLER.OL","EMGS.OL","SOFF.OL","DOF.OL",
]

# Dedupliser
SEED = sorted(set(SEED))


def discover():
    sb = get_client()
    print(f"Tester {len(SEED)} seed-tickers mot Yahoo Finance...\n")

    valid = []
    invalid = []

    for ticker in SEED:
        try:
            df = yf.download(ticker, period="20d", auto_adjust=True, progress=False)
            if df.empty:
                invalid.append(ticker)
                continue
            close_series = df["Close"].iloc[:, 0] if df["Close"].ndim > 1 else df["Close"]
            vol_series   = df["Volume"].iloc[:, 0] if df["Volume"].ndim > 1 else df["Volume"]
            avg_vol = float(vol_series.mean())
            close   = float(close_series.iloc[-1])
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
        except Exception as e:
            invalid.append(ticker)
            print(f"  ✗ {ticker:<15} feil: {e}")

    print(f"\n{len(valid)} godkjente tickers, {len(invalid)} forkastet.")

    # Lagre aktiv liste i Supabase
    sb.table("active_tickers").delete().neq("ticker", "").execute()
    if valid:
        sb.table("active_tickers").insert(valid).execute()

    print(f"✓ Supabase oppdatert med {len(valid)} aktive tickers.")
    return [v["ticker"] for v in valid]


if __name__ == "__main__":
    discover()
