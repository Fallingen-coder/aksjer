"""
Overvåker corporate actions for aksjer vi eier:
1. Utbytte-varsel  — ikke kjøp innen 3 dager før ex-dato
2. Emisjons-detektor — søk nyheter for emisjon/fortrinnsrett-nøkkelord
3. Splitt-justering — juster snittkost automatisk ved aksjesplitt

Kjøres som del av intradag-workflow.
"""

import yfinance as yf
from datetime import date, timedelta
from db import get_client

EMISJON_KEYWORDS = [
    "emisjon", "fortrinnsrett", "tegningsrett", "rettet emisjon",
    "reparasjonsemisjon", "kapitalforhøyelse", "private placement",
    "rights issue", "share issue", "new shares",
]


def check_dividend(ticker: str) -> dict | None:
    """Returnerer utbytte-info hvis ex-dato er innen 7 dager."""
    try:
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if not cal or "Ex-Dividend Date" not in cal:
            return None
        ex_date = cal["Ex-Dividend Date"]
        if ex_date is None:
            return None
        days = (ex_date - date.today()).days
        if -1 <= days <= 7:
            divs = t.dividends
            if divs.empty:
                return None
            amount = float(divs.iloc[-1])
            return {"ticker": ticker, "ex_date": str(ex_date), "days": days, "amount": amount}
    except Exception:
        pass
    return None


def check_split(sb, ticker: str) -> bool:
    """
    Sjekker om det har vært en aksjesplitt siden siste kjøp.
    Justerer snittkost og antall aksjer i porteføljen om nødvendig.
    """
    try:
        holding = sb.table("portfolio").select("*").eq("ticker", ticker).execute().data
        if not holding:
            return False
        h = holding[0]

        splits = yf.Ticker(ticker).splits
        if splits.empty:
            return False

        # Finn siste transaksjon for denne tickeren
        txns = (
            sb.table("transactions")
            .select("ts")
            .eq("ticker", ticker)
            .eq("action", "BUY")
            .order("ts", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if not txns:
            return False

        last_buy_date = txns[0]["ts"][:10]

        # Finn splitter som har skjedd ETTER siste kjøp
        recent_splits = splits[splits.index.strftime("%Y-%m-%d") > last_buy_date]
        if recent_splits.empty:
            return False

        # Beregn total splitt-faktor
        factor = 1.0
        for ratio in recent_splits:
            factor *= float(ratio)

        if abs(factor - 1.0) < 0.001:
            return False

        old_shares   = float(h["shares"])
        old_avg_cost = float(h["avg_cost"])
        new_shares   = old_shares * factor
        new_avg_cost = old_avg_cost / factor

        sb.table("portfolio").update({
            "shares":   new_shares,
            "avg_cost": new_avg_cost,
        }).eq("ticker", ticker).execute()

        print(f"  SPLITT {ticker}: faktor {factor:.4f} — "
              f"{old_shares:.2f} → {new_shares:.2f} aksjer | "
              f"snittkost {old_avg_cost:.2f} → {new_avg_cost:.2f} NOK")
        return True

    except Exception as e:
        print(f"  {ticker}: splitt-sjekk feil — {e}")
        return False


def check_emisjon_in_news(sb, ticker: str) -> str | None:
    """Sjekker om det er emisjons-relevante nyheter for tickeren."""
    try:
        news = (
            sb.table("news")
            .select("title, summary")
            .eq("ticker", ticker)
            .order("fetched_at", desc=True)
            .limit(10)
            .execute()
            .data
        )
        hits = []
        for n in news:
            tekst = (n.get("title", "") + " " + n.get("summary", "")).lower()
            kw = next((k for k in EMISJON_KEYWORDS if k in tekst), None)
            if kw:
                hits.append(n["title"])
        if hits:
            return f"EMISJON/FORTRINNSRETT detektert: {hits[0]}"
    except Exception:
        pass
    return None


def run():
    sb = get_client()

    # Hent alle tickers vi eier
    holdings = sb.table("portfolio").select("ticker").execute().data
    if not holdings:
        print("Ingen posisjoner å sjekke.")
        return

    tickers = [h["ticker"] for h in holdings]
    print(f"Sjekker corporate actions for {len(tickers)} posisjoner: {', '.join(tickers)}\n")

    alerts = []

    for ticker in tickers:
        # 1. Splitt-justering
        check_split(sb, ticker)

        # 2. Utbytte-varsel
        div = check_dividend(ticker)
        if div:
            if div["days"] >= 0:
                msg = (f"⚠ UTBYTTE {ticker}: ex-dato {div['ex_date']} "
                       f"(om {div['days']} dager) — {div['amount']:.2f} NOK/aksje. "
                       f"Kursen vil trolig falle tilsvarende på ex-dato.")
            else:
                msg = (f"ℹ UTBYTTE {ticker}: ex-dato var {div['ex_date']} "
                       f"— {div['amount']:.2f} NOK/aksje utbetalt.")
            print(f"  {msg}")
            alerts.append({"ticker": ticker, "type": "utbytte", "message": msg})

        # 3. Emisjons-detektor
        emisjon = check_emisjon_in_news(sb, ticker)
        if emisjon:
            msg = f"⚠ {ticker}: {emisjon}"
            print(f"  {msg}")
            alerts.append({"ticker": ticker, "type": "emisjon", "message": msg})

    if not alerts:
        print("  Ingen varsler — alt normalt.")

    # Lagre varsler i Supabase for dashboard-visning
    if alerts:
        for a in alerts:
            sb.table("corporate_action_alerts").upsert({
                "ticker":  a["ticker"],
                "type":    a["type"],
                "message": a["message"],
                "date":    str(date.today()),
            }).execute()

    print(f"\n✓ Corporate actions sjekket for {len(tickers)} tickers.")


if __name__ == "__main__":
    run()
