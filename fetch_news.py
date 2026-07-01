"""Henter nyheter for Oslo Børs-tickers via yfinance og E24 RSS."""

import feedparser
import requests
import yfinance as yf
import os
from datetime import datetime, timezone, timedelta
from db import get_client
from tickers import TICKERS

TICKER_KEYWORDS = {
    "EQNR.OL":   ["equinor", "eqnr"],
    "DNB.OL":    ["dnb"],
    "TEL.OL":    ["telenor"],
    "MOWI.OL":   ["mowi"],
    "ORK.OL":    ["orkla"],
    "YAR.OL":    ["yara"],
    "SALM.OL":   ["salmar"],
    "AKER.OL":   ["aker asa", " aker "],
    "STB.OL":    ["storebrand"],
    "NHY.OL":    ["hydro", "nhy"],
    "AKRBP.OL":  ["aker bp", "akerbp"],
    "HAFNI.OL":  ["hafnia"],
    "MPCC.OL":   ["mpc container", "mpcc"],
    "BORR.OL":   ["borr drilling"],
    "SOFF.OL":   ["solstad"],
    "TGS.OL":    ["tgs"],
    "SUBC.OL":   ["subsea 7", "subc"],
    "GJF.OL":    ["gjensidige"],
    "ATEA.OL":   ["atea"],
    "NONG.OL":   ["northern ocean", "nong"],
    "HBC.OL":    ["hbc"],
    "ENTRA.OL":  ["entra"],
    "SATS.OL":   ["sats"],
    "KOG.OL":    ["keystone rig", " kog "],
    "NRC.OL":    ["nrc group"],
    "SCATC.OL":  ["scatec"],
    "NSKOG.OL":  ["norske skog"],
    "KIT.OL":    ["kitron"],
    "LINK.OL":   ["link mobility"],
    "MING.OL":   ["ming"],
    "BEWI.OL":   ["bewi"],
    "BWO.OL":    ["bw offshore"],
    "BWLPG.OL":  ["bw lpg"],
    "OKEA.OL":   ["okea"],
    "SMOP.OL":   ["sm offshore", "smop"],
    "PEXIP.OL":  ["pexip"],
    "ABG.OL":    ["abg sundal"],
    "AUSS.OL":   ["austevoll"],
    "LSG.OL":    ["lerøy", "leroy"],
    "PHO.OL":    ["philly shipyard"],
    "ODL.OL":    ["odfjell drilling"],
    "SCANA.OL":  ["scana"],
    "2020.OL":   ["2020 bulkers"],
    "NEXT.OL":   ["next biometrics"],
    "EMGS.OL":   ["emgs", "electromagnetic"],
    "IDEX.OL":   ["idex biometrics"],
    "HAVI.OL":   ["havila"],
    "BWE.OL":    ["bw energy"],
    "TOM.OL":    ["tomra"],
}

E24_FEED = "https://e24.no/feed/rss/"
NEWSWEB_API = "https://api3.oslo.oslobors.no/v1/newsreader/list"

# NewsWeb-kategorier som er mest kurssensitive
NEWSWEB_PRIORITY = {
    "INSIDE INFORMATION",
    "MANDATORY NOTIFICATION OF TRADE",   # innsidehandler
    "FINANCIAL REPORTING",
    "HALF YEARLY FINANCIAL REPORTS AND AUDIT REPORTS / LIMITED REVIEWS",
    "EX DIVIDEND DATE",
    "MERGERS AND ACQUISITIONS",
    "PROFIT WARNING",
    "ISSUANCE OF SECURITIES",
}


