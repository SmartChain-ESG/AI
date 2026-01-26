set -e

BASE="http://127.0.0.1:8000"
DRAFT="test_draft_001"

echo "[1] run: 2025 only"
RUN1=$(curl -s -X POST "$BASE/ai/agent/run" \
  -F "draft_id=$DRAFT" \
  -F "files=@./tmp_uploads/002b838a94ff_E_electricity_usage_Q4_2025_current_spike_1012_1019.xlsx" \
  | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "RUN1=$RUN1"

echo "[2] run: 2024 + 2025"
RUN2=$(curl -s -X POST "$BASE/ai/agent/run" \
  -F "draft_id=$DRAFT" \
  -F "files=@./tmp_uploads/2886dcf62a00_E_electricity_usage_Q4_2024_baseline_spikeScenario.xlsx" \
  -F "files=@./tmp_uploads/002b838a94ff_E_electricity_usage_Q4_2025_current_spike_1012_1019.xlsx" \
  | python -c "import sys,json; print(json.load(sys.stdin)['run_id'])")
echo "RUN2=$RUN2"

echo "[3] latest run_id"
curl -s "$BASE/ai/drafts/$DRAFT/latest" \
  | python -c "import sys,json; print('LATEST=', json.load(sys.stdin)['run_id'])"

echo "[4] latest resubmit_diff"
curl -s "$BASE/ai/drafts/$DRAFT/latest" \
  | python -c "import sys,json; print(json.dumps(json.load(sys.stdin)['resubmit_diff'], ensure_ascii=False, indent=2))"
