#!/bin/bash
PLIST="$HOME/Library/LaunchAgents/com.ffalerts.news.plist"
launchctl unload "$PLIST" 2>/dev/null
rm -f "$PLIST"
rm -rf "$HOME/.ff-alerts"
echo "Desinstalado."
