from pathlib import Path

import aiohttp_jinja2
import jinja2
from aiohttp import web

from llm import OpenAIProvider
from store import MockSystemStore, MockTicketStore

from .handlers import (
    get_systems,
    get_ticket_detail,
    get_tickets,
    post_close,
    post_system_update,
    post_ticket_update,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def create_admin_app(
    ticket_store: MockTicketStore = None,
    system_store: MockSystemStore = None,
    llm: OpenAIProvider = None,
) -> web.Application:
    app = web.Application()
    app["ticket_store"] = ticket_store or MockTicketStore()
    app["system_store"] = system_store or MockSystemStore()
    app["llm"] = llm or OpenAIProvider()

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)))

    app.router.add_get("/", lambda r: web.HTTPFound("/tickets"))
    app.router.add_get("/tickets", get_tickets)
    app.router.add_get("/tickets/{ticket_id}", get_ticket_detail)
    app.router.add_post("/tickets/{ticket_id}/update", post_ticket_update)
    app.router.add_post("/tickets/{ticket_id}/close", post_close)
    app.router.add_get("/systems", get_systems)
    app.router.add_post("/systems/update", post_system_update)

    return app


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    web.run_app(create_admin_app(), host="127.0.0.1", port=8000)
