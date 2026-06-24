"""Viser nåværende kurser og porteføljestatus."""

from db import get_conn
from rich.table import Table
from rich.console import Console

console = Console()


def show_prices():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.ticker, p.close, p.date,
                   prev.close AS prev_close
            FROM prices p
            LEFT JOIN prices prev ON prev.ticker = p.ticker
                AND prev.date = (
                    SELECT MAX(date) FROM prices
                    WHERE ticker = p.ticker AND date < p.date
                )
            WHERE p.date = (SELECT MAX(date) FROM prices WHERE ticker = p.ticker)
            ORDER BY p.ticker
        """).fetchall()

        cash = conn.execute("SELECT amount FROM cash WHERE id=1").fetchone()["amount"]

    table = Table(title="Oslo Børs — Siste kurser", show_lines=False)
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Kurs (NOK)", justify="right")
    table.add_column("Endring", justify="right")
    table.add_column("Dato")

    for r in rows:
        change = ""
        if r["prev_close"]:
            pct = (r["close"] - r["prev_close"]) / r["prev_close"] * 100
            color = "green" if pct >= 0 else "red"
            sign = "+" if pct >= 0 else ""
            change = f"[{color}]{sign}{pct:.2f}%[/{color}]"
        table.add_row(r["ticker"], f"{r['close']:.2f}", change, r["date"])

    console.print(table)
    console.print(f"\n[bold]Tilgjengelig kontanter:[/bold] {cash:,.0f} NOK")


if __name__ == "__main__":
    show_prices()
