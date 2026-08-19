#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
[ -f data/unigraph.db ] || python seed_demo.py
python run.py
