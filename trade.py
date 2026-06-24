"""Papirhandel — omsetter AI-signaler til kjøp/salg med posisjonsstyring."""

import os
from db import get_client

MAX_POSITION_PCT    = 0.10  # maks 10% av total porteføljeverdi per aksje
MAX_TOTAL_EXPOSURE  = 0.80  # maks 80% av porteføljen investert samtidig
MIN_CONFIDENCE      = 0.65  # ignorer signaler under 65% konfidens
STOP_LOSS_PCT       = 0.07  # selg automatisk ved 7% tap
MAX_PER_SECTOR      = 2     # maks antall posisjoner per sektor samtidig

# Nordnet kurtasje: 0,05% av handelsverdi, minimum 99 NOK per handel
KURTASJE_PCT = 0.0005
KURTASJE_MIN = 99.0

# Minimum gevinst for at en handel skal være lønnsom etter kurtasje (begge veier)
# Posisjon må stige minst dette før salg gir netto pluss
MIN_PROFIT_AFTER_FEES_PCT = 0.015  # 1,5% netto — dekker kurtasje + litt margin

# VIX-styring: høy global frykt → reduser eksponering
VIX_CAUTION   = 20   # VIX > 20: halvér posisjonsstørrelse
VIX_DEFENSIVE = 25   # VIX > 25: ikke kjøp nye posisjoner
VIX_PANIC     = 30   # VIX > 30: selg alt ned til 30% eksponering

# Sektorkart — brukes til å unngå for høy konsentrasjon
SECTORS: dict[str, str] = {
    # Energi / olje og gass
    "EQNR.OL": "energi", "AKRBP.OL": "energi", "SUBC.OL": "energi",
    "TGS.OL":  "energi", "PGS.OL":   "energi", "BORR.OL": "energi",
    "OKEA.OL": "energi", "ODL.OL":   "energi", "SOFF.OL": "energi",
    "BWO.OL":  "energi", "SDRL.OL":  "energi",
    # Fornybar energi
    "SCATC.OL": "fornybar", "RECSI.OL": "fornybar", "BWE.OL": "fornybar",
    "NHY.OL":   "fornybar",
    # Shipping / frakt
    "HAFNI.OL": "shipping", "BWLPG.OL": "shipping", "MPCC.OL": "shipping",
    "GOGL.OL":  "shipping", "2020.OL":  "shipping", "FLNG.OL": "shipping",
    "COOL.OL":  "shipping", "SMOP.OL":  "shipping",
    # Sjømat / havbruk
    "MOWI.OL": "sjømat", "SALM.OL": "sjømat", "LSG.OL":  "sjømat",
    "AUSS.OL": "sjømat", "NRS.OL":  "sjømat", "GRIEG.OL": "sjømat",
    # Finans
    "DNB.OL": "finans", "STB.OL": "finans", "GJF.OL": "finans",
    "NONG.OL": "finans", "ABG.OL": "finans",
    # Telecom / tech
    "TEL.OL": "tech", "OPERA.OL": "tech", "ATEA.OL": "tech",
    "PEXIP.OL": "tech", "NEXT.OL": "tech", "IDEX.OL": "tech",
    "EMGS.OL":  "tech", "PHO.OL": "tech",
    # Industri / konglomerat
    "ORK.OL": "industri", "AKER.OL": "industri", "KOG.OL":  "industri",
    "NRC.OL": "industri", "NSKOG.OL": "industri", "KIT.OL": "industri",
    "MING.OL": "industri", "BEWI.OL": "industri",
    # Forbruk / tjenester
    "SATS.OL": "forbruk", "XXL.OL": "forbruk",
    # Diverse
    "SCANA.OL": "diverse", "LINK.OL": "diverse", "TOM.OL": "diverse",
    "ODL.OL":   "diverse", "HAVI.OL": "diverse", "HBC.OL": "diverse",
    "BWO.OL":   "diverse", "BORR.OL": "diverse",
}


