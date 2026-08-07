from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_escalation_path_billing_refund():
    resp = client.post("/tickets", json={
        "ticket_id": "t-escalate-1",
        "customer_id": "c2",
        "channel": "email",
        "text": "верните деньги, спишите оплату обратно",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "escalated"
    assert body["response"] is None
    assert body["escalation_reason"] is not None
    assert "t-escalate-1" in client.get("/escalations").json()


def test_escalation_path_pii_detected():
    resp = client.post("/tickets", json={
        "ticket_id": "t-escalate-2",
        "customer_id": "c3",
        "channel": "web",
        "text": "мой email ivan@example.com, подскажите по сервису",
    })
    body = resp.json()
    assert body["path"] == "escalated"
    assert "email" in body["flags"]
