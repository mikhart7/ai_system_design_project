"""Демо-сценарий: happy path, risky path и деградация при недоступности LLM.
Запуск: сервер должен быть поднят (`uvicorn app.main:app`), затем `python scripts/demo.py`.
"""
import httpx

BASE_URL = "http://localhost:8000"

CASES = [
    ("happy path", "demo-happy", "когда приедет мой заказ?", False),
    ("risky path (эскалация)", "demo-risky", "верните деньги, спишите оплату обратно", False),
    ("LLM недоступен (деградация)", "demo-llm-fallback", "не могу отследить свой заказ", True),
]


def main() -> None:
    for label, ticket_id, text, simulate_failure in CASES:
        payload = {
            "ticket_id": ticket_id,
            "customer_id": "demo-customer",
            "channel": "chat",
            "text": text,
        }
        resp = httpx.post(
            f"{BASE_URL}/tickets",
            json=payload,
            params={"simulate_llm_failure": simulate_failure},
            timeout=5,
        )
        print(f"--- {label} ---")
        print(resp.json())
        print()

    print("--- escalation queue ---")
    print(httpx.get(f"{BASE_URL}/escalations", timeout=5).json())


if __name__ == "__main__":
    main()
