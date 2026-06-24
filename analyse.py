"""Analyserer tickers med Claude — bruker intradag-data i børstid, dagskurs ellers."""

import os
import json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import anthropic
import yfinance as yf
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


def get_dividend_warning(ticker: str) -> str:
    """Returnerer advarsel hvis ex-utbytte-dato er innen 3 dager."""
    try:
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if not cal or "Ex-Dividend Date" not in cal:
            return ""
        ex_date = cal["Ex-Dividend Date"]
        if ex_date is None:
            return ""
        from datetime import date
        days = (ex_date - date.today()).days
        if 0 <= days <= 3:
            divs = t.dividends
            amount = float(divs.iloc[-1]) if not divs.empty else 0
            return (f"⚠ EX-UTBYTTE OM {days} DAGER ({ex_date}) — {amount:.2f} NOK/aksje. "
                    f"Kursen vil falle tilsvarende på ex-dato. Unngå kjøp.")
    except Exception:
        pass
    return ""


def get_earnings_warning(ticker: str) -> str:
    """Returnerer advarsel hvis kvartalstall er innen 3 dager."""
    try:
        cal = yf.Ticker(ticker).calendar
        if not cal or "Earnings Date" not in cal:
            return ""
        dates = cal["Earnings Date"]
        if dates is None or (hasattr(dates, '__len__') and len(dates) == 0):
            return ""
        earnings_date = dates[0] if isinstance(dates, (list, tuple)) else dates
        if not hasattr(earnings_date, 'days') and not hasattr(earnings_date, 'toordinal'):
            return ""
        from datetime import date
        days_away = (earnings_date - date.today()).days
        if 0 <= days_away <= 3:
            return f"⚠ KVARTALSTALL OM {days_away} DAGER ({earnings_date}) — høy usikkerhet, unngå nye kjøp"
        if days_away < 0 and days_away >= -2:
            return f"Kvartalstall nettopp lagt frem ({earnings_date})"
    except Exception:
        pass
    return ""


INSIDER_KEYWORDS = [
    "primærinnside", "innsidekjøp", "innsidehandel", "kjøpte aksjer",
    "solgte aksjer", "insider", "direktør kjøpte", "styreleder kjøpte",
    "ceo kjøpte", "cfo kjøpte",
]

def get_insider_news(news: list[dict]) -> str:
    """Finn innsiderelevante nyheter i nyhetslisten vi allerede har."""
    hits = []
    for n in news:
        tekst = (n.get("title", "") + " " + n.get("summary", "")).lower()
        if any(kw in tekst for kw in INSIDER_KEYWORDS):
            hits.append(n["title"])
    if not hits:
        return ""
    return "Innsidehandler i nyhetene:\n" + "\n".join(f"- {h}" for h in hits)


def get_52week(ticker: str) -> str:
    """Henter 52-ukers høy/lav og beregner hvor i området aksjen er nå."""
    try:
        df = yf.download(ticker, period="52wk", auto_adjust=True, progress=False)
        if df.empty:
            return ""
        close = df["Close"].iloc[:, 0] if df["Close"].ndim > 1 else df["Close"]
        high52 = float(close.max())
        low52  = float(close.min())
        now    = float(close.iloc[-1])
        pct    = (now - low52) / (high52 - low52) * 100 if high52 != low52 else 50
        return (
            f"52-ukers høy: {high52:.2f} NOK | "
            f"52-ukers lav: {low52:.2f} NOK | "
            f"Nåværende posisjon: {pct:.0f}% av årsintervallet"
            f" ({'nær topp — motstand' if pct > 80 else 'nær bunn — støtte' if pct < 20 else 'midt i intervallet'})"
        )
    except Exception:
        return ""


