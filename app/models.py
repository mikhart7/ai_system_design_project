from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Ticket(BaseModel):
    ticket_id: str
    customer_id: str
    channel: str  # chat | email | web | app
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TicketResult(BaseModel):
    ticket_id: str
    category: str
    confidence: float
    path: str  # "auto_reply" | "escalated"
    response: Optional[str] = None
    escalation_reason: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
