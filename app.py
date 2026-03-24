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

from bot import DannyBot

load_dotenv()

SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.getenv("MicrosoftAppId", ""),
    app_password=os.getenv("MicrosoftAppPassword", ""),
)
ADAPTER = BotFrameworkAdapter(SETTINGS)


async def on_error(context: TurnContext, error: Exception):
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()
    await context.send_activity("Sorry, something went wrong.")


ADAPTER.on_turn_error = on_error

BOT = DannyBot()


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


APP = web.Application()
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3978))
    print(f"Danny Bot starting on port {port}")
    web.run_app(APP, host="0.0.0.0", port=port)
