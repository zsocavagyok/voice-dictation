#!/bin/bash
# Installs Voice Dictation: Python venv, dependencies, Whisper model, and a
# "Voice Dictation.app" in ~/Applications you can launch / add to Login Items.
set -euo pipefail

cd "$(dirname "$0")"
REPO_DIR="$(pwd)"
MODEL="${DICTATION_MODEL:-mlx-community/whisper-large-v3-turbo}"
APP="$HOME/Applications/Voice Dictation.app"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This app needs macOS on Apple Silicon (M1 or newer)." >&2
  exit 1
fi

# Pick the newest suitable Python (3.10-3.13) already on the machine.
PY=""
for v in 3.13 3.12 3.11 3.10; do
  for cand in "/opt/homebrew/bin/python$v" \
              "/Library/Frameworks/Python.framework/Versions/$v/bin/python$v" \
              "$(command -v "python$v" 2>/dev/null || true)"; do
    if [[ -n "$cand" && -x "$cand" ]]; then PY="$cand"; break 2; fi
  done
done

# None found: download a private copy of Python 3.12 with uv (no Homebrew/admin needed).
if [[ -z "$PY" ]]; then
  echo "==> Python 3.10+ not found - downloading Python 3.12 (one-time, ~20 MB)"
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh || {
      echo "Could not download uv. Install Python 3.12 from https://www.python.org/downloads/ and re-run." >&2
      exit 1
    }
  fi
  uv python install 3.12
  PY="$(uv python find 3.12)"
fi
echo "==> Using $PY"

echo "==> Creating virtual environment"
"$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
echo "==> Installing dependencies (this can take a minute)"
.venv/bin/pip install --quiet -r requirements.txt

echo "==> Downloading Whisper model $MODEL (~1.6 GB, first time only)"
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL')"

echo "==> Building $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cat > "$APP/Contents/MacOS/VoiceDictation" <<SH
#!/bin/bash
mkdir -p "\$HOME/Library/Logs"
exec "$REPO_DIR/.venv/bin/python" "$REPO_DIR/dictation.py" >> "\$HOME/Library/Logs/VoiceDictation.log" 2>&1
SH
chmod +x "$APP/Contents/MacOS/VoiceDictation"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Voice Dictation</string>
  <key>CFBundleIdentifier</key><string>local.voice-dictation</string>
  <key>CFBundleExecutable</key><string>VoiceDictation</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key>
  <string>Voice Dictation records your voice while you hold the hotkey, to transcribe it.</string>
</dict>
</plist>
PLIST
codesign --force --sign - "$APP" >/dev/null 2>&1 || true

echo
echo "Done!"
echo "  Start it:        open \"$APP\"   (or ./run.sh to run in this terminal)"
echo "  Auto-start:      System Settings > General > Login Items > + > Voice Dictation"
echo "  Logs:            ~/Library/Logs/VoiceDictation.log"
echo
echo "On first start macOS asks for Microphone and Input Monitoring access - allow both,"
echo "then quit and reopen the app."
