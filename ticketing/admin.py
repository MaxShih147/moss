from typing import Optional

from store import Ticket, TicketStatus, TicketStore

HELP_TEXT = """**可用指令**

員工：
- 直接問問題 — 我會用歷史工單回答
- `開單` — 建立工單
- `我的單` — 查你的工單

IT 端：
- `/list` — 列進行中的單
- `/list new|assigned|inprogress|done` — 依狀態篩選
- `/list mine` — 只看派給我的單
- `/assign <id> <人名>` — 指派／改指派
- `/reply <id> <訊息>` — 加處理紀錄
- `/close <id>` — 結案並自動 AI 摘要
- `/help` — 顯示本說明"""


STATUS_FILTERS = {
    "new": TicketStatus.NEW,
    "assigned": TicketStatus.ASSIGNED,
    "inprogress": TicketStatus.IN_PROGRESS,
    "in_progress": TicketStatus.IN_PROGRESS,
    "done": TicketStatus.DONE,
    "rejected": TicketStatus.REJECTED,
}


def _render(tickets: list[Ticket], limit: int = 20) -> str:
    if not tickets:
        return "（無符合條件的工單）"
    lines = [f"（共 {len(tickets)} 張，顯示前 {min(limit, len(tickets))}）"]
    for t in tickets[:limit]:
        owner = t.assignee or "未指派"
        lines.append(f"#{t.id} [{t.system}] {t.description[:35]}  → {owner} ({t.status.value})")
    return "\n".join(lines)


async def list_tickets(store: TicketStore, filter_arg: str, caller_name: str) -> str:
    arg = (filter_arg or "").strip().lower()
    all_t = await store.list_all()

    if arg == "mine":
        filtered = [t for t in all_t if t.assignee.lower() == caller_name.lower()]
        filtered.sort(key=lambda t: (t.status != TicketStatus.NEW, t.status != TicketStatus.ASSIGNED, -t.id))
        return f"**派給 {caller_name} 的工單**\n" + _render(filtered)

    if arg == "all":
        all_t.sort(key=lambda t: -t.id)
        return _render(all_t, limit=30)

    if arg in STATUS_FILTERS:
        status = STATUS_FILTERS[arg]
        filtered = [t for t in all_t if t.status == status]
        filtered.sort(key=lambda t: -t.id)
        return f"**狀態={status.value}**\n" + _render(filtered)

    active = [t for t in all_t if t.status in (TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS)]
    active.sort(key=lambda t: -t.id)
    return "**進行中的工單**\n" + _render(active)


async def assign_ticket(store: TicketStore, ticket_id: int, assignee: str) -> str:
    assignee = assignee.strip()
    if not assignee:
        return "指派對象不可為空"
    ticket = await store.get(ticket_id)
    if ticket is None:
        return f"工單 #{ticket_id} 不存在"
    old = ticket.assignee or "未指派"
    new_status = TicketStatus.ASSIGNED if ticket.status == TicketStatus.NEW else ticket.status
    await store.update(ticket_id, assignee=assignee, status=new_status)
    return f"工單 #{ticket_id} 指派：{old} → **{assignee}** ✓"


async def add_reply(store: TicketStore, ticket_id: int, text: str) -> str:
    text = text.strip()
    if not text:
        return "處理紀錄內容不可為空"
    ticket = await store.get(ticket_id)
    if ticket is None:
        return f"工單 #{ticket_id} 不存在"
    existing = ticket.reply or ""
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    new_reply = (existing + f"\n[{stamp}] {text}").strip()
    new_status = TicketStatus.IN_PROGRESS if ticket.status in (TicketStatus.NEW, TicketStatus.ASSIGNED) else ticket.status
    await store.update(ticket_id, reply=new_reply, status=new_status)
    return f"工單 #{ticket_id} 已加處理紀錄 ✓（狀態：{new_status.value}）"
