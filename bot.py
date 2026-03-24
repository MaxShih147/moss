from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import CardAction, ActionTypes, SuggestedActions


class DannyBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text or ""
        user_name = turn_context.activity.from_property.name or "User"

        # Phase 1: echo back + show we're alive
        reply = f"Hi {user_name}, you said: **{user_text}**\n\nI'm Danny Bot. I'm not smart yet, but I'm here."

        await turn_context.send_activity(MessageFactory.text(reply))

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome = (
                    "Hello! I'm **Danny Bot**, your IT Helpdesk assistant.\n\n"
                    "You can ask me things like:\n"
                    "- \"Outlook can't receive mail\"\n"
                    "- \"ERP login issue\"\n"
                    "- \"Check my ticket status\"\n\n"
                    "How can I help you today?"
                )
                await turn_context.send_activity(MessageFactory.text(welcome))
