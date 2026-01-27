#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------
# ESG Day5 - Local Smoke Test Script
# - Load .env (DATABASE_URL)
# - Ensure DB driver installed (psycopg2)
# - Start uvicorn on 127.0.0.1:8001 (background)
# - Health check (/health)
# - Run sample /ai/agent/run with tmp_uploads files
# - Print how to stop server
# ---------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"   # .../AI/apps/esg_api
ENV_FILE="${APP_DIR}/.env"

PORT="${PORT:-8001}"
HOST="${HOST:-127.0.0.1}"
PID_FILE="/tmp/esg_api_${PORT}.pid"
LOG_FILE="/tmp/esg_api_${PORT}.log"
BASE_URL="http://${HOST}:${PORT}"

echo "[1/8] cd ${APP_DIR}"
cd "${APP_DIR}"

echo "[2/8] Load .env"
if [[ -f "${ENV_FILE}" ]]; then
  # .env must be bash-compatible: KEY=VALUE lines, comments allowed with #
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
else
  echo "❗ .env not found: ${ENV_FILE}"
fi

: "${DATABASE_URL:=postgresql+psycopg2://esg:esg_pw@127.0.0.1:5433/esg_db}"
export DATABASE_URL
echo "[ENV] DATABASE_URL=${DATABASE_URL}"

echo "[3/8] Check Python env (optional info)"
python -V || true
python -c "import sys; print('[PY]', sys.executable)" || true

echo "[4/8] Ensure DB driver exists: psycopg2"
python -c "import psycopg2; print('psycopg2 OK')" >/dev/null 2>&1 || {
  echo "Installing psycopg2-binary..."
  python -m pip install -q psycopg2-binary
  python -c "import psycopg2; print('psycopg2 OK after install')"
}

echo "[5/8] Start uvicorn (background) on ${BASE_URL}"
# if pid file exists, try to stop previous process
if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}" || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" >/dev/null 2>&1; then
    echo "Stopping previous server PID=${OLD_PID}"
    kill "${OLD_PID}" >/dev/null 2>&1 || true
    sleep 1
  fi
  rm -f "${PID_FILE}"
fi

# start server
nohup uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --log-level info \
  > "${LOG_FILE}" 2>&1 &

NEW_PID="$!"
echo "${NEW_PID}" > "${PID_FILE}"
echo "PID=${NEW_PID}"
echo "LOG=${LOG_FILE}"

echo "[6/8] Wait for readiness: GET /health (fallback /healthz)"
READY=0
for i in {1..30}; do
  # /health preferred
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  # fallback /healthz (혹시 내부적으로 남아있으면)
  if curl -fsS "${BASE_URL}/healthz" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.3
done

if [[ "${READY}" -ne 1 ]]; then
  echo "❌ Server not ready. Tail logs:"
  tail -n 80 "${LOG_FILE}" || true
  echo
  echo "Stop: kill $(cat "${PID_FILE}" 2>/dev/null || echo "<PID>")"
  exit 1
fi

echo "✅ Health OK"
curl -sS -i "${BASE_URL}/health" | head -n 5 || true

echo "[7/8] Smoke run: POST /ai/agent/run (use tmp_uploads samples)"
BASE_FILE="$(ls ./tmp_uploads/*baseline*spikeScenario*.xlsx 2>/dev/null | head -n 1 || true)"
CURR_FILE="$(ls ./tmp_uploads/*current_spike_1012_1019*.xlsx 2>/dev/null | head -n 1 || true)"
ISO_FILE="$(ls ./tmp_uploads/*ISO*45001*.pdf 2>/dev/null | head -n 1 || true)"

if [[ -z "${BASE_FILE}" || -z "${CURR_FILE}" || -z "${ISO_FILE}" ]]; then
  echo "❗ sample files not found in ./tmp_uploads"
  echo "   expected:"
  echo "   - *baseline*spikeScenario*.xlsx"
  echo "   - *current_spike_1012_1019*.xlsx"
  echo "   - *ISO*45001*.pdf"
  echo "Open docs: ${BASE_URL}/docs"
  echo "Stop: kill $(cat "${PID_FILE}")"
  exit 0
fi

DRAFT_ID="day5_smoke_$(date +%m%d_%H%M%S)"
OUT_JSON="/tmp/esg_day5_${DRAFT_ID}.json"

echo "Draft: ${DRAFT_ID}"
curl -sS -X POST "${BASE_URL}/ai/agent/run" \
  -F "draft_id=${DRAFT_ID}" \
  -F "files=@${BASE_FILE}" \
  -F "files=@${CURR_FILE}" \
  -F "files=@${ISO_FILE}" \
  | tee "${OUT_JSON}" \
  | python -m json.tool >/dev/null

echo "Run OK. Saved: ${OUT_JSON}"
echo "[8/8] Useful links"
echo "- Docs:    ${BASE_URL}/docs"
echo "- OpenAPI: ${BASE_URL}/openapi.json"
echo "- Logs:    ${LOG_FILE}"
echo "- Stop:    kill $(cat "${PID_FILE}")"