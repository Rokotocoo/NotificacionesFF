#!/bin/bash
# Uso: bash instalar.sh NOMBRE_DE_TU_TEMA_NTFY
set -e
TOPIC="$1"
if [ -z "$TOPIC" ]; then echo "Uso: bash instalar.sh NOMBRE_DE_TU_TEMA"; exit 1; fi

DIR="$HOME/.ff-alerts"
mkdir -p "$DIR"
cp "$(dirname "$0")/ff_news_local.py" "$DIR/"

echo "→ Creando entorno de Python…"
python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q playwright requests
echo "→ Descargando navegador…"
"$DIR/venv/bin/python" -m playwright install chromium

PLIST="$HOME/Library/LaunchAgents/com.ffalerts.news.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" << PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ffalerts.news</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/caffeinate</string><string>-i</string>
    <string>$DIR/venv/bin/python</string><string>$DIR/ff_news_local.py</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>NTFY_TOPIC</key><string>$TOPIC</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DIR/log.txt</string>
  <key>StandardErrorPath</key><string>$DIR/log.txt</string>
</dict></plist>
PL

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo ""
echo "✅ Listo. El lector de FF News está corriendo y arrancará solo al iniciar sesión."
echo "   Log: $DIR/log.txt"
