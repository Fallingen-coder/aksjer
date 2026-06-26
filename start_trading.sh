#!/usr/bin/env bash
# start_trading.sh — Kjør handelssystemet hvert 10. minutt i børstid
# Bruk: ./start_trading.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Last inn secrets fra .env hvis den finnes
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Sjekk at nødvendige env-variabler er satt
: "${SUPABASE_URL:?Mangler SUPABASE_URL}"
: "${SUPABASE_KEY:?Mangler SUPABASE_KEY}"
: "${ANTHROPIC_API_KEY:?Mangler ANTHROPIC_API_KEY}"

INTERVAL=1800  # 30 minutter

echo "╔══════════════════════════════════════════╗"
echo "║   Aksje-bot startet — kjører hvert 30m  ║"
echo "╚══════════════════════════════════════════╝"
echo "Trykk Ctrl+C for å stoppe."
echo ""

is_market_hours() {
  local hour min day
  hour=$(date '+%H')
  min=$(date '+%M')
  day=$(date '+%u')  # 1=mandag, 7=søndag
  local time_min=$(( hour * 60 + min ))
  local open=540    # 09:00
  local close=1050  # 17:30
  [[ $day -le 5 && $time_min -ge $open && $time_min -lt $close ]]
}

run_once() {
  local now
  now=$(date '+%H:%M:%S')

  if ! is_market_hours; then
    echo "⏸  $now — Børsen er stengt (åpner man–fre 09:00–17:30). Venter..."
    return
  fi

  echo "━━━ $now ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

  echo "📊 Henter intradag-kurser..."
  python3 fetch_intraday.py

  echo "📰 Henter nyheter..."
  python3 fetch_news.py

  echo "🤖 AI-analyse..."
  python3 analyse.py

  echo "💼 Papirhandel..."
  python3 trade.py

  echo "📈 Oppdaterer performance..."
  python3 performance.py

  echo "✓ Ferdig kl $(date '+%H:%M:%S')"
  echo ""
}

# Kjør med en gang ved oppstart
run_once

# Loop hvert 10. minutt
while true; do
  echo "Neste kjøring om $((INTERVAL / 60)) minutter..."
  sleep $INTERVAL
  run_once
done
