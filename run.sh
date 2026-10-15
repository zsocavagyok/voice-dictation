#!/bin/bash
# Run Voice Dictation from the terminal (useful for debugging - logs print here).
cd "$(dirname "$0")"
exec .venv/bin/python dictation.py
