import os
from abc import ABC, abstractmethod

import httpx


class LLMClient(ABC):
    @abstractmethod
    def generate(self, ticket_text: str, context: str) -> str: ...


class MockLLM(LLMClient):
    """Детерминированный мок: не требует API-ключа/сети, воспроизводим для проверяющего.
    force_failure имитирует недоступность/timeout реального LLM API для проверки деградации.
    Используется по умолчанию — все тесты и стандартный запуск PoC от неё не зависят
    от внешних сервисов."""

    def __init__(self, force_failure: bool = False):
        self.force_failure = force_failure

    def generate(self, ticket_text: str, context: str) -> str:
        if self.force_failure:
            raise TimeoutError("LLM API unavailable (simulated)")
        lines = [ln.strip("# ").strip() for ln in context.strip().splitlines() if ln.strip()]
        snippet = lines[1] if len(lines) > 1 else (lines[0] if lines else "см. базу знаний")
        return f"Спасибо за обращение. {snippet}"


class OllamaLLM(LLMClient):
    """Реальная генерация через локальный Ollama (https://ollama.com), опционально.
    Не используется по умолчанию и не участвует в тестах — требует отдельно
    установленного и запущенного Ollama с загруженной моделью (см. README)."""

    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float = 10.0):
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = timeout

    def generate(self, ticket_text: str, context: str) -> str:
        prompt = (
            "Ты — оператор поддержки. Кратко и вежливо ответь клиенту, используя только "
            f"факты из контекста.\n\nКонтекст из базы знаний:\n{context}\n\n"
            f"Вопрос клиента: {ticket_text}\n\nОтвет:"
        )
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["response"].strip()
        except httpx.HTTPError as exc:
            raise TimeoutError(f"LLM API unavailable: {exc}") from exc


def get_llm_client(force_failure: bool = False) -> LLMClient:
    """Фабрика: по умолчанию MockLLM (без внешних зависимостей — так работают тесты
    и стандартный запуск). Установите LLM_PROVIDER=ollama, чтобы использовать реальную
    локальную модель через Ollama (см. README, раздел "Запуск с реальной LLM")."""
    if force_failure:
        return MockLLM(force_failure=True)
    if os.environ.get("LLM_PROVIDER") == "ollama":
        return OllamaLLM()
    return MockLLM()
