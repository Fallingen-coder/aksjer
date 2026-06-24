"""Streamlit-dashboard for aksjeporteføljen."""

import os
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from db import get_client

st.set_page_config(
    page_title="Aksjeportefølje",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .metric-card { background: #1e1e2e; border-radius: 12px; padding: 1rem 1.5rem; }
    .signal-buy  { color: #4ade80; font-weight: bold; }
    .signal-sell { color: #f87171; font-weight: bold; }
    .signal-hold { color: #facc15; font-weight: bold; }
    .pos-pnl { color: #4ade80; }
    .neg-pnl { color: #f87171; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    sb = get_client()

    cash = float(sb.table("cash").select("amount").eq("id", 1).single().execute().data["amount"])

    holdings = sb.table("portfolio").select("*").execute().data

    # Siste kurs per ticker
    all_prices = sb.table("prices").select("ticker, date, close").execute().data
    latest_price = {}
    for r in all_prices:
        t = r["ticker"]
        if t not in latest_price or r["date"] > latest_price[t]["date"]:
            latest_price[t] = r

    # Porteføljeverdi og P&L per posisjon
    positions = []
    total_stock_value = 0
    total_cost = 0
    for h in holdings:
        t = h["ticker"]
        shares = float(h["shares"])
        avg_cost = float(h["avg_cost"])
        price = latest_price.get(t, {}).get("close", avg_cost)
        value = shares * price
        cost = shares * avg_cost
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0
        positions.append({
            "Ticker": t,
            "Antall": round(shares, 2),
            "Innkjøpskurs": round(avg_cost, 2),
            "Nåkurs": round(price, 2),
            "Verdi (NOK)": round(value, 0),
            "P&L (NOK)": round(pnl, 0),
            "P&L %": round(pnl_pct, 2),
        })
        total_stock_value += value
        total_cost += cost

    total_value = cash + total_stock_value
    total_pnl = total_value - 100_000  # startkapital

    # Siste signal per ticker
    all_signals = sb.table("signals").select("*").order("ts", desc=True).execute().data
    seen = set()
    signals = []
    for s in all_signals:
        if s["ticker"] not in seen:
            seen.add(s["ticker"])
            signals.append(s)

    # Kurshistorikk (30 dager) per ticker
    price_history = {}
    for r in all_prices:
        t = r["ticker"]
        if t not in price_history:
            price_history[t] = []
        price_history[t].append(r)
    for t in price_history:
        price_history[t].sort(key=lambda x: x["date"])
        price_history[t] = price_history[t][-30:]

    # Siste transaksjoner
    transactions = (
        sb.table("transactions")
        .select("*")
        .order("ts", desc=True)
        .limit(20)
        .execute()
        .data
    )

    # Siste nyheter
    news = (
        sb.table("news")
        .select("*")
        .order("fetched_at", desc=True)
        .limit(30)
        .execute()
        .data
    )

    return {
        "cash": cash,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "positions": positions,
        "signals": signals,
        "price_history": price_history,
        "transactions": transactions,
        "news": news,
        "latest_price": latest_price,
    }


def pnl_color(val):
    return "pos-pnl" if val >= 0 else "neg-pnl"


def signal_badge(signal):
    cls = {"BUY": "signal-buy", "SELL": "signal-sell", "HOLD": "signal-hold"}.get(signal, "")
    icon = {"BUY": "📈", "SELL": "📉", "HOLD": "⏸️"}.get(signal, "")
    return f'<span class="{cls}">{icon} {signal}</span>'


# ── Last inn data ──────────────────────────────────────────────────────────────
data = load_data()

st.title("📊 Aksjeportefølje — Papirhandel")
st.caption("Data oppdateres automatisk hver 5. minutt. Klikk ↺ for å tvinge oppdatering.")

# ── KPI-rad ────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
pnl = data["total_pnl"]
pnl_sign = "+" if pnl >= 0 else ""

col1.metric("Total porteføljeverdi", f"{data['total_value']:,.0f} NOK")
col2.metric("Kontanter", f"{data['cash']:,.0f} NOK")
col3.metric(
    "Urealisert P&L",
    f"{pnl_sign}{pnl:,.0f} NOK",
    delta=f"{pnl_sign}{pnl/1000:.1f}k",
    delta_color="normal",
)
col4.metric("Startkapital", "100 000 NOK")

st.divider()

# ── Portefølje + Signaler ──────────────────────────────────────────────────────
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("Portefølje")
    if data["positions"]:
        df = pd.DataFrame(data["positions"])
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "P&L %": st.column_config.NumberColumn(format="%.2f %%"),
                "Verdi (NOK)": st.column_config.NumberColumn(format="%.0f"),
                "P&L (NOK)": st.column_config.NumberColumn(format="%.0f"),
            },
        )

        # Kakediagram — fordeling
        fig = px.pie(
            df, values="Verdi (NOK)", names="Ticker",
            title="Fordeling av beholdning",
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(showlegend=False, height=280, margin=dict(t=40, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ingen åpne posisjoner.")

with col_right:
    st.subheader("AI-signaler (siste)")
    signal_map = {s["ticker"]: s for s in data["signals"]}
    lp = data["latest_price"]
    rows = []
    for ticker, s in sorted(signal_map.items()):
        price = lp.get(ticker, {}).get("close", "–")
        rows.append({
            "Ticker": ticker,
            "Signal": s["signal"],
            "Konfidens": f"{float(s['confidence']):.0%}",
            "Kurs": f"{price:.2f}" if isinstance(price, float) else price,
            "Begrunnelse": (s.get("reasoning") or "")[:80] + "…",
        })
    if rows:
        df_sig = pd.DataFrame(rows)
        st.dataframe(df_sig, use_container_width=True, hide_index=True)

st.divider()

# ── Kursgrafer ─────────────────────────────────────────────────────────────────
st.subheader("Kursutvikling (30 dager)")
tickers_with_data = sorted(data["price_history"].keys())
cols = st.columns(5)
for i, ticker in enumerate(tickers_with_data):
    hist = data["price_history"][ticker]
    if not hist:
        continue
    dates  = [r["date"] for r in hist]
    closes = [r["close"] for r in hist]
    pct_change = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
    color      = "rgba(74,222,128,1)"   if pct_change >= 0 else "rgba(248,113,113,1)"
    fill_color = "rgba(74,222,128,0.1)" if pct_change >= 0 else "rgba(248,113,113,0.1)"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=closes,
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=fill_color,
    ))
    sign = "+" if pct_change >= 0 else ""
    fig.update_layout(
        title=dict(text=f"{ticker}<br><span style='font-size:12px'>{sign}{pct_change:.1f}%</span>", font_size=13),
        height=160,
        margin=dict(t=45, b=10, l=10, r=10),
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    cols[i % 5].plotly_chart(fig, use_container_width=True)

st.divider()

# ── Transaksjoner + Nyheter ────────────────────────────────────────────────────
col_tx, col_news = st.columns(2)

with col_tx:
    st.subheader("Transaksjonslogg")
    if data["transactions"]:
        df_tx = pd.DataFrame([{
            "Tidspunkt": r["ts"][:16].replace("T", " "),
            "Ticker": r["ticker"],
            "Type": r["action"],
            "Antall": round(float(r["shares"]), 2),
            "Kurs": round(float(r["price"]), 2),
            "Sum": round(float(r["shares"]) * float(r["price"]), 0),
        } for r in data["transactions"]])
        st.dataframe(df_tx, use_container_width=True, hide_index=True)
    else:
        st.info("Ingen transaksjoner ennå.")

with col_news:
    st.subheader("Siste nyheter")
    if data["news"]:
        for n in data["news"][:10]:
            ticker = n["ticker"]
            title  = n["title"]
            source = n.get("source", "")
            url    = n.get("url", "")
            date   = (n.get("fetched_at") or "")[:10]
            link = f"[{title}]({url})" if url else title
            st.markdown(f"**{ticker}** · {source} · {date}  \n{link}")
            if n.get("summary"):
                st.caption(n["summary"])
            st.divider()
    else:
        st.info("Ingen nyheter hentet ennå.")
