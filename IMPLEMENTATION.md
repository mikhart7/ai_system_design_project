# IMPLEMENTATION.md — пошаговая инструкция реализации PoC

Сопровождает `PLAN.md` (что и почему). Здесь — конкретный код и команды, в порядке, повторяющем шаги/коммиты из `PLAN.md`. Копируется и адаптируется по ходу работы.

## 0. Окружение

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install fastapi uvicorn "pydantic>=2" scikit-learn pytest httpx
```

`requirements.txt`:
```
fastapi
uvicorn
pydantic>=2
scikit-learn
pytest
httpx
```

Структура пакета: `app/__init__.py` — пустой файл, чтобы `app` был пакетом (нужно для `uvicorn app.main:app` и относительных импортов).

## 1. models.py

```python
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
```

## 2. storage.py (in-memory: тикеты, audit-лог, очередь эскалаций)

```python
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
```

## 3. guard.py (PII / prompt injection эвристики)

```python
import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\- ]{7,}\d")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "system:",
    "you are now",
    "disregard the above",
    "забудь предыдущие инструкции",
]


def check_pii(text: str) -> list[str]:
    flags = []
    if EMAIL_RE.search(text):
        flags.append("email")
    if PHONE_RE.search(text):
        flags.append("phone")
    if CARD_RE.search(text):
        flags.append("card_number")
    return flags


def check_prompt_injection(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in INJECTION_PATTERNS if p in lowered]
```

## 3b. classifier.py (baseline: TF-IDF + cosine similarity к few-shot примерам)

```python
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

EXEMPLARS: dict[str, list[str]] = {
    "order_status": ["где мой заказ", "статус доставки", "когда придёт посылка"],
    "account_access": ["не могу войти в аккаунт", "забыл пароль", "заблокировали аккаунт"],
    "billing_refund": ["хочу вернуть деньги", "верните оплату", "списали деньги ошибочно"],
    "technical_bug": ["приложение вылетает", "ошибка при оплате", "не работает кнопка"],
    "abuse_or_complaint": ["оператор нахамил", "жалоба на сотрудника", "это возмутительно"],
    "other": ["у меня есть вопрос", "подскажите по сервису"],
}

CONFIDENCE_THRESHOLD = 0.35  # подобрать на data/eval/sample_tickets.jsonl, обосновать в docs/ml.md

_labels = [cat for cat, exs in EXEMPLARS.items() for _ in exs]
_corpus = [ex for exs in EXEMPLARS.values() for ex in exs]
_vectorizer = TfidfVectorizer().fit(_corpus)
_exemplar_vectors = _vectorizer.transform(_corpus)


def classify(text: str) -> tuple[str, float]:
    vec = _vectorizer.transform([text])
    sims = cosine_similarity(vec, _exemplar_vectors)[0]
    best_idx = int(np.argmax(sims))
    return _labels[best_idx], float(sims[best_idx])
```

## 4. rag.py (retrieval по FAQ, та же TF-IDF-механика)

```python
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

FAQ_DIR = Path(__file__).resolve().parent.parent / "data" / "faq"


def _load_faq() -> dict[str, str]:
    if not FAQ_DIR.exists():
        return {}
    return {p.stem: p.read_text(encoding="utf-8") for p in FAQ_DIR.glob("*.md")}


_docs = _load_faq()
_doc_ids = list(_docs.keys())
_vectorizer = TfidfVectorizer().fit(list(_docs.values()) or [" "])
_doc_vectors = _vectorizer.transform(list(_docs.values())) if _docs else None


def retrieve(text: str) -> tuple[str | None, str | None, float]:
    if not _docs:
        return None, None, 0.0
    vec = _vectorizer.transform([text])
    sims = cosine_similarity(vec, _doc_vectors)[0]
    best_idx = int(sims.argmax())
    return _doc_ids[best_idx], _docs[_doc_ids[best_idx]], float(sims[best_idx])
```

`data/faq/order_status.md` (пример, сделать ещё 2-4 таких файла под другие safe-категории):
```markdown
# Статус заказа
Проверить статус заказа можно в разделе "Мои заказы" в приложении.
Среднее время доставки — 2-4 дня в зависимости от региона.
```

`data/eval/sample_tickets.jsonl` (пример строк, всего сделать 15-20 под все категории и разные каналы):
```json
{"text": "когда приедет моя посылка?", "expected_category": "order_status"}
{"text": "не приходит смс код для входа", "expected_category": "account_access"}
{"text": "спишите деньги, хочу возврат за подписку", "expected_category": "billing_refund"}
```

## 5. llm_client.py (Mock + интерфейс под реального провайдера)

```python
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, ticket_text: str, context: str) -> str: ...


class MockLLM(LLMClient):
    """Детерминированный мок: не требует API-ключа, воспроизводим для проверяющего.
    force_failure имитирует недоступность LLM API для теста деградации."""

    def __init__(self, force_failure: bool = False):
        self.force_failure = force_failure

    def generate(self, ticket_text: str, context: str) -> str:
        if self.force_failure:
            raise TimeoutError("LLM API unavailable (simulated)")
        snippet = context.strip().splitlines()[0] if context else "см. базу знаний"
        return f"Спасибо за обращение. {snippet}"

# RealLLMClient(OpenAI/Anthropic) — не реализуется в PoC, только описывается в docs/architecture.md
# как design decision: тот же интерфейс LLMClient.generate(), подключается через DI в router.py.
```

## 6. router.py (решение: auto-reply vs escalate, идемпотентность, деградация)

```python
from .models import Ticket, TicketResult
from .guard import check_pii, check_prompt_injection
from .classifier import classify, CONFIDENCE_THRESHOLD
from .rag import retrieve
from .llm_client import LLMClient, MockLLM
from .storage import tickets_db, save_result

