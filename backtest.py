"""
Backtest — replayer lagrede AI-signaler mot faktisk kurshistorikk
med konfigurerbare parametere. Brukes til å teste parameterendringer
(stop-loss, konfidensterskel, posisjonsstørrelse) uten risiko.

Bruk:
  python3 backtest.py            # kjør parametergrid og sammenlign
  python3 backtest.py --single   # kjør kun dagens parametre
"""

import sys
from collections import defaultdict
from db import get_client
from trade import SECTORS, kurtasje

START_CAPITAL = 100_000.0

# Dagens produksjonsparametre (fra trade.py)
DEFAULT = {
    "min_confidence":  0.70,
    "stop_loss_pct":   0.07,
    "max_position_pct": 0.10,
    "max_exposure":    0.80,
    "max_per_sector":  2,
    "trailing":        True,
}


def load_data(sb):
    """Laster signaler og kurshistorikk fra Supabase."""
    signals = (
        sb.table("signals")
        .select("ticker, signal, confidence, ts")
        .in_("signal", ["BUY", "SELL"])
        .order("ts", desc=False)
        .execute()
        .data
    )
    # Supabase returnerer maks 1000 rader per kall — paginer
    prices = []
    offset = 0
    while True:
        page = (
            sb.table("intraday_prices")
            .select("ticker, ts, close")
            .order("ts", desc=False)
            .range(offset, offset + 999)
            .execute()
            .data
        )
        prices.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in prices:
        series[p["ticker"]].append((p["ts"], float(p["close"])))
    return signals, series


def price_at(series, ticker: str, ts: str) -> float | None:
    """Siste kjente kurs ved tidspunkt ts."""
    pts = series.get(ticker, [])
    last = None
    for t, c in pts:
        if t > ts:
            break
        last = c
    return last


def path_between(series, ticker: str, ts_from: str, ts_to: str) -> list[float]:
    """Kurser i tidsvinduet (brukes til stop-loss-sjekk mellom kjøringer)."""
    return [c for t, c in series.get(ticker, []) if ts_from < t <= ts_to]


def run_backtest(signals, series, p: dict) -> dict:
    cash = START_CAPITAL
    holdings: dict[str, dict] = {}   # ticker -> {shares, avg_cost, peak}
    trades, wins = 0, 0
    realized_pnl = 0.0

    # Grupper signaler per kjøringstidspunkt
    runs: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        runs[s["ts"]].append(s)
    run_times = sorted(runs.keys())

    def total_value(ts):
        v = cash
        for tk, h in holdings.items():
            pr = price_at(series, tk, ts) or h["avg_cost"]
            v += h["shares"] * pr
        return v

    def sell(ticker, price, is_stop=False):
        nonlocal cash, trades, wins, realized_pnl
        h = holdings.pop(ticker)
        gross = h["shares"] * price
        net = gross - kurtasje(gross)
        pnl = net - h["shares"] * h["avg_cost"]
        cash += net
        trades += 1
        realized_pnl += pnl
        if pnl > 0:
            wins += 1

    prev_ts = ""
    for ts in run_times:
        # 1) Stop-loss sjekk på kurspath siden forrige kjøring
        for ticker in list(holdings.keys()):
            h = holdings[ticker]
            path = path_between(series, ticker, prev_ts, ts) if prev_ts else []
            for c in path:
                if p["trailing"]:
                    h["peak"] = max(h["peak"], c)
                ref = h["peak"] if p["trailing"] else h["avg_cost"]
                if (ref - c) / ref >= p["stop_loss_pct"]:
                    sell(ticker, c, is_stop=True)
                    break

        # 2) Behandle signaler
        buys_this_run = 0
        for s in runs[ts]:
            ticker = s["ticker"]
            conf   = float(s["confidence"])
            if conf < p["min_confidence"]:
                continue
            price = price_at(series, ticker, ts)
            if not price:
                continue

            if s["signal"] == "SELL" and ticker in holdings:
                sell(ticker, price)

            elif s["signal"] == "BUY" and ticker not in holdings:
                if buys_this_run >= 3:
                    continue
                tv = total_value(ts)
                invested = tv - cash
                if invested / tv >= p["max_exposure"]:
                    continue
                sektor = SECTORS.get(ticker, "ukjent")
                n_sektor = sum(1 for t in holdings if SECTORS.get(t, "") == sektor)
                if sektor != "ukjent" and n_sektor >= p["max_per_sector"]:
                    continue
                spend = min(tv * p["max_position_pct"], cash * 0.95)
                if spend < 500:
                    continue
                fee = kurtasje(spend)
                shares = (spend - fee) / price
                holdings[ticker] = {
                    "shares":   shares,
                    "avg_cost": spend / shares,
                    "peak":     price,
                }
                cash -= spend
                buys_this_run += 1
        prev_ts = ts

    end_value = total_value(run_times[-1]) if run_times else cash
    return {
        "end_value":    end_value,
        "return_pct":   (end_value / START_CAPITAL - 1) * 100,
        "trades":       trades,
        "wins":         wins,
        "realized_pnl": realized_pnl,
        "open_pos":     len(holdings),
    }


def main():
    sb = get_client()
    print("Laster signaler og kurshistorikk fra Supabase...")
    signals, series = load_data(sb)
    n_days = len({s["ts"][:10] for s in signals})
    print(f"{len(signals)} signaler over {n_days} børsdager, {len(series)} tickers med kursdata.\n")

    if "--single" in sys.argv:
        r = run_backtest(signals, series, DEFAULT)
        print(f"Sluttverdi: {r['end_value']:,.0f} NOK ({r['return_pct']:+.2f}%)")
        print(f"Salg: {r['trades']} (hvorav {r['wins']} med gevinst) | Åpne posisjoner: {r['open_pos']}")
        return

    # Parametergrid
    print(f"{'Stop':>5} {'Trail':>6} {'Konf':>5} | {'Sluttverdi':>12} {'Avkastn.':>9} {'Salg':>5} {'Vinn':>5} {'Åpne':>5}")
    print("-" * 65)
    for stop in [0.05, 0.07, 0.10]:
        for trailing in [True, False]:
            for conf in [0.70, 0.75, 0.80]:
                params = DEFAULT | {
                    "stop_loss_pct": stop,
                    "trailing": trailing,
                    "min_confidence": conf,
                }
                r = run_backtest(signals, series, params)
                star = " ← dagens" if (stop, trailing, conf) == (0.07, True, 0.70) else ""
                print(
                    f"{stop:>5.0%} {'ja' if trailing else 'nei':>6} {conf:>5.0%} | "
                    f"{r['end_value']:>12,.0f} {r['return_pct']:>+8.2f}% "
                    f"{r['trades']:>5} {r['wins']:>5} {r['open_pos']:>5}{star}"
                )

    print("\nNB: kort historikk (~1 uke) — resultatene er indikative, ikke statistisk robuste.")


if __name__ == "__main__":
    main()
