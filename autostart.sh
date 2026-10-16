#!/bin/bash
# Makes Voice Dictation start automatically when you log in.
# It opens a Terminal window running run.sh (Terminal already has the
# Microphone and Input Monitoring permissions). Minimize the window, don't close it.
#   ./autostart.sh          enable
#   ./autostart.sh off      disable
set -euo pipefail
cd "$(dirname "$0")"
LAUNCHER="$HOME/Applications/Voice Dictation.command"

if [[ "${1:-}" == "off" ]]; then
  osascript -e 'tell application "System Events" to delete (every login item whose name is "Voice Dictation.command")' >/dev/null 2>&1 || true
  rm -f "$LAUNCHER"
  echo "Autostart disabled."
  exit 0
fi

mkdir -p "$HOME/Applications"
cat > "$LAUNCHER" <<SH
#!/bin/bash
cd "$(pwd)"
pkill -f dictation.py 2>/dev/null; sleep 1
exec ./run.sh
SH
chmod +x "$LAUNCHER"

if osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$LAUNCHER\", hidden:true}" >/dev/null 2>&1; then
  echo "Autostart enabled: Voice Dictation will start when you log in."
else
  echo "Could not add the login item automatically. Add it by hand:"
  echo "  System Settings > General > Login Items > + > $LAUNCHER"
fi
