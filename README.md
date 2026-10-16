# Voice Dictation 🎙

Push-to-talk dictation for macOS (Apple Silicon) in **English** and **Hungarian**.
Everything runs locally with Whisper (large-v3-turbo via MLX) — no internet, no API key.

| Hold            | Language  |
|-----------------|-----------|
| **Right ⌥**     | English   |
| **Right ⌘**     | Hungarian |

Hold the key, speak, release. A second later the text is on your clipboard — press **⌘V** anywhere.

## Install

No Python setup needed — if you don't have Python 3.10+, the installer downloads its own copy.

```bash
git clone https://github.com/zsocavagyok/voice-dictation.git
cd voice-dictation
./install.sh
open ~/Applications/"Voice Dictation.app"
```

The installer downloads the Whisper model (~1.6 GB) once.

### Permissions (first launch)

macOS will ask for two permissions — allow both, then quit and reopen the app:

1. **Microphone** — to record while you hold the key.
2. **Input Monitoring** — to detect the Right ⌥ / Right ⌘ keys.
   (System Settings → Privacy & Security → Input Monitoring)

### Start at login

```bash
./autostart.sh        # enable  (./autostart.sh off to disable)
```

This opens a Terminal window running `./run.sh` at login — minimize it, don't close it.

## Menu-bar icon

| Icon     | Meaning                         |
|----------|---------------------------------|
| ⏳       | Loading model                   |
| 🎙       | Ready                           |
| 🔴 EN/HU | Recording                       |
| ✍️       | Transcribing                    |

The menu also has **Recent** (click to re-copy one of your last 5 transcripts) and a **Sounds** toggle.

## Notes

- Taps shorter than 0.3 s are ignored, and using the key in a shortcut (e.g. Right ⌘ + C) cancels recording.
- Want a different model? `DICTATION_MODEL=mlx-community/whisper-large-v3-mlx ./install.sh`
  (and set the same env var when running), or edit `MODEL` in `dictation.py`.
- Different hotkeys: edit `HOTKEYS` in `dictation.py` (macOS keycodes).

## Troubleshooting

- **Nothing happens on keypress** → Input Monitoring isn't granted. Remove and re-add
  "Voice Dictation" in Privacy & Security → Input Monitoring, then restart the app.
- **Mic/permission issues with the .app** → run `./run.sh` from Terminal instead
  (permissions then go to Terminal). Errors print there.
- Logs: `~/Library/Logs/VoiceDictation.log`
