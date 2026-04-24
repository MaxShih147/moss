"""Seed Systems store from historical assignee distribution.

Tickets store is backed directly by docs/Helpdesk.xlsx — no migration needed.
"""
import asyncio
from collections import Counter
from pathlib import Path

import pandas as pd

from store import MockSystemStore, MockTicketStore, SystemEntry

ROOT = Path(__file__).resolve().parent.parent


CORE_SYSTEMS = {
    "Outlook": "軟體",
    "ERP": "軟體",
    "BPM": "軟體",
    "NAS": "網路",
    "VPN": "網路",
    "Teams": "軟體",
    "M365": "軟體",
    "OneDrive": "軟體",
    "Email": "軟體",
    "印表機": "硬體",
    "電腦": "硬體",
    "Microsoft": "軟體",
    "防毒軟體": "軟體",
}

DEFAULT_BACKUPS = {
    "Leny": "Jasam",
    "Jasam": "Leny",
    "Danny": "Leny",
    "Wade": "Leny",
}


def normalize_assignee(raw) -> str:
    s = str(raw or "").strip()
    if s.lower() == "danny":
        return "Danny"
    if s in ("X", "", "nan"):
        return ""
    return s


async def main():
    store = MockTicketStore()
    all_tickets = await store.list_all()

    assignees_by_system: dict[str, list[str]] = {}
    for t in all_tickets:
        sys_name = t.system
        a = normalize_assignee(t.assignee)
        if not a:
            continue
        assignees_by_system.setdefault(sys_name, []).append(a)

    entries: list[SystemEntry] = []
    for sys_title, category in CORE_SYSTEMS.items():
        assignees = assignees_by_system.get(sys_title, [])
        primary = Counter(assignees).most_common(1)[0][0] if assignees else "Leny"
        backup = DEFAULT_BACKUPS.get(primary, "Jasam")
        entries.append(SystemEntry(
            title=sys_title,
            primary_owner=primary,
            backup_owner=backup,
            category=category,
            is_active=True,
        ))
    entries.sort(key=lambda e: e.title)

    sys_store = MockSystemStore()
    await sys_store.seed(entries)

    print(f"seeded {len(entries)} systems:")
    for s in entries:
        print(f"  {s.title:12s} [{s.category}]  primary={s.primary_owner:10s} backup={s.backup_owner}")
    print(f"\ntickets backing file: {store.path}")
    print(f"current total tickets: {len(all_tickets)}")


if __name__ == "__main__":
    asyncio.run(main())