def get_relative_strength(ticker: str) -> str:
    """Sammenligner aksjen mot OSEBX siste 5 dager."""
    try:
        df_stock = yf.download(ticker,   period="5d", auto_adjust=True, progress=False)
        df_index = yf.download("OSEBX.OL", period="5d", auto_adjust=True, progress=False)
        if df_stock.empty or df_index.empty:
            return ""

        s = df_stock["Close"].iloc[:, 0] if df_stock["Close"].ndim > 1 else df_stock["Close"]
        i = df_index["Close"].iloc[:, 0] if df_index["Close"].ndim > 1 else df_index["Close"]

        stock_ret = (float(s.iloc[-1]) / float(s.iloc[0]) - 1) * 100
        index_ret = (float(i.iloc[-1]) / float(i.iloc[0]) - 1) * 100
        rs        = stock_ret - index_ret

        vurdering = (
            "utperformerer markedet" if rs > 1 else
            "underperformerer markedet" if rs < -1 else
            "følger markedet"
        )
        return (
            f"Siste 5 dager: aksjen {stock_ret:+.1f}% vs OSEBX {index_ret:+.1f}% "
            f"→ relativ styrke {rs:+.1f}% ({vurdering})"
        )
    except Exception:
        return ""


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
    news          = get_news(sb, ticker)
    news_text     = "\n".join(f"- {n['title']} ({n['source']})" for n in news) or "Ingen nyheter."
    w52           = get_52week(ticker)
    rs            = get_relative_strength(ticker)
    earnings_warn = get_earnings_warning(ticker)
    dividend_warn = get_dividend_warning(ticker)
    insider_news  = get_insider_news(news)

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

    # Automatiske HOLD-sperrer — for høy usikkerhet
    for sperre, tekst in [
        ("KVARTALSTALL OM",  earnings_warn),
        ("EX-UTBYTTE OM",    dividend_warn),
    ]:
        if tekst and sperre in tekst:
            return {"ticker": ticker, "signal": "HOLD", "confidence": 0.50, "reasoning": tekst}

    kontekst_linjer = []
    if macro:         kontekst_linjer.append(f"Makroøkonomi:\n{macro}")
    if w52:           kontekst_linjer.append(f"52-ukers intervall:\n{w52}")
    if rs:            kontekst_linjer.append(f"Relativ styrke:\n{rs}")
    if insider_news:  kontekst_linjer.append(insider_news)
    if earnings_warn: kontekst_linjer.append(earnings_warn)
    if dividend_warn: kontekst_linjer.append(dividend_warn)
    kontekst = ("\n\n" + "\n\n".join(kontekst_linjer)) if kontekst_linjer else ""

    prompt = f"""Du er en aksjeanalytiker. Vurder {ticker} for papirhandel med {horizon} horisont.

Ticker: {ticker}
Siste kurs: {latest_price:.2f} NOK
Tidsramme: {timeframe}
{kontekst}
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

    try:
        macro = get_macro(sb)
    except Exception as e:
        print(f"⚠ Makrodata utilgjengelig: {e}")
        macro = ""

    print(f"AI-analyse [{mode}] for {len(TICKERS)} tickers...\n")
    if macro:
        print(f"Makro: {macro.replace(chr(10), ' | ')}\n")

    def analyse_one(ticker: str) -> dict | None:
        try:
            return analyse_ticker(ai, sb, ticker, intraday, macro)
        except Exception as e:
            print(f"  {ticker}: FEIL — {e}")
            return None

    signals = []
    # 10 parallelle tråder — balanse mellom fart og API-rate-limits
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(analyse_one, t): t for t in TICKERS}
        for future in as_completed(futures):
            result = future.result()
            if not result:
                print(f"  {futures[future]}: ingen data")
                continue
            signals.append({
                "ticker":     result["ticker"],
                "signal":     result["signal"],
                "confidence": result["confidence"],
                "reasoning":  result["reasoning"],
            })
            icon = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸️"}.get(result["signal"], "")
            print(f"  {result['ticker']}: {result['signal']} {icon} ({result['confidence']:.0%}) — {result['reasoning'][:80]}")

    if signals:
        sb.table("signals").insert(signals).execute()
        print(f"\n✓ {len(signals)} signaler lagret.")


if __name__ == "__main__":
    run()
