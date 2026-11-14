#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Activate Python virtual environment on Ubuntu
if [ -f "$HOME/ZERO/hf-venv/bin/activate" ]; then
    source "$HOME/ZERO/hf-venv/bin/activate"
fi

export PYTHONPATH="$HOME/ZERO/image-models/xkcd-artist-source/python/src:$DIR:$PYTHONPATH"
export COMIC_OUTPUT_DIR="$DIR/output"

echo "[ZERO Comic Service] Starting XKCD ONNX Comic Service on port 8002..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8002

