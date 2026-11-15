#!/bin/bash
# Double-click to start MiRG Chart Editor.
# The first start downloads Python and the parts it needs (about 2 GB); later starts take a few seconds.
cd "$(dirname "$0")" || exit 1
set -e
UV="$(command -v uv || true)"
if [ -z "$UV" ]; then
  if [ ! -x .tools/uv ] && [ ! -x .tools/bin/uv ]; then
    echo "Getting uv, the Python installer..."
    mkdir -p .tools
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$PWD/.tools" UV_NO_MODIFY_PATH=1 sh
  fi
  UV="$PWD/.tools/uv"; [ -x "$UV" ] || UV="$PWD/.tools/bin/uv"
fi
[ -x .venv/bin/python ] || "$UV" venv --python 3.12 .venv
echo "Checking the Python packages..."
"$UV" pip install --quiet --python .venv/bin/python -r requirements.txt
.venv/bin/python tools/get_models.py
PORT="${MIRG_PORT:-8651}"
[ -n "$MIRG_NO_BROWSER" ] || (sleep 4; open "http://localhost:$PORT/") &
echo "MiRG Chart Editor is running at http://localhost:$PORT/ . Keep this window open; close it to stop."
exec .venv/bin/python server.py "$PORT"
