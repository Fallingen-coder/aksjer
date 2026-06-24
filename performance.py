"""
Beregner treffraten til AI-signalene.
For hvert BUY-signal: sjekk om kursen var høyere 1t, 4t og 1 dag senere.
"""

from db import get_client


def run():
    sb = get_client()

    # Hent alle kjøpstransaksjoner
    buys = (
        sb.table("transactions")
        .select("ticker, price, ts")
        .eq("action", "BUY")
        .order("ts", desc=False)
        .execute()
        .data
    )

    if not buys:
        print("Ingen kjøp å evaluere ennå.")
        return

    results = []
    for buy in buys:
        ticker    = buy["ticker"]
        buy_price = float(buy["price"])
        buy_ts    = buy["ts"]

        # Hent kurser ETTER kjøpet (intradag)
        later = (
            sb.table("intraday_prices")
            .select("ts, close")
            .eq("ticker", ticker)
            .gt("ts", buy_ts)
            .order("ts", desc=False)
            .execute()
            .data
        )

        if not later:
            # Prøv dagskurs
            later = (
                sb.table("prices")
                .select("date as ts, close")
                .eq("ticker", ticker)
                .gt("date", buy_ts[:10])
                .order("date", desc=False)
                .execute()
                .data
            )

        if not later:
            results.append({
                "ticker": ticker, "buy_price": buy_price, "buy_ts": buy_ts,
                "outcome": "ingen data ennå"
            })
            continue

        # Finn pris nærmest 1t, 4t og sluttkurs
        checkpoints = {}
        for candle in later:
            ts_str = candle.get("ts") or candle.get("date", "")
            close  = float(candle["close"])
            checkpoints[ts_str] = close

        prices_after = list(checkpoints.values())
        latest_price = prices_after[-1] if prices_after else None

        if latest_price:
            pnl_pct = (latest_price / buy_price - 1) * 100
            win = latest_price > buy_price
            results.append({
                "ticker":    ticker,
                "buy_ts":    buy_ts[:16],
                "buy_price": buy_price,
                "last_price": latest_price,
                "pnl_pct":   pnl_pct,
                "win":       win,
            })
        else:
            results.append({
                "ticker": ticker, "buy_price": buy_price, "buy_ts": buy_ts,
                "outcome": "ingen data ennå"
            })

    # Oppsummering
    evaluated = [r for r in results if "win" in r]
    pending   = [r for r in results if "win" not in r]

    print(f"{'Ticker':<12} {'Kjøpt':<17} {'Kjøpskurs':>10} {'Nå':>10} {'P&L':>8}  Resultat")
    print("-" * 70)
    for r in evaluated:
        sign = "+" if r["pnl_pct"] >= 0 else ""
        icon = "✓" if r["win"] else "✗"
        print(f"  {r['ticker']:<10} {r['buy_ts']:<17} {r['buy_price']:>10.2f} {r['last_price']:>10.2f} {sign}{r['pnl_pct']:>6.1f}%  {icon}")

    if pending:
        print(f"\n  {len(pending)} kjøp venter på kursdata: {', '.join(r['ticker'] for r in pending)}")

    if evaluated:
        wins     = sum(1 for r in evaluated if r["win"])
        total    = len(evaluated)
        tot_pnl  = sum(r["pnl_pct"] for r in evaluated) / total
        print(f"\n  Treffraten: {wins}/{total} ({wins/total:.0%})  |  Snitt P&L per handel: {'+' if tot_pnl >= 0 else ''}{tot_pnl:.1f}%")

        # Lagre i Supabase
        sb.table("performance_log").upsert([
            {
                "ticker":     r["ticker"],
                "buy_ts":     r["buy_ts"],
                "buy_price":  r["buy_price"],
                "last_price": r["last_price"],
                "pnl_pct":    round(r["pnl_pct"], 2),
                "win":        r["win"],
            }
            for r in evaluated
        ]).execute()


if __name__ == "__main__":
    run()
