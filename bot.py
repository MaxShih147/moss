from botbuilder.core import ActivityHandler, TurnContext, MessageFactory

from llm import OpenAIProvider
from rag import HelpdeskRetriever

SYSTEM_PROMPT = """你是 Danny Bot，普羅森科技的 IT Helpdesk 助理，部署在 Microsoft Teams 上。

你的職責：
- 協助員工解決 IT 相關問題（Outlook、ERP、BPM、VPN、印表機、NAS 等）
- 優先依據「相關歷史工單」回答，這是真實處理過的紀錄
- 若歷史紀錄顯示問題曾轉交特定廠商／同事處理，明確告知使用者可能的處理路徑
- 如果歷史紀錄不相關，誠實說明並建議聯繫 IT 人員

回答規則：
- 用繁體中文回答
- 回答要簡潔實用，優先給出可執行的步驟
- 如果有 3 筆以上相似歷史工單，可以點出「這類問題過去通常由 X 處理」
- 不要編造歷史紀錄沒有的系統或流程
- 語氣親切專業"""


def format_context(hits):
    lines = []
    for i, h in enumerate(hits, 1):
        m = h["metadata"]
        line = f"{i}. [{m.get('system', '?')}] {m.get('question', '')}"
        if m.get("reply"):
            line += f" — 處理紀錄: {m['reply']}"
        if m.get("assignee"):
            line += f" （處理人: {m['assignee']}）"
        lines.append(line)
    return "\n".join(lines)


class DannyBot(ActivityHandler):

    def __init__(self):
        super().__init__()
        self.llm = OpenAIProvider()
        self.retriever = HelpdeskRetriever()

    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text or ""
        user_name = turn_context.activity.from_property.name or "User"

        try:
            hits = await self.retriever.search(user_text, k=5)
            context = format_context(hits)
            augmented = (
                f"[相關歷史工單]\n{context}\n\n"
                f"[用戶 {user_name} 問]\n{user_text}"
            )
            reply = await self.llm.chat(
                user_message=augmented,
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception as e:
            print(f"LLM/RAG error: {e}")
            reply = f"抱歉，我目前無法處理您的問題。請直接聯繫 IT 人員。\n\n（錯誤：{type(e).__name__}）"

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
