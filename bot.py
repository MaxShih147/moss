from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from llm import OpenAIProvider

SYSTEM_PROMPT = """你是 Danny Bot，普羅森科技的 IT Helpdesk 助理，部署在 Microsoft Teams 上。

你的職責：
- 協助員工解決 IT 相關問題（Outlook、ERP、BPM、VPN、印表機、NAS 等）
- 提供清楚的排錯步驟
- 如果問題需要現場處理（硬體故障、權限開通、帳號異常），告知使用者你會協助轉派給 IT 人員

回答規則：
- 用繁體中文回答
- 回答要簡潔實用，優先給出可執行的步驟
- 如果不確定，誠實說明並建議聯繫 IT 人員
- 不要編造不存在的系統或流程
- 語氣親切專業"""


class DannyBot(ActivityHandler):

    def __init__(self):
        super().__init__()
        self.llm = OpenAIProvider()

    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text or ""
        user_name = turn_context.activity.from_property.name or "User"

        try:
            reply = await self.llm.chat(
                user_message=f"[{user_name}]: {user_text}",
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"LLM error: {e}")
            reply = f"抱歉，我目前無法處理您的問題（LLM 連線異常）。請直接聯繫 IT 人員。\n\n（錯誤：{type(e).__name__}）"

        await turn_context.send_activity(MessageFactory.text(reply))

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome = (
                    "你好！我是 **Danny Bot**，普羅森科技的 IT Helpdesk 助理。\n\n"
                    "你可以問我：\n"
                    "- 「Outlook 收不到信」\n"
                    "- 「ERP 登入有問題」\n"
                    "- 「查詢我的報修進度」\n\n"
                    "有什麼我可以幫忙的嗎？"
                )
                await turn_context.send_activity(MessageFactory.text(welcome))
