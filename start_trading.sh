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

INTERVAL=600  # 10 minutter

echo "╔══════════════════════════════════════════╗"
echo "║   Aksje-bot startet — kjører hvert 10m  ║"
echo "╚══════════════════════════════════════════╝"
echo "Trykk Ctrl+C for å stoppe."
echo ""

run_once() {
  local now
  now=$(date '+%H:%M:%S')
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
