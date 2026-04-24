from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TicketStatus(str, Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "InProgress"
    DONE = "Done"
    REJECTED = "Rejected"


@dataclass
class SystemEntry:
    title: str
    primary_owner: str
    backup_owner: str = ""
    category: str = ""
    is_active: bool = True


@dataclass
class Ticket:
    id: int
    title: str
    requester: str
    requester_email: str
    system: str
    description: str
    source: str = "Bot"
    status: TicketStatus = TicketStatus.NEW
    assignee: str = ""
    reply: str = ""
    resolution: str = ""
    created_at: str = ""
    completed_at: str = ""

    def text_for_embedding(self) -> str:
        parts = [f"[{self.system}] {self.description}"]
        if self.resolution:
            parts.append(f"處理方式: {self.resolution}")
        elif self.reply:
            parts.append(f"處理紀錄: {self.reply}")
        return "\n".join(parts)


class SystemStore(ABC):

    @abstractmethod
    async def get(self, system_title: str) -> Optional[SystemEntry]:
        ...

    @abstractmethod
    async def list_all(self) -> List[SystemEntry]:
        ...


class TicketStore(ABC):

    @abstractmethod
    async def create(self, ticket: Ticket) -> Ticket:
        ...

    @abstractmethod
    async def get(self, ticket_id: int) -> Optional[Ticket]:
        ...

    @abstractmethod
    async def update(self, ticket_id: int, **fields) -> Ticket:
        ...

    @abstractmethod
    async def list_by_requester(self, email: str) -> List[Ticket]:
        ...

    @abstractmethod
    async def list_modified_after(self, cursor: str) -> List[Ticket]:
        ...

    @abstractmethod
    async def list_all(self) -> List[Ticket]:
        ...
