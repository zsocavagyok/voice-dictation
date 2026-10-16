#!/bin/bash
# Start Voice Dictation automatically (in the background) when you log in.
#   ./autostart.sh          enable
#   ./autostart.sh off      disable
set -euo pipefail
APP="$HOME/Applications/Voice Dictation.app"

remove_items() {
  osascript -e 'tell application "System Events" to delete (every login item whose name is "Voice Dictation.command" or name is "Voice Dictation")' >/dev/null 2>&1 || true
  rm -f "$HOME/Applications/Voice Dictation.command"   # old Terminal-based launcher
}

if [[ "${1:-}" == "off" ]]; then
  remove_items
  echo "Autostart disabled."
  exit 0
fi

if [[ ! -d "$APP" ]]; then
  echo "$APP not found - run ./install.sh first." >&2
  exit 1
fi
remove_items
if osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:true}" >/dev/null 2>&1; then
  echo "Autostart enabled: Voice Dictation will start in the background when you log in."
else
  echo "Could not add the login item automatically. Add it by hand:"
  echo "  System Settings > General > Login Items > + > $APP"
fi
