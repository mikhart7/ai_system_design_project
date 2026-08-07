from app.llm_client import MockLLM
from app.models import Ticket
from app.router import handle_ticket


def test_llm_fallback_does_not_crash_canned_response():
    ticket = Ticket(
        ticket_id="t-fallback-1",
        customer_id="c4",
        channel="web",
        text="где мой заказ, не могу отследить",
    )
    result = handle_ticket(ticket, llm=MockLLM(force_failure=True))
    assert result.path in {"auto_reply", "escalated"}
    if result.path == "auto_reply":
        assert result.response is not None  # canned-ответ для order_status
    else:
        assert result.escalation_reason == "llm_unavailable"


def test_idempotent_repeat_request_returns_same_result():
    ticket = Ticket(
        ticket_id="t-idempotent-1",
        customer_id="c5",
        channel="chat",
        text="статус доставки заказа",
    )
    first = handle_ticket(ticket)
    second = handle_ticket(ticket)
    assert first == second
