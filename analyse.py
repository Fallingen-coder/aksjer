"""Henter siste kursdata og nyheter, sender til Claude for kjøp/selg/hold-signal."""

import os
import json
import anthropic
from db import get_client
from tickers import TICKERS

MODEL = "claude-sonnet-4-6"


def get_price_history(sb, ticker: str, days: int = 30) -> list[dict]:
    rows = (
        sb.table("prices")
        .select("date, open, high, low, close, volume")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(days)
        .execute()
        .data
    )
    return list(reversed(rows))


def get_recent_news(sb, ticker: str, limit: int = 5) -> list[dict]:
    return (
        sb.table("news")
        .select("title, summary, source, fetched_at")
        .eq("ticker", ticker)
        .order("fetched_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def analyse_ticker(client: anthropic.Anthropic, sb, ticker: str) -> dict:
    prices = get_price_history(sb, ticker)
    news = get_recent_news(sb, ticker)

    if not prices:
        print(f"  {ticker}: ingen kursdata — hopper over")
        return None

    latest_price = prices[-1]["close"]

    price_summary = "\n".join(
        f"{r['date']}: åpning={r['open']:.2f}, høy={r['high']:.2f}, lav={r['low']:.2f}, slutt={r['close']:.2f}, volum={r['volume']}"
        for r in prices
    )

    news_summary = (
        "\n".join(f"- {n['title']} ({n['source']}, {n['fetched_at'][:10]})" for n in news)
        if news else "Ingen nyheter tilgjengelig."
    )

    prompt = f"""Du er en aksjeanalytiker som vurderer Oslo Børs-aksjer for en papirportefølje (ingen ekte penger).

Ticker: {ticker}
Siste kurs: {latest_price:.2f} NOK

Kurshistorikk (siste 30 dager):
{price_summary}

Nyheter:
{news_summary}

Gi et signal basert på teknisk analyse og tilgjengelige nyheter.

Svar KUN med et JSON-objekt på dette formatet:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0–1.0,
  "reasoning": "kortfattet begrunnelse på norsk (maks 3 setninger)"
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Trekk ut JSON selv om modellen pakker det i ```json
    if "```" in text:
        text = text.split("```")[1].lstrip("json").strip()

    result = json.loads(text)
    result["ticker"] = ticker
    return result


def run():
    sb = get_client()
    ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("Kjører AI-analyse for alle tickers...\n")
    signals = []
    for ticker in TICKERS:
        result = analyse_ticker(ai, sb, ticker)
        if result:
            signals.append({
                "ticker":     result["ticker"],
                "signal":     result["signal"],
                "confidence": result["confidence"],
                "reasoning":  result["reasoning"],
            })
            icon = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸️"}.get(result["signal"], "")
            print(f"  {ticker}: {result['signal']} {icon} (konfidens: {result['confidence']:.0%})")
            print(f"    → {result['reasoning']}\n")

    if signals:
        sb.table("signals").insert(signals).execute()
        print(f"✓ {len(signals)} signaler lagret i Supabase.")


if __name__ == "__main__":
    run()
