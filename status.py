"""Viser nåværende kurser og porteføljestatus fra Supabase."""

from db import get_client
from rich.table import Table
from rich.console import Console

console = Console()


def show_prices():
    sb = get_client()

    prices = sb.table("prices").select("ticker, date, close").execute().data
    # Siste kurs per ticker
    latest = {}
    prev = {}
    for r in prices:
        t = r["ticker"]
        if t not in latest or r["date"] > latest[t]["date"]:
            prev[t] = latest.get(t)
            latest[t] = r
        elif t not in prev or r["date"] > (prev[t]["date"] if prev[t] else ""):
            if latest[t]["date"] != r["date"]:
                prev[t] = r

    cash = sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"]

    table = Table(title="Oslo Børs — Siste kurser", show_lines=False)
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Kurs (NOK)", justify="right")
    table.add_column("Endring", justify="right")
    table.add_column("Dato")

    for ticker in sorted(latest):
        r = latest[ticker]
        p = prev.get(ticker)
        change = ""
        if p:
            pct = (r["close"] - p["close"]) / p["close"] * 100
            color = "green" if pct >= 0 else "red"
            sign = "+" if pct >= 0 else ""
            change = f"[{color}]{sign}{pct:.2f}%[/{color}]"
        table.add_row(ticker, f"{r['close']:.2f}", change, r["date"])

    console.print(table)
    console.print(f"\n[bold]Tilgjengelig kontanter:[/bold] {float(cash):,.0f} NOK")


if __name__ == "__main__":
    show_prices()
