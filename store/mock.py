"""Mock stores backed directly by xlsx files (developing against real data)."""
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .base import SystemEntry, SystemStore, Ticket, TicketStatus, TicketStore

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "_data"
DATA_DIR.mkdir(exist_ok=True)

SYSTEMS_FILE = DATA_DIR / "systems.xlsx"
TICKETS_FILE = ROOT / "docs" / "Helpdesk.xlsx"

SYSTEM_COLS = ["title", "primary_owner", "backup_owner", "category", "is_active"]

COL_ID = "Id"
COL_START = "開始時間"
COL_COMPLETED = "完成時間"
COL_USER = "User"
COL_SYSTEM = "系統\xa0 System"
COL_QUESTION = "問題\xa0 Question"
COL_ASSIGN = "分配"
COL_OLD_STATUS = "完成狀況"
COL_REPLY = "回覆"
COL_EMAIL = "電子郵件"
COL_TITLE = "Title"
COL_STATUS = "Status"
COL_RESOLUTION = "Resolution"
COL_SOURCE = "Source"
COL_LAST_MOD = "LastModified"

TICKET_COLS_ORDERED = [
    COL_ID, COL_START, COL_COMPLETED, COL_USER, "工號\xa0 WorkID",
    COL_SYSTEM, COL_QUESTION, "附件", COL_ASSIGN, COL_OLD_STATUS,
    "完成日", "未完成天數", COL_REPLY, COL_EMAIL,
    COL_TITLE, COL_STATUS, COL_RESOLUTION, COL_SOURCE, COL_LAST_MOD,
]

