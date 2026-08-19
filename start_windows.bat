@echo off
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
if not exist data\unigraph.db python seed_demo.py
python run.py
