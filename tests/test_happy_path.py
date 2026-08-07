from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_happy_path_order_status():
    resp = client.post("/tickets", json={
        "ticket_id": "t-happy-1",
        "customer_id": "c1",
        "channel": "chat",
        "text": "когда приедет мой заказ?",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "auto_reply"
    assert body["response"] is not None
    assert body["category"] == "order_status"
