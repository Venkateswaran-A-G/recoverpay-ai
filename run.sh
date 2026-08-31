#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo " ============================================================"
echo "  RecoverPay AI"
echo "  Starting RecoverPay AI Engine..."
echo " ============================================================"
echo
echo "  API        http://127.0.0.1:8000"
echo "  Dashboard  http://localhost:8000"
echo "  Health     http://localhost:8000/health"
echo
echo "  Keep this terminal open while the engine is running."
echo "  Press Ctrl+C to stop the server."
echo

if [[ -x ".venv/bin/python" ]]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

"$PY" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
sleep 2

if command -v open >/dev/null 2>&1; then
  open "http://localhost:8000"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:8000" >/dev/null 2>&1 || true
fi

echo "  Browser opened. uvicorn is running in the background (PID $!)."
echo
wait
