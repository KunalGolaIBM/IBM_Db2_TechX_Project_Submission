#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PAPERS_DIR="data/samples/papers"
mkdir -p "$PAPERS_DIR"

ATTENTION="$PAPERS_DIR/attention-is-all-you-need.pdf"
BERT="$PAPERS_DIR/bert-pre-training.pdf"

download() {
  local url="$1"
  local output="$2"
  if [[ -s "$output" ]]; then
    echo "Already exists: $output"
    return
  fi
  echo "Downloading $url"
  curl -L --fail --silent --show-error "$url" -o "$output"
}

download "https://arxiv.org/pdf/1706.03762v7" "$ATTENTION"
download "https://arxiv.org/pdf/1810.04805v2" "$BERT"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

"$PYTHON" database/seed_papers.py
