"""Manually import rows from another xlsx into the ticket store.

Usage:
    python -m scripts.import_xlsx path/to/new_data.xlsx

Behavior:
- Reads target xlsx
- Merges by `Id` (existing ids are updated, new ids are appended)
- Writes back to docs/Helpdesk.xlsx via MockTicketStore
"""
import asyncio
import sys
from pathlib import Path

import pandas as pd

from store.mock import MockTicketStore, COL_ID


async def main(source_path: str):
    src = Path(source_path)
    if not src.exists():
        print(f"ERROR: {src} 不存在", file=sys.stderr)
        sys.exit(1)

    df_new = pd.read_excel(src)
    if COL_ID not in df_new.columns:
        print(f"ERROR: 來源 xlsx 需要有 `{COL_ID}` 欄位", file=sys.stderr)
        sys.exit(1)

    store = MockTicketStore()
    async with store._lock:
        df_cur = store._read()
        existing_ids = set(pd.to_numeric(df_cur[COL_ID], errors="coerce").dropna().astype(int).tolist())

        new_ids = set(pd.to_numeric(df_new[COL_ID], errors="coerce").dropna().astype(int).tolist())
        to_update = new_ids & existing_ids
        to_add = new_ids - existing_ids

        if to_update:
            for tid in to_update:
                new_row = df_new[pd.to_numeric(df_new[COL_ID], errors="coerce") == tid].iloc[0]
                cur_idx = df_cur.index[pd.to_numeric(df_cur[COL_ID], errors="coerce") == tid][0]
                for col in df_new.columns:
                    df_cur.at[cur_idx, col] = new_row[col]

        if to_add:
            new_rows = df_new[pd.to_numeric(df_new[COL_ID], errors="coerce").isin(to_add)]
            df_cur = pd.concat([df_cur, new_rows], ignore_index=True)

        store._write(df_cur)

    print(f"匯入完成：新增 {len(to_add)} 筆，更新 {len(to_update)} 筆")
    print(f"目前總筆數：{len(df_cur)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.import_xlsx <source.xlsx>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
