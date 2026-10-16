#!/usr/bin/env python3
"""Push-to-talk voice dictation for macOS (English + Hungarian).

Hold Right Option  -> record English
Hold Right Command -> record Hungarian
Release            -> transcribe locally with Whisper (MLX) and copy to clipboard.
"""

import fcntl
import os
import queue
import sys
import subprocess
import threading
import time


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)

import numpy as np
import rumps
import sounddevice as sd
import Quartz
from AppKit import NSPasteboard, NSPasteboardTypeString, NSSound

# ---------------------------------------------------------------- settings ---

MODEL = os.environ.get("DICTATION_MODEL", "mlx-community/whisper-large-v3-turbo")
SAMPLE_RATE = 16000
MIN_SECONDS = 0.3          # ignore accidental taps shorter than this
SILENCE_RMS = 0.002        # skip clips quieter than this (avoids Whisper hallucinations)
HISTORY_SIZE = 5

# macOS virtual keycode -> (language, device-specific modifier flag bit)
HOTKEYS = {
    61: ("en", 0x00000040),  # Right Option  (NX_DEVICERALTKEYMASK)
    54: ("hu", 0x00000010),  # Right Command (NX_DEVICERCMDKEYMASK)
}

ICON_IDLE = "🎙"
ICON_LOADING = "⏳"
ICON_BUSY = "✍️"
ICON_REC = {"en": "🔴 EN", "hu": "🔴 HU"}

# Phrases Whisper tends to invent on near-silent audio.
HALLUCINATIONS = {
    "thank you.", "thanks for watching!", "thank you for watching.",
    "köszönöm.", "köszönöm szépen.", "feliratok: ...", "you",
}

INPUT_MONITORING_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
)


# --------------------------------------------------------------- recording ---

class Recorder:
    def __init__(self):
        self._chunks = []
        self._stream = None

    def start(self):
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=lambda data, *_: self._chunks.append(data.copy()),
        )
        self._stream.start()

    def stop(self):
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._chunks)[:, 0]


# ------------------------------------------------------------ transcription ---

class Transcriber(threading.Thread):
    """Background worker: loads the model once, then transcribes queued clips."""

    def __init__(self, results):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.results = results
        self.ready = False

    def run(self):
        import mlx_whisper  # heavy import, keep it off the main thread

        self._mlx_whisper = mlx_whisper
        try:
            # Warm-up: downloads the model on first run and compiles kernels.
            self._transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), "en")
        except Exception as e:
            self.results.put(("error", f"Model load failed: {e}"))
            return
        self.ready = True
        log("Model loaded - ready")
        self.results.put(("ready", None))

        while True:
            audio, lang = self.jobs.get()
            log(f"Transcribing {audio.size / SAMPLE_RATE:.1f}s of {lang}")
            try:
                self.results.put(("text", self._transcribe(audio, lang)))
            except Exception as e:
                self.results.put(("error", str(e)))

    def _transcribe(self, audio, lang):
        out = self._mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=MODEL,
            language=lang,
            task="transcribe",
            condition_on_previous_text=False,
            verbose=None,
        )
        return out["text"].strip()


def clean(text):
    if text.lower() in HALLUCINATIONS:
        return ""
    return text


# --------------------------------------------------------------------- app ---

