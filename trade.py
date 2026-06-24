"""Papirhandel — omsetter AI-signaler til kjøp/salg med posisjonsstyring."""

import os
from db import get_client

MAX_POSITION_PCT = 0.20   # maks 20% av total porteføljeverdi per aksje
MIN_CONFIDENCE   = 0.60   # ignorer signaler under 60% konfidens
STOP_LOSS_PCT    = 0.08   # selg automatisk ved 8% tap


def portfolio_value(sb) -> float:
    cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])
    holdings = sb.table("portfolio").select("ticker, shares, avg_cost").execute().data
    prices = {
        r["ticker"]: r["close"]
        for r in sb.table("prices")
        .select("ticker, close")
        .in_("ticker", [h["ticker"] for h in holdings] or ["_"])
        .execute().data
        if r["ticker"] in {
            r2["ticker"]: r2["date"]
            for r2 in sb.table("prices").select("ticker, date").execute().data
        }
    }
    # Hent siste kurs per ticker
    for h in holdings:
        row = (
            sb.table("prices")
            .select("close")
            .eq("ticker", h["ticker"])
            .order("date", desc=True)
            .limit(1)
            .execute()
            .data
        )
        if row:
            prices[h["ticker"]] = row[0]["close"]

    stock_value = sum(
        float(h["shares"]) * prices.get(h["ticker"], float(h["avg_cost"]))
        for h in holdings
    )
    return cash + stock_value


def latest_price(sb, ticker: str) -> float | None:
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


def get_holding(sb, ticker: str) -> dict | None:
    rows = sb.table("portfolio").select("*").eq("ticker", ticker).execute().data
    return rows[0] if rows else None


def buy(sb, ticker: str, price: float, reason: str, total_value: float):
    cash_row = sb.table("cash").select("amount").eq("id", 1).single().execute().data
    cash = float(cash_row["amount"])

    max_spend = total_value * MAX_POSITION_PCT
    spend = min(max_spend, cash * 0.95)  # bruk maks 95% av kontanter

    if spend < 100:
        print(f"  {ticker}: ikke nok kontanter (har {cash:.0f} NOK)")
        return

    shares = spend / price
    cost = shares * price

    holding = get_holding(sb, ticker)
    if holding:
        old_shares = float(holding["shares"])
        old_avg = float(holding["avg_cost"])
        new_shares = old_shares + shares
        new_avg = (old_shares * old_avg + cost) / new_shares
        sb.table("portfolio").update({"shares": new_shares, "avg_cost": new_avg}).eq("ticker", ticker).execute()
    else:
        sb.table("portfolio").upsert({"ticker": ticker, "shares": shares, "avg_cost": price}).execute()

    sb.table("cash").update({"amount": cash - cost}).eq("id", 1).execute()
    sb.table("transactions").insert({
        "ticker": ticker, "action": "BUY",
        "shares": shares, "price": price, "reason": reason,
    }).execute()
    print(f"  KJØPt {shares:.2f} aksjer i {ticker} @ {price:.2f} NOK (kostnad: {cost:.0f} NOK)")


def sell(sb, ticker: str, price: float, reason: str):
    holding = get_holding(sb, ticker)
    if not holding or float(holding["shares"]) <= 0:
        print(f"  {ticker}: ingen posisjon å selge")
        return

    shares = float(holding["shares"])
    proceeds = shares * price
    cash_row = sb.table("cash").select("amount").eq("id", 1).single().execute().data
    new_cash = float(cash_row["amount"]) + proceeds

    sb.table("portfolio").delete().eq("ticker", ticker).execute()
    sb.table("cash").update({"amount": new_cash}).eq("id", 1).execute()
    sb.table("transactions").insert({
        "ticker": ticker, "action": "SELL",
        "shares": shares, "price": price, "reason": reason,
    }).execute()

    pnl = (price - float(holding["avg_cost"])) * shares
    pnl_pct = (price / float(holding["avg_cost"]) - 1) * 100
    sign = "+" if pnl >= 0 else ""
    print(f"  SOLGT {shares:.2f} aksjer i {ticker} @ {price:.2f} NOK | P&L: {sign}{pnl:.0f} NOK ({sign}{pnl_pct:.1f}%)")


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
            sell(sb, h["ticker"], price, f"Stop-loss utløst ved -{loss_pct*100:.1f}%")


def run():
    sb = get_client()
    total_value = portfolio_value(sb)
    print(f"Porteføljeverdi: {total_value:,.0f} NOK\n")

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
            sell(sb, ticker, price, reasoning)
        else:
            status = "allerede eid" if (signal == "BUY" and holding) else "ingen posisjon"
            print(f"  {ticker}: {signal} — ingen handling ({status})")

    # Oppdatert oversikt
    new_value = portfolio_value(sb)
    cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])
    print(f"\nKontanter: {cash:,.0f} NOK | Total verdi: {new_value:,.0f} NOK")


if __name__ == "__main__":
    run()
