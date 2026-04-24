from dataclasses import dataclass, field
from typing import Optional

from store import SystemStore, Ticket, TicketStatus, TicketStore

CREATE_KEYWORDS = ("開單", "建單", "開工單", "報修", "申請工單", "/新單", "/open")
QUERY_KEYWORDS = ("我的單", "我的工單", "/我的單", "查單", "/查單", "ticket 進度", "工單進度")


def detect_intent(text: str) -> str:
    t = (text or "").strip().lower()
    for kw in CREATE_KEYWORDS:
        if kw.lower() in t:
            return "create"
    for kw in QUERY_KEYWORDS:
        if kw.lower() in t:
            return "query"
    return "chat"


@dataclass
class DialogState:
    step: str = "idle"
    pending_system: Optional[str] = None
    pending_description: Optional[str] = None


class CreateTicketDialog:

    def __init__(self, ticket_store: TicketStore, system_store: SystemStore):
        self.tickets = ticket_store
        self.systems = system_store
        self.states: dict[str, DialogState] = {}

    def state_for(self, user_id: str) -> DialogState:
        return self.states.setdefault(user_id, DialogState())

    def reset(self, user_id: str) -> None:
        self.states.pop(user_id, None)

    async def start(self, user_id: str) -> str:
        systems = await self.systems.list_all()
        names = "、".join(s.title for s in systems)
        self.states[user_id] = DialogState(step="awaiting_system")
        return f"好的，幫您開工單。請問是哪個系統？\n\n常見類別：{names}\n\n（也可以直接輸入其他類別名稱）"

    async def handle(self, user_id: str, text: str, requester_name: str, requester_email: str) -> Optional[str]:
        state = self.state_for(user_id)
        text = (text or "").strip()

        if state.step == "idle":
            return None

        if text.lower() in ("取消", "/cancel", "cancel"):
            self.reset(user_id)
            return "已取消開單流程。"

        if state.step == "awaiting_system":
            state.pending_system = text
            state.step = "awaiting_description"
            return f"系統類別：{text} ✓\n\n請描述問題（1-2 句即可）："

        if state.step == "awaiting_description":
            state.pending_description = text
            state.step = "awaiting_confirm"
            return (
                f"請確認：\n\n"
                f"系統：{state.pending_system}\n"
                f"問題：{state.pending_description}\n"
                f"報修人：{requester_name}\n\n"
                f"確認要建立工單嗎？（是 / 否）"
            )

        if state.step == "awaiting_confirm":
            if text in ("是", "yes", "好", "ok", "確認", "y"):
                sys_entry = await self.systems.get(state.pending_system)
                assignee = sys_entry.primary_owner if sys_entry else ""
                ticket = Ticket(
                    id=0,
                    title=f"[{state.pending_system}] {state.pending_description[:40]}",
                    requester=requester_name,
                    requester_email=requester_email,
                    system=state.pending_system,
                    description=state.pending_description,
                    source="Bot",
                    status=TicketStatus.ASSIGNED if assignee else TicketStatus.NEW,
                    assignee=assignee,
                )
                created = await self.tickets.create(ticket)
                self.reset(user_id)
                owner_line = f"負責人：{assignee}" if assignee else "尚未指派"
                return (
                    f"工單 #{created.id} 已建立 ✓\n\n"
                    f"類別：{state.pending_system or created.system}\n"
                    f"{owner_line}\n"
                    f"狀態：{created.status.value}\n\n"
                    f"可隨時輸入「我的單」查詢進度。"
                )
            else:
                self.reset(user_id)
                return "已取消開單流程。"

        return None
