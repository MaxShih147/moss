#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/teams-app"
OUT="$ROOT/teams-app/danny-bot.zip"

if [ ! -f "$APP_DIR/color.png" ] || [ ! -f "$APP_DIR/outline.png" ]; then
    echo "icons 不存在，先產生..."
    source "$ROOT/.venv/bin/activate"
    python "$APP_DIR/generate_icons.py"
fi

cd "$APP_DIR"
rm -f danny-bot.zip
zip -j danny-bot.zip manifest.json color.png outline.png

echo
echo "==> 輸出: $OUT"
unzip -l "$OUT"
