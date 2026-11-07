#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEST="data/scifact"
ARCHIVE="${TMPDIR:-/tmp}/scifact-data.tar.gz"
URL="https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"

echo "SciFact is licensed CC BY-NC 2.0 and is not redistributed by AEGIS."
echo "Source: https://github.com/allenai/scifact"
echo "Archive: $URL"

if [[ -f "$DEST/corpus.jsonl" && -f "$DEST/claims_dev.jsonl" ]]; then
  echo "SciFact data already present in $DEST"
  exit 0
fi

mkdir -p "$DEST"
curl -L --fail --silent --show-error "$URL" -o "$ARCHIVE"
tar -xzf "$ARCHIVE" -C "$DEST" --strip-components=1
echo "Extracted SciFact data into $DEST"
ls -lh "$DEST"/corpus.jsonl "$DEST"/claims_dev.jsonl
