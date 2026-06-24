"""Analyserer tickers med Claude — bruker intradag-data i børstid, dagskurs ellers."""

import os
import json
from datetime import datetime, timezone
import anthropic
from db import get_client
from tickers import TICKERS

MODEL = "claude-haiku-4-5-20251001"

KNOWLEDGE_FILE = os.path.join(os.path.dirname(__file__), "trading_knowledge.md")

def load_knowledge() -> str:
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

TRADING_KNOWLEDGE = load_knowledge()


def is_market_hours() -> bool:
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    return 7 <= now.hour < 16


def get_intraday(sb, ticker: str, periods: int = 26) -> list[dict]:
    """Siste N 15-min-perioder (ca. 1 børsdag)."""
    return list(reversed(
        sb.table("intraday_prices")
        .select("ts, open, high, low, close, volume")
        .eq("ticker", ticker)
        .order("ts", desc=True)
        .limit(periods)
        .execute()
        .data
    ))


def get_daily(sb, ticker: str, days: int = 10) -> list[dict]:
    return list(reversed(
        sb.table("prices")
        .select("date, open, high, low, close, volume")
        .eq("ticker", ticker)
        .order("date", desc=True)
        .limit(days)
        .execute()
        .data
    ))


def get_macro(sb) -> str:
    rows = sb.table("macro").select("*").order("date", desc=True).limit(1).execute().data
    if not rows:
        return "Ingen makrodata tilgjengelig."
    m = rows[0]
    parts = []
    if m.get("policy_rate"):  parts.append(f"Norges Bank styringsrente: {m['policy_rate']}%")
    if m.get("brent_usd"):    parts.append(f"Brent-olje: {m['brent_usd']:.1f} USD/fat")
    if m.get("osebx"):        parts.append(f"OSEBX-indeks: {m['osebx']:.0f}")
    if m.get("usd_nok"):      parts.append(f"USD/NOK: {m['usd_nok']:.2f}")
    if m.get("eur_nok"):      parts.append(f"EUR/NOK: {m['eur_nok']:.2f}")
    return "\n".join(parts)


def get_news(sb, ticker: str) -> list[dict]:
    return (
        sb.table("news")
        .select("title, summary, source, fetched_at")
        .eq("ticker", ticker)
        .order("fetched_at", desc=True)
        .limit(5)
        .execute()
        .data
    )


def analyse_ticker(client: anthropic.Anthropic, sb, ticker: str, intraday_mode: bool, macro: str = "") -> dict | None:
    news = get_news(sb, ticker)
    news_text = "\n".join(f"- {n['title']} ({n['source']})" for n in news) or "Ingen nyheter."

    if intraday_mode:
        candles = get_intraday(sb, ticker)
        if not candles:
            candles = get_daily(sb, ticker, 3)
            if not candles:
                return None
        latest_price = candles[-1]["close"]
        timeframe = "15-minutters"
        price_lines = "\n".join(
            f"{r.get('ts', r.get('date',''))[:16]}: slutt={r['close']:.2f}, volum={r['volume']}"
            for r in candles
        )
        horizon = "kortsiktig (intradag)"
    else:
        candles = get_daily(sb, ticker, 10)
        if not candles:
            return None
        latest_price = candles[-1]["close"]
        timeframe = "daglig"
        price_lines = "\n".join(
            f"{r['date']}: slutt={r['close']:.2f}, volum={r['volume']}"
            for r in candles
        )
        horizon = "1–3 dager"

    macro_section = f"\nMakroøkonomi:\n{macro}" if macro else ""

    prompt = f"""Du er en aksjeanalytiker. Vurder {ticker} for papirhandel med {horizon} horisont.

Ticker: {ticker}
Siste kurs: {latest_price:.2f} NOK
Tidsramme: {timeframe}
{macro_section}
Kursdata:
{price_lines}

Nyheter:
{news_text}

Svar KUN med JSON:
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0–1.0,
  "reasoning": "maks 2 setninger på norsk"
}}"""

    system = TRADING_KNOWLEDGE if TRADING_KNOWLEDGE else (
        "Du er en profesjonell aksjeanalytiker. Bruk teknisk analyse og nyhetsvurdering "
        "for å gi presise BUY/SELL/HOLD-signaler."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].lstrip("json").strip()

    result = json.loads(text)
    result["ticker"] = ticker
    return result


def run():
    sb = get_client()
    ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    intraday = is_market_hours()
    mode = "INTRADAG (15 min)" if intraday else "DAGLIG"

    macro = get_macro(sb)
    print(f"AI-analyse [{mode}] for {len(TICKERS)} tickers...\n")
    print(f"Makro: {macro.replace(chr(10), ' | ')}\n")

    signals = []
    for ticker in TICKERS:
        try:
            result = analyse_ticker(ai, sb, ticker, intraday, macro)
            if not result:
                print(f"  {ticker}: ingen data")
                continue
            signals.append({
                "ticker":     result["ticker"],
                "signal":     result["signal"],
                "confidence": result["confidence"],
                "reasoning":  result["reasoning"],
            })
            icon = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸️"}.get(result["signal"], "")
            print(f"  {ticker}: {result['signal']} {icon} ({result['confidence']:.0%}) — {result['reasoning'][:80]}")
        except Exception as e:
            print(f"  {ticker}: FEIL — {e}")

    if signals:
        sb.table("signals").insert(signals).execute()
        print(f"\n✓ {len(signals)} signaler lagret.")


if __name__ == "__main__":
    run()
