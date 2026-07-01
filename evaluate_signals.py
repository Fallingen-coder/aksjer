"""
Selvevaluering av AI-signaler.
Sammenligner historiske BUY/SELL-signaler mot faktisk kursutvikling,
beregner treffrater, og lar Claude destillere lærdommer som skrives
inn i trading_knowledge.md (leses av analyse.py ved hver kjøring).
Kjøres ukentlig via GitHub Actions.
"""

import os
from datetime import datetime, timezone, timedelta
import anthropic
from db import get_client
from trade import SECTORS

MODEL = "claude-haiku-4-5-20251001"
KNOWLEDGE_FILE = os.path.join(os.path.dirname(__file__), "trading_knowledge.md")

MARKER_START = "<!-- AUTO-LÆRDOMMER START -->"
MARKER_END   = "<!-- AUTO-LÆRDOMMER END -->"

MIN_AGE_DAYS  = 2   # signalet må være minst så gammelt at utfallet kan måles
MAX_HORIZON_D = 7   # mål utfall maks 7 dager etter signalet
MIN_CONF      = 0.70


def price_at(sb, ticker: str, after_ts: str) -> float | None:
    """Første intradag-kurs etter tidspunktet (= kursen da signalet ble handlet)."""
    rows = (
        sb.table("intraday_prices")
        .select("close")
        .eq("ticker", ticker)
        .gte("ts", after_ts)
        .order("ts", desc=False)
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return float(rows[0]["close"])
    rows = (
        sb.table("prices")
        .select("close")
        .eq("ticker", ticker)
        .gte("date", after_ts[:10])
        .order("date", desc=False)
        .limit(1)
        .execute()
        .data
    )
    return float(rows[0]["close"]) if rows else None


def outcome_price(sb, ticker: str, signal_ts: str) -> float | None:
    """Siste kurs innenfor horisonten etter signalet."""
    end_ts = (
        datetime.fromisoformat(signal_ts.replace("Z", "+00:00"))
        + timedelta(days=MAX_HORIZON_D)
    ).isoformat()
    rows = (
        sb.table("intraday_prices")
        .select("close")
        .eq("ticker", ticker)
        .gt("ts", signal_ts)
        .lte("ts", end_ts)
        .order("ts", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return float(rows[0]["close"]) if rows else None


def evaluate():
    sb = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=MIN_AGE_DAYS)).isoformat()

    signals = (
        sb.table("signals")
        .select("ticker, signal, confidence, ts")
        .in_("signal", ["BUY", "SELL"])
        .gte("confidence", MIN_CONF)
        .lt("ts", cutoff)
        .order("ts", desc=False)
        .execute()
        .data
    )

    if not signals:
        print("Ingen signaler gamle nok til evaluering ennå.")
        return None

    print(f"Evaluerer {len(signals)} BUY/SELL-signaler (≥{MIN_CONF:.0%}, eldre enn {MIN_AGE_DAYS} dager)...\n")

    results = []
    for s in signals:
        entry = price_at(sb, s["ticker"], s["ts"])
        out   = outcome_price(sb, s["ticker"], s["ts"])
        if entry is None or out is None or entry == 0:
            continue
        ret = (out / entry - 1) * 100
        win = ret > 0 if s["signal"] == "BUY" else ret < 0
        results.append({
            "ticker":     s["ticker"],
            "signal":     s["signal"],
            "confidence": float(s["confidence"]),
            "sector":     SECTORS.get(s["ticker"], "ukjent"),
            "ret_pct":    ret,
            "win":        win,
        })

    if not results:
        print("Ingen signaler med målbart utfall.")
        return None

    def bucket(rs, label):
        if not rs:
            return f"  {label}: ingen data"
        wins = sum(1 for r in rs if r["win"])
        avg  = sum(r["ret_pct"] for r in rs) / len(rs)
        return f"  {label}: {wins}/{len(rs)} treff ({wins/len(rs):.0%}), snittavkastning {avg:+.1f}%"

    lines = [f"Totalt evaluert: {len(results)} signaler\n"]

    lines.append("Per signaltype:")
    for sig in ["BUY", "SELL"]:
        lines.append(bucket([r for r in results if r["signal"] == sig], sig))

    lines.append("\nPer konfidensnivå:")
    for lo, hi in [(0.70, 0.75), (0.75, 0.80), (0.80, 1.01)]:
        rs = [r for r in results if lo <= r["confidence"] < hi]
        lines.append(bucket(rs, f"{lo:.0%}–{min(hi,1.0):.0%}"))

    lines.append("\nPer sektor (BUY-signaler):")
    sectors = sorted({r["sector"] for r in results})
    for sek in sectors:
        rs = [r for r in results if r["sector"] == sek and r["signal"] == "BUY"]
        if rs:
            lines.append(bucket(rs, sek))

    lines.append("\nPer sektor (SELL-signaler):")
    for sek in sectors:
        rs = [r for r in results if r["sector"] == sek and r["signal"] == "SELL"]
        if rs:
            lines.append(bucket(rs, sek))

    # Verste og beste enkeltsignaler
    worst = sorted(results, key=lambda r: r["ret_pct"] if r["signal"] == "BUY" else -r["ret_pct"])[:5]
    lines.append("\nDe 5 dårligste signalene:")
    for r in worst:
        lines.append(f"  {r['ticker']} {r['signal']} ({r['confidence']:.0%}) → {r['ret_pct']:+.1f}%")

    stats_text = "\n".join(lines)
    print(stats_text)
    return stats_text


def generate_lessons(stats_text: str) -> str:
    ai = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = f"""Du evaluerer treffsikkerheten til dine egne aksjesignaler (BUY/SELL på Oslo Børs, swing trading 1–2 uker).

Viktig om lesing av tallene:
- Et BUY-signal "treffer" når kursen steg etterpå — positiv snittavkastning er bra.
- Et SELL-signal "treffer" når kursen falt etterpå — NEGATIV snittavkastning betyr at SELL-signalet var korrekt (vi unngikk tapet). Det er bra.

Statistikk fra faktiske signaler mot faktisk kursutvikling:

{stats_text}

Skriv 3–7 konkrete, handlingsrettede lærdommer på norsk som kan forbedre fremtidige signaler.
Fokuser på mønstre i dataene: hvilke signaltyper/konfidensnivåer/sektorer treffer godt eller dårlig.
Vær ærlig om svakheter. Ikke gjenta statistikken — trekk konklusjoner fra den.
Svar KUN med punktlisten (én linje per lærdom, start hver linje med "- ")."""

    response = ai.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def update_knowledge(lessons: str):
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    section = f"""{MARKER_START}
## 10. Lærdommer fra egen handelshistorikk (auto-generert {today})

Disse lærdommene er destillert fra systemets egne signaler målt mot faktisk
kursutvikling. Vektlegg dem når du setter konfidens på nye signaler.

{lessons}
{MARKER_END}"""

    if MARKER_START in content and MARKER_END in content:
        pre  = content.split(MARKER_START)[0]
        post = content.split(MARKER_END)[1]
        content = pre + section + post
    else:
        content = content.rstrip() + "\n\n---\n\n" + section + "\n"

    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n✓ trading_knowledge.md oppdatert med lærdommer ({today}).")


def run():
    stats = evaluate()
    if not stats:
        return
    print("\nGenererer lærdommer med Claude...")
    lessons = generate_lessons(stats)
    print(lessons)
    update_knowledge(lessons)


if __name__ == "__main__":
    run()