def latest_price(sb, ticker: str) -> float | None:
    # Prøv intradag-kurs først (ferskest), deretter dagskurs
    row = (
        sb.table("intraday_prices")
        .select("close")
        .eq("ticker", ticker)
        .order("ts", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if row:
        return float(row[0]["close"])
    row = (
        sb.table("prices")
        .select("close")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return float(row[0]["close"]) if row else None


def portfolio_value(sb) -> float:
    cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])
    holdings = sb.table("portfolio").select("ticker, shares, avg_cost").execute().data
    stock_value = 0.0
    for h in holdings:
        price = latest_price(sb, h["ticker"])
        if price is None:
            price = float(h["avg_cost"])
        stock_value += float(h["shares"]) * price
    return cash + stock_value


def get_holding(sb, ticker: str) -> dict | None:
    rows = sb.table("portfolio").select("*").eq("ticker", ticker).execute().data
    return rows[0] if rows else None


def kurtasje(verdi: float) -> float:
    """Beregner Nordnet-kurtasje for en handel av gitt verdi."""
    return max(KURTASJE_MIN, verdi * KURTASJE_PCT)


def get_vix(sb) -> float:
    rows = sb.table("macro").select("vix").order("date", desc=True).limit(1).execute().data
    return float(rows[0]["vix"]) if rows and rows[0].get("vix") else 0.0


def sector_count(sb, ticker: str) -> tuple[str, int]:
    """Returnerer sektoren til ticker og antall posisjoner vi allerede har i samme sektor."""
    sektor = SECTORS.get(ticker, "ukjent")
    if sektor == "ukjent":
        return sektor, 0
    holdings = sb.table("portfolio").select("ticker").execute().data
    count = sum(1 for h in holdings if SECTORS.get(h["ticker"], "") == sektor)
    return sektor, count


def buy(sb, ticker: str, price: float, reason: str, total_value: float):
    cash_row = sb.table("cash").select("amount").eq("id", 1).single().execute().data
    cash = float(cash_row["amount"])

    # Ikke kjøp hvis total eksponering allerede er høy
    invested = total_value - cash
    if invested / total_value >= MAX_TOTAL_EXPOSURE:
        print(f"  {ticker}: BUY avvist — maks eksponering nådd ({invested/total_value:.0%})")
        return

    # Ikke kjøp hvis sektoren allerede er fullt utnyttet
    sektor, antall = sector_count(sb, ticker)
    if antall >= MAX_PER_SECTOR:
        print(f"  {ticker}: BUY avvist — allerede {antall} posisjoner i '{sektor}' (maks {MAX_PER_SECTOR})")
        return

    # VIX-justert posisjonsstørrelse
    vix = get_vix(sb)
    if vix >= VIX_DEFENSIVE:
        print(f"  {ticker}: BUY avvist — VIX={vix:.0f} over forsiktighetsnivå ({VIX_DEFENSIVE})")
        return
    vix_factor = 0.5 if vix >= VIX_CAUTION else 1.0

    max_spend = total_value * MAX_POSITION_PCT * vix_factor
    spend = min(max_spend, cash * 0.95)

    if spend < 100:
        print(f"  {ticker}: ikke nok kontanter (har {cash:.0f} NOK)")
        return

    fee = kurtasje(spend)
    shares = (spend - fee) / price
    cost_total = spend  # inkl. kurtasje

    holding = get_holding(sb, ticker)
    if holding:
        old_shares = float(holding["shares"])
        old_avg = float(holding["avg_cost"])
        new_shares = old_shares + shares
        # Snittinngangskurs inkl. kjøpskurtasje
        new_avg = (old_shares * old_avg + shares * price + fee) / new_shares
        sb.table("portfolio").update({"shares": new_shares, "avg_cost": new_avg}).eq("ticker", ticker).execute()
    else:
        # avg_cost inkluderer kurtasje slik at break-even beregnes riktig
        avg_cost_inkl_fee = (shares * price + fee) / shares
        sb.table("portfolio").upsert({"ticker": ticker, "shares": shares, "avg_cost": avg_cost_inkl_fee}).execute()

    sb.table("cash").update({"amount": cash - cost_total}).eq("id", 1).execute()
    sb.table("transactions").insert({
        "ticker": ticker, "action": "BUY",
        "shares": shares, "price": price, "reason": reason,
    }).execute()
    print(f"  KJØPt {shares:.2f} aksjer i {ticker} @ {price:.2f} NOK | kurtasje: {fee:.0f} NOK | totalt: {cost_total:.0f} NOK")


def sell(sb, ticker: str, price: float, reason: str, force: bool = False):
    holding = get_holding(sb, ticker)
    if not holding or float(holding["shares"]) <= 0:
        print(f"  {ticker}: ingen posisjon å selge")
        return

    shares   = float(holding["shares"])
    avg_cost = float(holding["avg_cost"])  # inkl. kjøpskurtasje
    gross    = shares * price
    fee      = kurtasje(gross)
    net      = gross - fee

    # Ikke selg med tap pga kurtasje alene (med mindre det er stop-loss/force)
    if not force:
        net_pnl_pct = (net / (shares * avg_cost) - 1) * 100
        if net_pnl_pct < 0 and net_pnl_pct > -(STOP_LOSS_PCT * 100):
            # Sjekk om vi faktisk tjener etter alle kostnader
            breakeven_price = avg_cost * (1 + MIN_PROFIT_AFTER_FEES_PCT)
            if price < breakeven_price:
                print(f"  {ticker}: SELL avvist — kurs {price:.2f} under break-even {breakeven_price:.2f} (kurtasje spiser gevinsten)")
                return

    cash_row = sb.table("cash").select("amount").eq("id", 1).single().execute().data
    new_cash = float(cash_row["amount"]) + net

    sb.table("portfolio").delete().eq("ticker", ticker).execute()
    sb.table("cash").update({"amount": new_cash}).eq("id", 1).execute()
    sb.table("transactions").insert({
        "ticker": ticker, "action": "SELL",
        "shares": shares, "price": price, "reason": reason,
    }).execute()

    pnl     = net - shares * avg_cost
    pnl_pct = pnl / (shares * avg_cost) * 100
    sign    = "+" if pnl >= 0 else ""
    print(f"  SOLGT {shares:.2f} aksjer i {ticker} @ {price:.2f} NOK | kurtasje: {fee:.0f} NOK | P&L: {sign}{pnl:.0f} NOK ({sign}{pnl_pct:.1f}%)")


def check_stop_losses(sb, total_value: float):
    holdings = sb.table("portfolio").select("*").execute().data
    for h in holdings:
        price = latest_price(sb, h["ticker"])
        if not price:
            continue
        avg = float(h["avg_cost"])
        loss_pct = (avg - price) / avg
        if loss_pct >= STOP_LOSS_PCT:
            print(f"  STOP-LOSS utløst for {h['ticker']} (kjøpt @ {avg:.2f}, nå {price:.2f}, -{loss_pct*100:.1f}%)")
            sell(sb, h["ticker"], price, f"Stop-loss utløst ved -{loss_pct*100:.1f}%", force=True)


def run():
    sb = get_client()
    total_value = portfolio_value(sb)
    vix = get_vix(sb)
    print(f"Porteføljeverdi: {total_value:,.0f} NOK | VIX: {vix:.1f}\n")

    # VIX-panikk: reduser eksponering til 30%
    if vix >= VIX_PANIC:
        print(f"⚠ VIX={vix:.0f} — PANIKKMODUS: selger ned til 30% eksponering")
        cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])
        invested = total_value - cash
        target_invested = total_value * 0.30
        if invested > target_invested:
            holdings = sb.table("portfolio").select("*").execute().data
            for h in holdings:
                price = latest_price(sb, h["ticker"])
                if price:
                    sell(sb, h["ticker"], price, f"VIX={vix:.0f} — panikksalg", force=True)

    # Sjekk stop-loss før vi behandler signaler
    print("--- Stop-loss sjekk ---")
    check_stop_losses(sb, total_value)

    # Hent siste signal per ticker
    all_signals = sb.table("signals").select("*").order("ts", desc=True).execute().data
    seen = set()
    signals = []
    for s in all_signals:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            signals.append(s)

    print("\n--- Behandler signaler ---")
    for s in signals:
        ticker     = s["ticker"]
        signal     = s["signal"]
        confidence = float(s["confidence"])
        reasoning  = s["reasoning"]

        if confidence < MIN_CONFIDENCE:
            print(f"  {ticker}: {signal} ignorert (konfidens {confidence:.0%} < {MIN_CONFIDENCE:.0%})")
            continue

        price = latest_price(sb, ticker)
        if not price:
            print(f"  {ticker}: ingen kurs — hopper over")
            continue

        holding = get_holding(sb, ticker)

        if signal == "BUY" and not holding:
            buy(sb, ticker, price, reasoning, total_value)
        elif signal == "SELL" and holding:
            sell(sb, ticker, price, reasoning, force=False)
        else:
            status = "allerede eid" if (signal == "BUY" and holding) else "ingen posisjon"
            print(f"  {ticker}: {signal} — ingen handling ({status})")

    # Oppdatert oversikt
    new_value = portfolio_value(sb)
    cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])
    print(f"\nKontanter: {cash:,.0f} NOK | Total verdi: {new_value:,.0f} NOK")


if __name__ == "__main__":
    run()
