from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, ticket_text: str, context: str) -> str: ...


class MockLLM(LLMClient):
    """Детерминированный мок: не требует API-ключа, воспроизводим для проверяющего.
    force_failure имитирует недоступность/timeout реального LLM API для проверки деградации."""

    def __init__(self, force_failure: bool = False):
        self.force_failure = force_failure

    def generate(self, ticket_text: str, context: str) -> str:
        if self.force_failure:
            raise TimeoutError("LLM API unavailable (simulated)")
        snippet = context.strip().splitlines()[0] if context else "см. базу знаний"
        return f"Спасибо за обращение. {snippet}"


# RealLLMClient(OpenAI/Anthropic и т.п.) в PoC не реализуется — это осознанное упрощение.
# Design decision (см. docs/architecture.md): любая реализация LLMClient подключается
# в router.handle_ticket через параметр без изменения остальной логики.
