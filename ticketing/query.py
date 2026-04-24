from store import TicketStatus, TicketStore

ACTIVE = {TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS}


async def format_my_tickets(store: TicketStore, email: str) -> str:
    if not email:
        return "無法取得您的電子郵件，請在 Teams 中使用本機器人以便查詢。"
    tickets = await store.list_by_requester(email)
    active = [t for t in tickets if t.status in ACTIVE]
    done = [t for t in tickets if t.status == TicketStatus.DONE]

    if not tickets:
        return "您目前沒有任何工單紀錄。"

    lines = []
    if active:
        lines.append(f"**進行中的工單（{len(active)} 張）**")
        for t in active[:10]:
            owner = t.assignee or "未指派"
            lines.append(f"- #{t.id} [{t.system}] {t.description[:40]}  → {owner} ({t.status.value})")
    if done:
        lines.append(f"\n**已完成的工單（近期 5 張）**")
        for t in sorted(done, key=lambda x: x.completed_at, reverse=True)[:5]:
            lines.append(f"- #{t.id} [{t.system}] {t.description[:40]}  ✓")
    return "\n".join(lines)
