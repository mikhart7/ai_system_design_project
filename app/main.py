from fastapi import FastAPI, HTTPException

from .models import Ticket, TicketResult
from .router import handle_ticket
from .storage import escalation_queue, tickets_db

app = FastAPI(title="Support Ticket Automation PoC")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets", response_model=TicketResult)
def create_ticket(ticket: Ticket):
    return handle_ticket(ticket)


@app.get("/tickets/{ticket_id}", response_model=TicketResult)
def get_ticket(ticket_id: str):
    if ticket_id not in tickets_db:
        raise HTTPException(status_code=404, detail="ticket not found")
    return tickets_db[ticket_id]


@app.get("/escalations")
def get_escalations():
    return escalation_queue
