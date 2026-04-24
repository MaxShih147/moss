import asyncio
import os
import sys
import traceback

from aiohttp import web
from dotenv import load_dotenv

from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity

from admin import create_admin_app
from bot import DannyBot
from llm import OpenAIProvider
from store import MockSystemStore, MockTicketStore

load_dotenv()

SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.getenv("MicrosoftAppId", ""),
    app_password=os.getenv("MicrosoftAppPassword", ""),
    channel_auth_tenant=os.getenv("MicrosoftAppTenantId") or None,
)
ADAPTER = BotFrameworkAdapter(SETTINGS)

TICKET_STORE = MockTicketStore()
SYSTEM_STORE = MockSystemStore()
LLM = OpenAIProvider()

BOT = DannyBot(ticket_store=TICKET_STORE, system_store=SYSTEM_STORE, llm=LLM)


async def on_error(context: TurnContext, error: Exception):
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("Sorry, something went wrong.")


ADAPTER.on_turn_error = on_error


async def messages(req: web.Request) -> web.Response:
    if "application/json" not in req.content_type:
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=201)


BOT_APP = web.Application()
BOT_APP.router.add_post("/api/messages", messages)

ADMIN_APP = create_admin_app(
    ticket_store=TICKET_STORE,
    system_store=SYSTEM_STORE,
    llm=LLM,
)


async def start_servers():
    bot_port = int(os.getenv("PORT", 3978))
    admin_port = int(os.getenv("ADMIN_PORT", 8765))

    bot_runner = web.AppRunner(BOT_APP)
    await bot_runner.setup()
    bot_site = web.TCPSite(bot_runner, "0.0.0.0", bot_port)
    await bot_site.start()
    print(f"Danny Bot  listening on 0.0.0.0:{bot_port}")

    admin_runner = web.AppRunner(ADMIN_APP)
    await admin_runner.setup()
    admin_site = web.TCPSite(admin_runner, "127.0.0.1", admin_port)
    await admin_site.start()
    print(f"Admin Web  listening on http://127.0.0.1:{admin_port}")


async def main():
    await start_servers()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