EXTENSION_COLS = [COL_TITLE, COL_STATUS, COL_RESOLUTION, COL_SOURCE, COL_LAST_MOD]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _s(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    return str(v)


class MockSystemStore(SystemStore):

    def __init__(self, path: Path = SYSTEMS_FILE):
        self.path = path
        self._lock = asyncio.Lock()
        if not self.path.exists():
            pd.DataFrame({c: pd.Series(dtype="object") for c in SYSTEM_COLS}).to_excel(self.path, index=False)

    def _read(self) -> pd.DataFrame:
        df = pd.read_excel(self.path)
        for c in SYSTEM_COLS:
            if c not in df.columns:
                df[c] = None
        return df[SYSTEM_COLS]

    def _write(self, df: pd.DataFrame) -> None:
        df.to_excel(self.path, index=False)

    def _row_to_entry(self, r) -> SystemEntry:
        return SystemEntry(
            title=_s(r["title"]),
            primary_owner=_s(r["primary_owner"]),
            backup_owner=_s(r["backup_owner"]),
            category=_s(r["category"]),
            is_active=(True if pd.isna(r["is_active"]) else bool(r["is_active"])),
        )

    async def get(self, system_title: str) -> Optional[SystemEntry]:
        async with self._lock:
            df = self._read()
            for _, r in df.iterrows():
                if _s(r["title"]).lower() == system_title.lower() and (pd.isna(r["is_active"]) or bool(r["is_active"])):
                    return self._row_to_entry(r)
        return None

    async def list_all(self) -> List[SystemEntry]:
        async with self._lock:
            df = self._read()
            return [self._row_to_entry(r) for _, r in df.iterrows() if pd.isna(r["is_active"]) or bool(r["is_active"])]

    async def seed(self, entries: List[SystemEntry]) -> None:
        async with self._lock:
            df = pd.DataFrame([asdict(e) for e in entries], columns=SYSTEM_COLS)
            self._write(df)


class MockTicketStore(TicketStore):
    """Backed by docs/Helpdesk.xlsx directly (the real Phrozen data).

    Reads/writes in-place. Extension columns (Status/Resolution/Source/Title/
    LastModified) are added on first write if missing.
    """

    def __init__(self, path: Path = TICKETS_FILE):
        self.path = path
        self._lock = asyncio.Lock()
        if not self.path.exists():
            raise FileNotFoundError(f"{path} 不存在，請先放入 Helpdesk.xlsx")

    def _read(self) -> pd.DataFrame:
        df = pd.read_excel(self.path)
        for c in EXTENSION_COLS:
            if c not in df.columns:
                df[c] = ""
        for c in EXTENSION_COLS:
            df[c] = df[c].astype(object)
        return df

    def _write(self, df: pd.DataFrame) -> None:
        existing = set(df.columns)
        ordered = [c for c in TICKET_COLS_ORDERED if c in existing]
        leftover = [c for c in df.columns if c not in ordered]
        df = df[ordered + leftover]
        df.to_excel(self.path, index=False)

    def _row_to_ticket(self, r) -> Ticket:
        status_raw = _s(r.get(COL_STATUS))
        if not status_raw:
            status_raw = TicketStatus.DONE.value if _s(r.get(COL_OLD_STATUS)).lower() == "v" else TicketStatus.NEW.value
        source = _s(r.get(COL_SOURCE)) or "Manual"
        title = _s(r.get(COL_TITLE)) or f"[{_s(r.get(COL_SYSTEM))}] {_s(r.get(COL_QUESTION))[:40]}"
        try:
            ticket_id = int(r[COL_ID])
        except (TypeError, ValueError):
            ticket_id = 0
        return Ticket(
            id=ticket_id,
            title=title,
            requester=_s(r.get(COL_USER)),
            requester_email=_s(r.get(COL_EMAIL)),
            system=_s(r.get(COL_SYSTEM)),
            description=_s(r.get(COL_QUESTION)),
            source=source,
            status=TicketStatus(status_raw),
            assignee=_s(r.get(COL_ASSIGN)),
            reply=_s(r.get(COL_REPLY)),
            resolution=_s(r.get(COL_RESOLUTION)),
            created_at=_s(r.get(COL_START)),
            completed_at=_s(r.get(COL_COMPLETED)),
        )

    def _ticket_to_row(self, t: Ticket) -> dict:
        return {
            COL_ID: t.id,
            COL_START: t.created_at,
            COL_COMPLETED: t.completed_at,
            COL_USER: t.requester,
            COL_SYSTEM: t.system,
            COL_QUESTION: t.description,
            COL_ASSIGN: t.assignee,
            COL_OLD_STATUS: "V" if t.status == TicketStatus.DONE else "",
            COL_REPLY: t.reply,
            COL_EMAIL: t.requester_email,
            COL_TITLE: t.title,
            COL_STATUS: t.status.value,
            COL_RESOLUTION: t.resolution,
            COL_SOURCE: t.source,
            COL_LAST_MOD: _now(),
        }

    async def create(self, ticket: Ticket) -> Ticket:
        async with self._lock:
            df = self._read()
            next_id = int(pd.to_numeric(df[COL_ID], errors="coerce").max() or 0) + 1 if len(df) else 1
            ticket.id = next_id
            ticket.created_at = ticket.created_at or _now()
            if not ticket.title:
                ticket.title = f"[{ticket.system}] {ticket.description[:40]}"
            df = pd.concat([df, pd.DataFrame([self._ticket_to_row(ticket)])], ignore_index=True)
            self._write(df)
            return ticket

    async def get(self, ticket_id: int) -> Optional[Ticket]:
        async with self._lock:
            df = self._read()
            match = df[pd.to_numeric(df[COL_ID], errors="coerce") == ticket_id]
            if len(match):
                return self._row_to_ticket(match.iloc[0])
        return None

    async def update(self, ticket_id: int, **fields) -> Ticket:
        async with self._lock:
            df = self._read()
            idx = df.index[pd.to_numeric(df[COL_ID], errors="coerce") == ticket_id]
            if len(idx) == 0:
                raise KeyError(f"ticket {ticket_id} not found")
            i = idx[0]
            field_to_col = {
                "status": COL_STATUS,
                "assignee": COL_ASSIGN,
                "reply": COL_REPLY,
                "resolution": COL_RESOLUTION,
                "title": COL_TITLE,
                "description": COL_QUESTION,
                "requester": COL_USER,
                "requester_email": COL_EMAIL,
                "system": COL_SYSTEM,
                "source": COL_SOURCE,
                "completed_at": COL_COMPLETED,
            }
            for k, v in fields.items():
                if isinstance(v, TicketStatus):
                    v = v.value
                col = field_to_col.get(k, k)
                df.at[i, col] = v
            if fields.get("status") in (TicketStatus.DONE, TicketStatus.DONE.value):
                if pd.isna(df.at[i, COL_COMPLETED]) or not _s(df.at[i, COL_COMPLETED]):
                    df.at[i, COL_COMPLETED] = _now()
                df.at[i, COL_OLD_STATUS] = "V"
            df.at[i, COL_LAST_MOD] = _now()
            self._write(df)
            return self._row_to_ticket(df.iloc[i])

    async def list_by_requester(self, email: str) -> List[Ticket]:
        async with self._lock:
            df = self._read()
            match = df[df[COL_EMAIL].astype(str).str.lower() == email.lower()]
            return [self._row_to_ticket(r) for _, r in match.iterrows()]

    async def list_modified_after(self, cursor: str) -> List[Ticket]:
        async with self._lock:
            df = self._read()
            match = df[df[COL_LAST_MOD].astype(str) > cursor]
            return [self._row_to_ticket(r) for _, r in match.iterrows()]

    async def list_all(self) -> List[Ticket]:
        async with self._lock:
            df = self._read()
            return [self._row_to_ticket(r) for _, r in df.iterrows()]

    async def bulk_insert(self, tickets: List[Ticket]) -> None:
        async with self._lock:
            df = self._read()
            next_id = int(pd.to_numeric(df[COL_ID], errors="coerce").max() or 0) + 1 if len(df) else 1
            rows = []
            for t in tickets:
                if not t.id:
                    t.id = next_id
                    next_id += 1
                if not t.created_at:
                    t.created_at = _now()
                if not t.title:
                    t.title = f"[{t.system}] {t.description[:40]}"
                rows.append(self._ticket_to_row(t))
            df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
            self._write(df)
