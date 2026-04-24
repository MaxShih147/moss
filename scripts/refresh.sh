#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f "docs/Helpdesk.xlsx" ]; then
    echo "ERROR: docs/Helpdesk.xlsx 不存在" >&2
    echo "請先從 SharePoint 下載最新 Helpdesk.xlsx 放到 docs/ 底下" >&2
    exit 1
fi

source .venv/bin/activate

echo "==> [$(date '+%Y-%m-%d %H:%M:%S')] 重新清洗資料"
python -m data.ingest

echo
echo "==> [$(date '+%Y-%m-%d %H:%M:%S')] 重建向量索引"
python -m data.build_index

echo
echo "==> 完成 ✓"
