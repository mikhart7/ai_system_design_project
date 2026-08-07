from typing import Dict, List, Optional

from .models import TicketResult

tickets_db: Dict[str, TicketResult] = {}
audit_log: List[dict] = []
escalation_queue: List[str] = []


def save_result(result: TicketResult, reason: Optional[str] = None) -> None:
    tickets_db[result.ticket_id] = result
    audit_log.append({
        "ticket_id": result.ticket_id,
        "category": result.category,
        "confidence": result.confidence,
        "path": result.path,
        "flags": result.flags,
        "reason": reason,
    })
    if result.path == "escalated":
        escalation_queue.append(result.ticket_id)
