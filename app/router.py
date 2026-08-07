from .classifier import CONFIDENCE_THRESHOLD, classify
from .guard import check_pii, check_prompt_injection
from .llm_client import LLMClient, MockLLM
from .models import Ticket, TicketResult
from .rag import retrieve
from .storage import save_result, tickets_db

RISKY_CATEGORIES = {"billing_refund", "account_access", "abuse_or_complaint"}

# Canned-ответы для категорий, где допустим автоответ, но LLM недоступен —
# позволяют деградировать без немедленной эскалации всего трафика.
CANNED_RESPONSES = {
    "order_status": "Мы получили ваш запрос о статусе заказа и ответим в ближайшее время.",
}


def handle_ticket(ticket: Ticket, llm: LLMClient | None = None) -> TicketResult:
    if ticket.ticket_id in tickets_db:
        return tickets_db[ticket.ticket_id]  # идемпотентность: не переобрабатываем повтор

    llm = llm or MockLLM()
    pii_flags = check_pii(ticket.text)
    injection_flags = check_prompt_injection(ticket.text)
    category, confidence = classify(ticket.text)
    flags = pii_flags + injection_flags

    risky = (
        category in RISKY_CATEGORIES
        or bool(pii_flags)
        or bool(injection_flags)
        or confidence < CONFIDENCE_THRESHOLD
    )

    if risky:
        reason = (
            "risky_category" if category in RISKY_CATEGORIES else
            "pii_detected" if pii_flags else
            "prompt_injection" if injection_flags else
            "low_confidence"
        )
        result = TicketResult(
            ticket_id=ticket.ticket_id,
            category=category,
            confidence=confidence,
            path="escalated",
            response=None,
            escalation_reason=reason,
            flags=flags,
        )
        save_result(result, reason=reason)
        return result

    _, doc_text, _ = retrieve(ticket.text)
    try:
        response = llm.generate(ticket.text, doc_text or "")
        result = TicketResult(
            ticket_id=ticket.ticket_id,
            category=category,
            confidence=confidence,
            path="auto_reply",
            response=response,
            flags=flags,
        )
        save_result(result)
        return result
    except TimeoutError:
        canned = CANNED_RESPONSES.get(category)
        if canned:
            result = TicketResult(
                ticket_id=ticket.ticket_id,
                category=category,
                confidence=confidence,
                path="auto_reply",
                response=canned,
                flags=flags,
            )
            save_result(result, reason="llm_unavailable_canned")
        else:
            result = TicketResult(
                ticket_id=ticket.ticket_id,
                category=category,
                confidence=confidence,
                path="escalated",
                response=None,
                escalation_reason="llm_unavailable",
                flags=flags,
            )
            save_result(result, reason="llm_unavailable")
        return result
