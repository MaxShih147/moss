import aiohttp_jinja2
from aiohttp import web

from store import SystemEntry, TicketStatus
from ticketing.summarize import close_and_summarize

STATUS_OPTIONS = [s.value for s in TicketStatus]


def _store(request: web.Request, key: str):
    return request.app[key]


@aiohttp_jinja2.template("tickets.html")
async def get_tickets(request: web.Request):
    ticket_store = _store(request, "ticket_store")
    system_store = _store(request, "system_store")

    status_filter = request.query.get("status", "active")
    assignee_filter = request.query.get("assignee", "")
    q = request.query.get("q", "").strip().lower()

    all_tickets = await ticket_store.list_all()
    tickets = all_tickets

    if status_filter == "active":
        active = {TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS}
        tickets = [t for t in tickets if t.status in active]
    elif status_filter and status_filter != "all":
        try:
            s = TicketStatus(status_filter)
            tickets = [t for t in tickets if t.status == s]
        except ValueError:
            pass

    if assignee_filter:
        tickets = [t for t in tickets if t.assignee == assignee_filter]

    if q:
        tickets = [t for t in tickets if q in t.description.lower() or q in t.system.lower() or q in t.title.lower()]

    tickets.sort(key=lambda t: (-t.id,))

    systems = await system_store.list_all()
    known_assignees = sorted({e.primary_owner for e in systems} | {e.backup_owner for e in systems if e.backup_owner})
    all_assignees = sorted({t.assignee for t in all_tickets if t.assignee} | set(known_assignees))

    stats = {
        "total": len(all_tickets),
        "new": sum(1 for t in all_tickets if t.status == TicketStatus.NEW),
        "assigned": sum(1 for t in all_tickets if t.status == TicketStatus.ASSIGNED),
        "in_progress": sum(1 for t in all_tickets if t.status == TicketStatus.IN_PROGRESS),
        "done": sum(1 for t in all_tickets if t.status == TicketStatus.DONE),
    }

    return {
        "tickets": tickets[:200],
        "status_filter": status_filter,
        "assignee_filter": assignee_filter,
        "q": q,
        "status_options": STATUS_OPTIONS,
        "assignee_options": all_assignees,
        "stats": stats,
        "total_shown": min(len(tickets), 200),
        "total_filtered": len(tickets),
    }


@aiohttp_jinja2.template("ticket_detail.html")
async def get_ticket_detail(request: web.Request):
    ticket_id = int(request.match_info["ticket_id"])
    ticket_store = _store(request, "ticket_store")
    system_store = _store(request, "system_store")

    ticket = await ticket_store.get(ticket_id)
    if ticket is None:
        raise web.HTTPNotFound(text=f"ticket {ticket_id} not found")

    systems = await system_store.list_all()
    known_assignees = sorted({e.primary_owner for e in systems} | {e.backup_owner for e in systems if e.backup_owner})

    return {
        "ticket": ticket,
        "status_options": STATUS_OPTIONS,
        "assignee_options": known_assignees,
    }


async def post_ticket_update(request: web.Request):
    ticket_id = int(request.match_info["ticket_id"])
    ticket_store = _store(request, "ticket_store")

    data = await request.post()
    updates = {}
    if "assignee" in data:
        updates["assignee"] = data.get("assignee", "").strip()
    if "status" in data:
        raw_status = data.get("status", "").strip()
        if raw_status:
            try:
                updates["status"] = TicketStatus(raw_status)
            except ValueError:
                pass
    reply_add = data.get("reply_add", "").strip()
    if reply_add:
        ticket = await ticket_store.get(ticket_id)
        existing = (ticket.reply or "") if ticket else ""
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        updates["reply"] = (existing + f"\n[{stamp}] {reply_add}").strip()

    if updates:
        await ticket_store.update(ticket_id, **updates)

    raise web.HTTPFound(f"/tickets/{ticket_id}")


async def post_close(request: web.Request):
    ticket_id = int(request.match_info["ticket_id"])
    ticket_store = _store(request, "ticket_store")
    llm = _store(request, "llm")
    try:
        await close_and_summarize(ticket_id, ticket_store, llm)
    except Exception:
        pass
    raise web.HTTPFound(f"/tickets/{ticket_id}")


@aiohttp_jinja2.template("systems.html")
async def get_systems(request: web.Request):
    system_store = _store(request, "system_store")
    systems = await system_store.list_all()
    systems.sort(key=lambda e: e.title)
    return {"systems": systems}


async def post_system_update(request: web.Request):
    system_store = _store(request, "system_store")
    data = await request.post()

    titles = data.getall("title")
    primary = data.getall("primary_owner")
    backup = data.getall("backup_owner")
    category = data.getall("category")

    entries = []
    for i in range(len(titles)):
        t = titles[i].strip()
        if not t:
            continue
        entries.append(SystemEntry(
            title=t,
            primary_owner=primary[i].strip() if i < len(primary) else "",
            backup_owner=backup[i].strip() if i < len(backup) else "",
            category=category[i].strip() if i < len(category) else "",
            is_active=True,
        ))

    await system_store.seed(entries)
    raise web.HTTPFound("/systems")
