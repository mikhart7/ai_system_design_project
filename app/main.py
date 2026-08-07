from fastapi import FastAPI, HTTPException

from .llm_client import get_llm_client
from .models import Ticket, TicketResult
from .router import handle_ticket
from .storage import escalation_queue, tickets_db

app = FastAPI(title="Support Ticket Automation PoC")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets", response_model=TicketResult)
def create_ticket(ticket: Ticket, simulate_llm_failure: bool = False):
    # simulate_llm_failure — только для демонстрации деградации (docs/architecture.md,
    # сценарий "LLM API недоступен"); в проде переключатель отсутствует.
    # get_llm_client() по умолчанию возвращает MockLLM (без внешних зависимостей);
    # LLM_PROVIDER=ollama в окружении переключает на реальную локальную модель (см. README).
    llm = get_llm_client(force_failure=simulate_llm_failure)
    return handle_ticket(ticket, llm=llm)


@app.get("/tickets/{ticket_id}", response_model=TicketResult)
def get_ticket(ticket_id: str):
    if ticket_id not in tickets_db:
        raise HTTPException(status_code=404, detail="ticket not found")
    return tickets_db[ticket_id]


@app.get("/escalations")
def get_escalations():
    return escalation_queue
