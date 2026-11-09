#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  Starting Audilect Active Learning Cockpit..."
echo "==================================================="

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    exit 1
fi

echo "Checking dependencies..."
python3 -m pip install -r requirements.txt --quiet

echo "Launching web cockpit on http://localhost:8000"
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8000 &
elif command -v open &> /dev/null; then
    open http://localhost:8000 &
fi

python3 run.py --host 127.0.0.1 --port 8000
