#!/bin/zsh
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ ! -f models/ggml-large-v3-turbo-q5_0.bin || ! -f models/ggml-silero-v6.2.0.bin ]]; then
  python3 scripts/setup.py || exit 1
fi
# Reuse the already-running local app only if its authenticated health check succeeds.
python3 - <<'CHECK'
from pathlib import Path
import json
import urllib.request
try:
    token=Path('data/token').read_text().strip()
    req=urllib.request.Request('http://127.0.0.1:8765/api/status',headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(req,timeout=2) as response:
        assert response.status==200
        status=json.load(response)
except Exception:
    raise SystemExit(1)
if status.get('version') != '0.2.0':
    print('È aperta una versione precedente di LocalCall. Chiudila dal suo Terminale con Control+C, poi riapri questo file.')
    raise SystemExit(2)
CHECK
health_result=$?
if [[ "$health_result" == 2 ]]; then
  read "?Premi Invio per chiudere."
  exit 1
fi
if [[ "$health_result" == 0 ]]; then
  token=$(cat data/token)
  open "http://127.0.0.1:8765/#$token"
  exit 0
fi
python3 -m localcall.server &
server_pid=$!
trap 'kill $server_pid 2>/dev/null' EXIT INT TERM
sleep 1
if kill -0 "$server_pid" 2>/dev/null; then
  token=$(cat data/token)
  open "http://127.0.0.1:8765/#$token"
  wait "$server_pid"
fi
