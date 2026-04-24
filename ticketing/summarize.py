from llm import OpenAIProvider
from store import Ticket, TicketStatus, TicketStore

SUMMARIZE_PROMPT = """你是 IT 工單整理助理。根據原始處理紀錄，寫一段精簡的「處理方式」（2-4 句繁中），讓未來遇到同樣問題的人能快速參考。

要求：
- 寫結論，不要流水帳
- 點出 root cause 和解法
- 若需聯絡廠商／同事，寫出來
- 若原始紀錄資訊不足，直接寫「處理紀錄不足，建議聯繫處理人了解細節」
"""


async def summarize_resolution(ticket: Ticket, llm: OpenAIProvider) -> str:
    if not ticket.reply:
        return "處理紀錄不足，建議聯繫處理人了解細節"
    user_msg = f"問題：{ticket.description}\n原始處理紀錄：{ticket.reply}"
    try:
        result = await llm.chat(user_message=user_msg, system_prompt=SUMMARIZE_PROMPT)
        return (result or "").strip()
    except Exception as e:
        return f"（AI 摘要失敗：{type(e).__name__}）"


async def close_and_summarize(ticket_id: int, store: TicketStore, llm: OpenAIProvider) -> Ticket:
    ticket = await store.get(ticket_id)
    if ticket is None:
        raise KeyError(f"ticket {ticket_id} not found")
    resolution = await summarize_resolution(ticket, llm)
    return await store.update(ticket_id, status=TicketStatus.DONE, resolution=resolution)
