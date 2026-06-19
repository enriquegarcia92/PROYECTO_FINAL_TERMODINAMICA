#!/bin/zsh
set -e
ROOT="${0:A:h:h}"
cd "$ROOT"
exec .venv/bin/python main.py
