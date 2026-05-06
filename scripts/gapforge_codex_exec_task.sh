#!/usr/bin/env bash
set -euo pipefail

TASK_PACK=""
OUTPUTS_DIR=""
MODEL="${GAPFORGE_CODEX_MODEL:-gpt-5.4}"
TASK_ID=""
RUN_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --task-pack)
      TASK_PACK="${2:-}"
      shift 2
      ;;
    --outputs-dir)
      OUTPUTS_DIR="${2:-}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --run-id)
      RUN_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$TASK_PACK" || -z "$OUTPUTS_DIR" || -z "$MODEL" ]]; then
  echo "Usage: $0 --task-pack PATH --outputs-dir PATH --model MODEL [--task-id ID] [--run-id ID]" >&2
  exit 2
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI not found on PATH." >&2
  exit 127
fi

TASK_PACK="$(cd "$TASK_PACK" && pwd)"
mkdir -p "$OUTPUTS_DIR"

PROMPT_FILE="$TASK_PACK/CODEX_PROMPT.md"
if [[ ! -f "$PROMPT_FILE" ]]; then
  PROMPT_FILE="$TASK_PACK/TASK.md"
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  PROMPT_FILE="$TASK_PACK/CAMPAIGN_TASK.md"
fi
if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "No CODEX_PROMPT.md, TASK.md, or CAMPAIGN_TASK.md found in $TASK_PACK." >&2
  exit 2
fi

cat "$PROMPT_FILE" | codex exec \
  --model "$MODEL" \
  --cd "$TASK_PACK" \
  --sandbox workspace-write \
  -

echo "Codex task completed for task_id=${TASK_ID:-unknown} run_id=${RUN_ID:-none}."
echo "Expected outputs directory: $OUTPUTS_DIR"