def fetch_newsweb(sb, tickers: list[str]) -> int:
    """Henter offisielle børsmeldinger fra Oslo Børs NewsWeb (siste 2 dager)."""
    from datetime import date
    saved = 0
    ticker_set = {t.replace(".OL", "") for t in tickers}
    try:
        from_date = (date.today() - timedelta(days=2)).isoformat()
        r = requests.get(
            NEWSWEB_API,
            params={"fromDate": from_date},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        messages = r.json()["data"]["messages"]
    except Exception as e:
        print(f"  NewsWeb: feil — {e}")
        return 0

    # Grupper per ticker slik at vi kan dedupe mot eksisterende titler
    by_ticker: dict[str, list[dict]] = {}
    for m in messages:
        sign = m.get("issuerSign", "")
        if m.get("test") or sign not in ticker_set:
            continue
        cats = {c.get("category_en", "") for c in m.get("category", [])}
        prioritized = bool(cats & NEWSWEB_PRIORITY)
        by_ticker.setdefault(sign + ".OL", []).append({
            "title":  m.get("title", "").strip(),
            "cats":   ", ".join(sorted(cats)) or "Børsmelding",
            "ts":     m.get("publishedTime", datetime.now(timezone.utc).isoformat()),
            "msg_id": m.get("messageId", ""),
            "pri":    prioritized,
        })

    for ticker, msgs in by_ticker.items():
        existing = {
            r["title"]
            for r in sb.table("news").select("title").eq("ticker", ticker).execute().data
        }
        for m in msgs:
            if not m["title"]:
                continue
            url = f"https://newsweb.oslobors.no/message/{m['msg_id']}" if m["msg_id"] else ""
            prefix = "⚠ " if m["pri"] else ""
            if _insert(sb, ticker, m["title"], url,
                       f"{prefix}Børsmelding [{m['cats']}]",
                       "NewsWeb", m["ts"], existing):
                saved += 1
    if saved:
        print(f"  NewsWeb: {saved} børsmeldinger lagret")
    return saved


def parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _insert(sb, ticker: str, title: str, url: str, summary: str, source: str, fetched_at: str, existing: set) -> bool:
    if title in existing:
        return False
    try:
        sb.table("news").insert({
            "ticker":     ticker,
            "title":      title,
            "url":        url,
            "summary":    summary,
            "source":     source,
            "fetched_at": fetched_at,
        }).execute()
        existing.add(title)
        return True
    except Exception:
        return False


def fetch_yfinance_news(sb, ticker: str, existing: set) -> int:
    """Henter nyheter direkte fra yfinance (Yahoo Finance) per ticker."""
    saved = 0
    try:
        news_items = yf.Ticker(ticker).news or []
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for item in news_items:
            content = item.get("content", item)
            title = content.get("title", "").strip()
            if not title:
                continue
            url = content.get("canonicalUrl", {}).get("url", "") or content.get("link", "")
            source = content.get("provider", {}).get("displayName", "Yahoo Finance")
            # Dato
            pub = content.get("pubDate", "") or content.get("published", "")
            try:
                fetched_at = datetime.fromisoformat(pub.replace("Z", "+00:00")).isoformat() if pub else datetime.now(timezone.utc).isoformat()
            except Exception:
                fetched_at = datetime.now(timezone.utc).isoformat()
            # Filtrer bort for gamle nyheter
            try:
                if datetime.fromisoformat(fetched_at) < cutoff:
                    continue
            except Exception:
                pass
            summary = content.get("summary", "")[:200]
            if _insert(sb, ticker, title, url, summary, source, fetched_at, existing):
                saved += 1
    except Exception:
        pass
    return saved


def fetch_e24_news(sb, ticker: str, existing: set) -> int:
    """Henter nyheter fra E24 RSS basert på selskapsnavn-matching."""
    saved = 0
    keywords = TICKER_KEYWORDS.get(ticker, [ticker.replace(".OL", "").lower()])
    try:
        resp = requests.get(E24_FEED, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        feed = feedparser.parse(resp.text)
        for entry in feed.entries[:50]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            title_lower = title.lower()
            desc_lower  = entry.get("summary", "").lower()
            if not any(kw in title_lower or kw in desc_lower for kw in keywords):
                continue
            if _insert(sb, ticker, title,
                       entry.get("link", ""),
                       entry.get("summary", "")[:200],
                       "E24", parse_date(entry), existing):
                saved += 1
    except Exception:
        pass
    return saved


def run():
    sb = get_client()
    print("Henter nyheter for Oslo Børs-tickers...\n")
    total = fetch_newsweb(sb, TICKERS)
    for ticker in TICKERS:
        existing = {
            r["title"]
            for r in sb.table("news").select("title").eq("ticker", ticker).execute().data
        }
        n  = fetch_yfinance_news(sb, ticker, existing)
        n += fetch_e24_news(sb, ticker, existing)
        if n:
            print(f"  {ticker}: {n} nye nyheter lagret")
        total += n

    print(f"\n✓ Totalt {total} nyheter lagret i Supabase.")


if __name__ == "__main__":
    run()