class DictationApp(rumps.App):
    def __init__(self):
        super().__init__("Voice Dictation", title=ICON_LOADING, quit_button=None)

        self.status_item = rumps.MenuItem("Loading model (first run downloads ~1.6 GB)…")
        self.sounds_item = rumps.MenuItem("Sounds", callback=self.toggle_sounds)
        self.sounds_item.state = True
        self.history_menu = rumps.MenuItem("Recent")
        self.history_menu.add(rumps.MenuItem("(nothing yet)"))
        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Hold Right ⌥  → English"),
            rumps.MenuItem("Hold Right ⌘  → Hungarian"),
            None,
            self.history_menu,
            self.sounds_item,
            None,
            rumps.MenuItem("Quit", callback=rumps.quit_application),
        ]

        self.results = queue.Queue()
        self.transcriber = Transcriber(self.results)
        self.transcriber.start()
        self.recorder = Recorder()
        self.history = []

        self.active_lang = None     # language currently being recorded
        self.active_key = None
        self.started_at = 0.0
        self.pending = 0            # clips waiting for transcription

        self._install_event_tap()
        # Poll worker results on the main thread (UI + clipboard must be main-thread).
        self._timer = rumps.Timer(self._poll, 0.05)
        self._timer.start()

    # ---- hotkeys --------------------------------------------------------

    def _install_event_tap(self):
        if hasattr(Quartz, "CGPreflightListenEventAccess"):
            if not Quartz.CGPreflightListenEventAccess():
                Quartz.CGRequestListenEventAccess()

        mask = (Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
                | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown))
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            mask,
            self._on_event,
            None,
        )
        if self._tap is None:
            log("Hotkey listener NOT installed - Input Monitoring permission missing")
            self._tap_missing = True
            return
        log("Hotkey listener installed")
        self._tap_missing = False
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetMain(), source, Quartz.kCFRunLoopCommonModes
        )
        Quartz.CGEventTapEnable(self._tap, True)

    def _on_event(self, proxy, etype, event, refcon):
        if etype in (Quartz.kCGEventTapDisabledByTimeout,
                     Quartz.kCGEventTapDisabledByUserInput):
            Quartz.CGEventTapEnable(self._tap, True)
            return event

        if etype == Quartz.kCGEventKeyDown:
            # A normal key pressed while holding the hotkey (e.g. Right⌘+C):
            # the user is using a shortcut, not dictating.
            if self.active_lang is not None:
                self._cancel()
            return event

        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        if keycode not in HOTKEYS:
            return event
        lang, flag_bit = HOTKEYS[keycode]
        pressed = bool(Quartz.CGEventGetFlags(event) & flag_bit)

        if pressed and self.active_lang is None:
            self._start(lang, keycode)
        elif not pressed and self.active_key == keycode:
            self._finish()
        return event

    # ---- recording lifecycle -------------------------------------------

    def _start(self, lang, keycode):
        if not self.transcriber.ready:
            log("Hotkey pressed, but model is still loading")
            return
        try:
            self.recorder.start()
        except Exception as e:
            log(f"Microphone error: {e}")
            self._notify("Microphone error", str(e))
            return
        self.active_lang, self.active_key = lang, keycode
        self.started_at = time.monotonic()
        self.title = ICON_REC[lang]
        log(f"Recording ({lang})")
        self._sound("Tink")

    def _cancel(self):
        log("Recording cancelled (key used in a shortcut)")
        self.recorder.stop()
        self.active_lang = self.active_key = None
        self._refresh_title()

    def _finish(self):
        lang = self.active_lang
        duration = time.monotonic() - self.started_at
        audio = self.recorder.stop()
        self.active_lang = self.active_key = None

        if duration < MIN_SECONDS or audio.size == 0:
            log(f"Ignored: too short ({duration:.2f}s)")
            self._refresh_title()
            return
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < SILENCE_RMS:
            log(f"Ignored: silence (level {rms:.4f}) - is the microphone allowed?")
            self._refresh_title()
            return

        self.pending += 1
        self.transcriber.jobs.put((audio, lang))
        self._refresh_title()

    # ---- results (main thread) -----------------------------------------

    def _poll(self, _timer):
        if getattr(self, "_tap_missing", False):
            self._tap_missing = None
            self._permission_alert()

        while True:
            try:
                kind, payload = self.results.get_nowait()
            except queue.Empty:
                break
            if kind == "ready":
                self.status_item.title = "Ready"
            elif kind == "text":
                self.pending -= 1
                text = clean(payload)
                log(f"Result: {text!r}")
                if text:
                    copy_to_clipboard(text)
                    self._add_history(text)
                    self._sound("Pop")
            elif kind == "error":
                log(f"ERROR: {payload}")
                if self.pending:
                    self.pending -= 1
                self.status_item.title = f"Error: {payload[:60]}"
                self._notify("Voice Dictation error", payload)
                self._sound("Basso")
            self._refresh_title()

    def _refresh_title(self):
        if self.active_lang:
            self.title = ICON_REC[self.active_lang]
        elif not self.transcriber.ready:
            self.title = ICON_LOADING
        elif self.pending:
            self.title = ICON_BUSY
        else:
            self.title = ICON_IDLE

    def _add_history(self, text):
        self.history.insert(0, text)
        del self.history[HISTORY_SIZE:]
        self.history_menu.clear()
        for item in self.history:
            label = item if len(item) <= 50 else item[:47] + "…"
            self.history_menu.add(
                rumps.MenuItem(label, callback=lambda _, t=item: copy_to_clipboard(t))
            )

    # ---- misc ----------------------------------------------------------

    def toggle_sounds(self, sender):
        sender.state = not sender.state

    def _sound(self, name):
        if self.sounds_item.state:
            snd = NSSound.soundNamed_(name)
            if snd:
                snd.play()

    def _notify(self, title, message):
        try:
            rumps.notification(title, "", message)
        except Exception:
            print(f"{title}: {message}")

    def _permission_alert(self):
        rumps.alert(
            title="Input Monitoring permission needed",
            message=(
                "Voice Dictation needs Input Monitoring access to detect the "
                "Right ⌥ / Right ⌘ hotkeys.\n\nEnable it in System Settings → "
                "Privacy & Security → Input Monitoring, then restart the app."
            ),
        )
        subprocess.run(["open", INPUT_MONITORING_URL])


def copy_to_clipboard(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def single_instance():
    """Exit if another copy is already running (two copies would both react to hotkeys)."""
    lock = open(os.path.expanduser("~/Library/Caches/voice-dictation.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("Another copy of Voice Dictation is already running - exiting")
        sys.exit(0)
    return lock


if __name__ == "__main__":
    _lock = single_instance()
    log("Starting Voice Dictation")
    DictationApp().run()
