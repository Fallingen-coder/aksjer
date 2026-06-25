"""
Henter aktive Oslo Børs-tickers fra Supabase.
Faller tilbake til en hardkodet liste dersom databasen er tom.
"""

import os

FALLBACK = [
    "EQNR.OL","DNB.OL","TEL.OL","MOWI.OL","ORK.OL",
    "YAR.OL","SALM.OL","AKER.OL","STB.OL",
    "NSKOG.OL","MPCC.OL","BORR.OL","ATEA.OL","NRC.OL",
    "WSTEP.OL","PHO.OL","SCANA.OL","BWO.OL","MULTI.OL",
]


def get_tickers() -> list[str]:
    try:
        from db import get_client
        sb = get_client()
        rows = sb.table("active_tickers").select("ticker").order("avg_volume", desc=True).execute().data
        if rows:
            return [r["ticker"] for r in rows]
    except Exception:
        pass
    return FALLBACK


# Eksporter som TICKERS for bakoverkompatibilitet
TICKERS = get_tickers() if os.environ.get("SUPABASE_URL") else FALLBACK
