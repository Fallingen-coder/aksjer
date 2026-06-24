"""Henter nyheter for Oslo Børs-tickers fra RSS-feeds."""

import feedparser
import requests
import anthropic
import os
import ssl
from datetime import datetime, timezone
from db import get_client
from tickers import TICKERS

MODEL = "claude-haiku-4-5-20251001"

# Bekreftet fungerende RSS-feeds
GENERAL_FEEDS = [
    ("E24",    "https://e24.no/feed/rss/"),
]

TICKER_KEYWORDS = {
    "EQNR.OL":  ["equinor", "eqnr"],
    "DNB.OL":   ["dnb"],
    "TEL.OL":   ["telenor"],
    "MOWI.OL":  ["mowi"],
    "ORK.OL":   ["orkla"],
    "YAR.OL":   ["yara"],
    "SALM.OL":  ["salmar"],
    "RECSI.OL": ["rec silicon", "recsi"],
    "AKER.OL":  ["aker asa", " aker "],
    "STB.OL":   ["storebrand"],
}


def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def summarize(client: anthropic.Anthropic, title: str, description: str) -> str:
    text = description.strip() if description else ""
    if len(text) < 30:
        return text
    response = client.messages.create(
        model=MODEL,
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": f"Oppsummer på én setning (maks 25 ord), norsk:\n{title}\n{text[:600]}"
        }],
    )
    return response.content[0].text.strip()


def fetch_for_ticker(sb, client: anthropic.Anthropic, ticker: str) -> int:
    saved = 0
    existing = {
        r["title"]
        for r in sb.table("news").select("title").eq("ticker", ticker).execute().data
    }
    keywords = TICKER_KEYWORDS.get(ticker, [ticker.replace(".OL", "").lower()])

    for source_name, url in GENERAL_FEEDS:
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:50]:
                title = entry.get("title", "").strip()
                if not title or title in existing:
                    continue
                title_lower = title.lower()
                desc_lower  = entry.get("summary", "").lower()
                if not any(kw in title_lower or kw in desc_lower for kw in keywords):
                    continue
                summary = summarize(client, title, entry.get("summary", ""))
                sb.table("news").insert({
                    "ticker":     ticker,
                    "title":      title,
                    "url":        entry.get("link", ""),
                    "summary":    summary,
                    "source":     source_name,
                    "fetched_at": parse_date(entry),
                }).execute()
                existing.add(title)
                saved += 1
        except Exception as e:
            print(f"    [{source_name}] feil: {e}")

    return saved


def run():
    sb = get_client()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("Henter nyheter for Oslo Børs-tickers...\n")
    total = 0
    for ticker in TICKERS:
        n = fetch_for_ticker(sb, client, ticker)
        if n:
            print(f"  {ticker}: {n} nye nyheter lagret")
        total += n

    print(f"\n✓ Totalt {total} nyheter lagret i Supabase.")


if __name__ == "__main__":
    run()
