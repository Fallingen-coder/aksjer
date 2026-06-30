"""Viser P&L for åpne posisjoner og total porteføljestatus."""

from db import get_client


def run():
    sb = get_client()

    # Hent kun åpne posisjoner fra portfolio-tabellen
    portfolio = (
        sb.table("portfolio")
        .select("ticker, shares, avg_cost")
        .gt("shares", 0)
        .order("ticker")
        .execute()
        .data
    )

    if not portfolio:
        print("Ingen åpne posisjoner.")
        return

    results = []
    pending = []

    for pos in portfolio:
        ticker    = pos["ticker"]
        shares    = float(pos["shares"])
        avg_cost  = float(pos["avg_cost"])

        # Hent siste intradag-kurs
        latest_row = (
            sb.table("intraday_prices")
            .select("close")
            .eq("ticker", ticker)
            .order("ts", desc=True)
            .limit(1)
            .execute()
            .data
        )

        if not latest_row:
            # Prøv dagskurs
            latest_row = (
                sb.table("prices")
                .select("close")
                .eq("ticker", ticker)
                .order("date", desc=True)
                .limit(1)
                .execute()
                .data
            )

        if not latest_row:
            pending.append(ticker)
            continue

        latest_price = float(latest_row[0]["close"])
        pnl_pct      = (latest_price / avg_cost - 1) * 100
        pnl_nok      = (latest_price - avg_cost) * shares

        results.append({
            "ticker":       ticker,
            "shares":       shares,
            "avg_cost":     avg_cost,
            "latest_price": latest_price,
            "pnl_pct":      pnl_pct,
            "pnl_nok":      pnl_nok,
            "win":          latest_price > avg_cost,
        })

    # Hent kontanter og totalverdi
    cash_row = sb.table("cash").select("amount").eq("id", 1).single().execute().data
    cash = float(cash_row["amount"]) if cash_row else 0.0
    invested = sum(r["latest_price"] * r["shares"] for r in results)
    total    = cash + invested

    print(f"{'Ticker':<12} {'Snitt kjøp':>10} {'Nå':>10} {'P&L %':>8} {'P&L NOK':>10}  Status")
    print("-" * 70)
    for r in results:
        sign = "+" if r["pnl_pct"] >= 0 else ""
        icon = "✓" if r["win"] else "✗"
        print(
            f"  {r['ticker']:<10} {r['avg_cost']:>10.2f} {r['latest_price']:>10.2f} "
            f"{sign}{r['pnl_pct']:>6.1f}% {sign}{r['pnl_nok']:>9.0f}  {icon}"
        )

    if pending:
        print(f"\n  Venter på kursdata: {', '.join(pending)}")

    if results:
        wins  = sum(1 for r in results if r["win"])
        total_count = len(results)
        print(f"\n  Åpne posisjoner: {total_count} | I pluss: {wins} | I minus: {total_count - wins}")

    print(f"\n  Kontanter: {cash:,.0f} NOK | Investert: {invested:,.0f} NOK | Total: {total:,.0f} NOK")


if __name__ == "__main__":
    run()
