from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsInfo

from llm import OpenAIProvider
from rag import HelpdeskRetriever
from store import MockSystemStore, MockTicketStore
from ticketing import (
    CreateTicketDialog,
    HELP_TEXT,
    add_reply,
    assign_ticket,
    detect_intent,
    format_my_tickets,
    list_tickets,
)
from ticketing.summarize import close_and_summarize

SYSTEM_PROMPT = """你是 Danny Bot，普羅森科技的 IT Helpdesk 助理，部署在 Microsoft Teams 上。

你的職責：
- 協助員工解決 IT 相關問題（Outlook、ERP、BPM、VPN、印表機、NAS 等）
- 優先依據「相關歷史工單」回答，這是真實處理過的紀錄
- 若歷史紀錄顯示問題曾轉交特定廠商，明確告知使用者可能的處理路徑
- 在答案末尾，如果「當前負責人」欄位有值，一律用「這類問題目前由 X 負責」作為結尾
- 如果歷史紀錄不相關或不足，誠實說明並建議「您也可以輸入『開單』讓我幫您建立工單」

回答規則：
- 用繁體中文回答
- 回答要簡潔實用，優先給出可執行的步驟
- 不要編造歷史紀錄沒有的系統或流程
- 語氣親切專業"""


def format_context(hits, current_owner_by_system):
    lines = []
    for i, h in enumerate(hits, 1):
        m = h["metadata"]
        sys_name = m.get("system", "?")
        line = f"{i}. [{sys_name}] {m.get('question', '')}"
        if m.get("reply"):
            line += f" — 處理紀錄: {m['reply']}"
        if m.get("assignee"):
            line += f" （歷史處理人: {m['assignee']}）"
        lines.append(line)
    if current_owner_by_system:
        lines.append("")
        lines.append("當前負責人（以此為準）：")
        for s, owner in current_owner_by_system.items():
            lines.append(f"- {s}: {owner}")
    return "\n".join(lines)


class DannyBot(ActivityHandler):

    def __init__(self, ticket_store=None, system_store=None, llm=None):
        super().__init__()
        self.llm = llm or OpenAIProvider()
        self.retriever = HelpdeskRetriever()
        self.system_store = system_store or MockSystemStore()
        self.ticket_store = ticket_store or MockTicketStore()
        self.create_dialog = CreateTicketDialog(self.ticket_store, self.system_store)

    async def _get_user_info(self, turn_context: TurnContext):
        user_id = turn_context.activity.from_property.id
        name = turn_context.activity.from_property.name or "User"
        email = ""
        try:
            member = await TeamsInfo.get_member(turn_context, user_id)
            email = getattr(member, "email", "") or ""
        except Exception:
            pass
        return user_id, name, email

    async def _resolve_owners(self, hits):
        owners = {}
        seen = []
        for h in hits:
            sys_name = h["metadata"].get("system", "")
            if sys_name and sys_name not in owners:
                entry = await self.system_store.get(sys_name)
                if entry and entry.primary_owner:
                    owners[sys_name] = entry.primary_owner
                    seen.append(sys_name)
        return owners

    async def on_message_activity(self, turn_context: TurnContext):
        user_text = turn_context.activity.text or ""
        user_id, user_name, user_email = await self._get_user_info(turn_context)

        stripped = user_text.strip()
        if stripped.startswith("/"):
            reply = await self._handle_command(stripped, user_name)
            if reply is not None:
                await turn_context.send_activity(MessageFactory.text(reply))
                return

        state = self.create_dialog.state_for(user_id)
        if state.step != "idle":
            reply = await self.create_dialog.handle(user_id, user_text, user_name, user_email)
            if reply:
                await turn_context.send_activity(MessageFactory.text(reply))
                return

        intent = detect_intent(user_text)

        if intent == "create":
            reply = await self.create_dialog.start(user_id)
            await turn_context.send_activity(MessageFactory.text(reply))
            return

        if intent == "query":
            reply = await format_my_tickets(self.ticket_store, user_email)
            await turn_context.send_activity(MessageFactory.text(reply))
            return

        try:
            hits = await self.retriever.search(user_text, k=5)
            owners = await self._resolve_owners(hits)
            context = format_context(hits, owners)
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

    async def _handle_command(self, text: str, caller_name: str):
        parts = text.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "/help":
            return HELP_TEXT

        if cmd == "/list":
            arg = parts[1] if len(parts) >= 2 else ""
            return await list_tickets(self.ticket_store, arg, caller_name)

        if cmd == "/assign":
            if len(parts) < 3:
                return "用法：`/assign <工單id> <人名>`"
            try:
                tid = int(parts[1])
            except ValueError:
                return "工單 id 必須是數字"
            return await assign_ticket(self.ticket_store, tid, parts[2])

        if cmd == "/reply":
            if len(parts) < 3:
                return "用法：`/reply <工單id> <處理紀錄>`"
            try:
                tid = int(parts[1])
            except ValueError:
                return "工單 id 必須是數字"
            return await add_reply(self.ticket_store, tid, parts[2])

        if cmd == "/close":
            if len(parts) < 2:
                return "用法：`/close <工單id>`"
            try:
                tid = int(parts[1])
            except ValueError:
                return "工單 id 必須是數字"
            try:
                updated = await close_and_summarize(tid, self.ticket_store, self.llm)
                return f"工單 #{updated.id} 已結案 ✓\n\n處理方式：\n{updated.resolution}"
            except KeyError:
                return f"工單 #{tid} 不存在"
            except Exception as e:
                return f"結案失敗：{type(e).__name__}: {e}"

        return None

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                welcome = (
                    "你好！我是 **Danny Bot**，普羅森科技的 IT Helpdesk 助理。\n\n"
                    "你可以：\n"
                    "- 直接問我 IT 問題（例如：「Outlook 收不到信」）\n"
                    "- 輸入「**開單**」讓我幫你建立工單\n"
                    "- 輸入「**我的單**」查詢你的工單進度\n\n"
                    "有什麼我可以幫忙的嗎？"
                )
                await turn_context.send_activity(MessageFactory.text(welcome))