RISKY_CATEGORIES = {"billing_refund", "account_access", "abuse_or_complaint"}
CANNED_RESPONSES = {
    "order_status": "Мы получили ваш запрос о статусе заказа, ответим в ближайшее время.",
}


def handle_ticket(ticket: Ticket, llm: LLMClient | None = None) -> TicketResult:
    if ticket.ticket_id in tickets_db:          # идемпотентность
        return tickets_db[ticket.ticket_id]

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
            ticket_id=ticket.ticket_id, category=category, confidence=confidence,
            path="escalated", response=None, escalation_reason=reason, flags=flags,
        )
        save_result(result, reason=reason)
        return result

    _, doc_text, _ = retrieve(ticket.text)
    try:
        response = llm.generate(ticket.text, doc_text or "")
        result = TicketResult(
            ticket_id=ticket.ticket_id, category=category, confidence=confidence,
            path="auto_reply", response=response, flags=flags,
        )
        save_result(result)
        return result
    except TimeoutError:
        canned = CANNED_RESPONSES.get(category)
        if canned:
            result = TicketResult(
                ticket_id=ticket.ticket_id, category=category, confidence=confidence,
                path="auto_reply", response=canned, flags=flags,
            )
            save_result(result, reason="llm_unavailable_canned")
        else:
            result = TicketResult(
                ticket_id=ticket.ticket_id, category=category, confidence=confidence,
                path="escalated", response=None, escalation_reason="llm_unavailable", flags=flags,
            )
            save_result(result, reason="llm_unavailable")
        return result
```

## 7. main.py (FastAPI)

```python
from fastapi import FastAPI, HTTPException
from .models import Ticket, TicketResult
from .router import handle_ticket
from .storage import tickets_db, escalation_queue

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
```

Запуск локально: `uvicorn app.main:app --reload` из корня репозитория.

## 8. tests/

```python
# tests/test_happy_path.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_happy_path():
    resp = client.post("/tickets", json={
        "ticket_id": "t1", "customer_id": "c1", "channel": "chat",
        "text": "когда приедет мой заказ?",
    })
    body = resp.json()
    assert body["path"] == "auto_reply"
    assert body["response"] is not None
    assert body["category"] == "order_status"
```

```python
# tests/test_escalation_path.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_escalation_path():
    resp = client.post("/tickets", json={
        "ticket_id": "t2", "customer_id": "c2", "channel": "email",
        "text": "верните деньги, спишите оплату обратно",
    })
    body = resp.json()
    assert body["path"] == "escalated"
    assert body["response"] is None
    assert "t2" in client.get("/escalations").json()
```

```python
# tests/test_llm_fallback.py
from fastapi.testclient import TestClient
from app.main import app
from app.router import handle_ticket
from app.models import Ticket
from app.llm_client import MockLLM


def test_llm_fallback_does_not_crash():
    ticket = Ticket(ticket_id="t3", customer_id="c3", channel="web", text="где мой заказ?")
    result = handle_ticket(ticket, llm=MockLLM(force_failure=True))
    assert result.path in {"auto_reply", "escalated"}
    if result.path == "escalated":
        assert result.escalation_reason == "llm_unavailable"
```

Запуск: `pytest -q` из корня.

## 9. Dockerfile / docker-compose.yml

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
```

## 10. scripts/demo.py (для формального требования smoke-test/demo)

```python
import httpx

BASE = "http://localhost:8000"

CASES = [
    {"ticket_id": "demo-happy", "customer_id": "c1", "channel": "chat",
     "text": "когда приедет мой заказ?"},
    {"ticket_id": "demo-risky", "customer_id": "c2", "channel": "email",
     "text": "верните деньги, спишите оплату обратно"},
]

if __name__ == "__main__":
    for case in CASES:
        r = httpx.post(f"{BASE}/tickets", json=case, timeout=5)
        print(case["ticket_id"], "->", r.json())
```

## 11. Порядок команд для проверки в конце

```bash
pytest -q
uvicorn app.main:app --reload &      # в одном терминале
python scripts/demo.py               # в другом
curl -X POST localhost:8000/tickets -H "Content-Type: application/json" \
  -d '{"ticket_id":"t1","customer_id":"c1","channel":"chat","text":"где мой заказ"}'
docker compose up --build            # финальная проверка через контейнер
```

## 12. Git — коммиты по шагам (пример сообщений, соответствуют PLAN.md)

```bash
git add README.md PLAN.md IMPLEMENTATION.md
git commit -m "docs: problem framing and assumptions"

git add app/__init__.py app/models.py app/storage.py app/main.py requirements.txt
git commit -m "feat: API skeleton and ticket model"

git add app/guard.py app/classifier.py data/eval/sample_tickets.jsonl
git commit -m "feat: intake guard and baseline classifier"

git add app/rag.py data/faq/
git commit -m "feat: retrieval over FAQ knowledge base"

git add app/llm_client.py
git commit -m "feat: LLM client with degradation fallback"

git add app/router.py
git commit -m "feat: routing between auto-reply and human escalation"

git add tests/
git commit -m "test: smoke tests for both paths"

git add Dockerfile docker-compose.yml scripts/demo.py
git commit -m "chore: containerize PoC and add demo script"

git add docs/architecture.md docs/ml.md
git commit -m "docs: architecture and ML approach"

git add docs/monitoring.md docs/risks-and-ops.md
git commit -m "docs: monitoring and risks"

git add AI_USAGE.md SELF_REVIEW.md
git commit -m "docs: AI usage log and self review"
```
