import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Few-shot примеры на категорию. Баланс между покрытием и временем разработки —
# в проде заменяется на классификатор, дообученный на размеченных исторических тикетах.
EXEMPLARS: dict[str, list[str]] = {
    "order_status": [
        "где мой заказ",
        "статус доставки",
        "когда придёт посылка",
        "не могу отследить заказ",
    ],
    "account_access": [
        "не могу войти в аккаунт",
        "забыл пароль",
        "заблокировали аккаунт",
        "не приходит код подтверждения",
    ],
    "billing_refund": [
        "хочу вернуть деньги",
        "верните оплату",
        "списали деньги ошибочно",
        "запросить возврат средств",
    ],
    "technical_bug": [
        "приложение вылетает",
        "ошибка при оплате",
        "не работает кнопка",
        "сайт не загружается",
    ],
    "abuse_or_complaint": [
        "оператор нахамил",
        "жалоба на сотрудника",
        "это возмутительно",
        "хочу пожаловаться на обслуживание",
    ],
    "other": [
        "у меня есть вопрос",
        "подскажите по сервису",
        "как связаться с поддержкой",
    ],
}

# Порог подобран на data/eval/sample_tickets.jsonl (см. docs/ml.md): на этом наборе
# 0.5 отделяет обе реальные ошибки классификации (conf 0.37-0.45) от всех верных
# предсказаний (conf >= 0.58) — ниже него уходим в эскалацию, а не в автоответ.
CONFIDENCE_THRESHOLD = 0.5

_labels = [cat for cat, exs in EXEMPLARS.items() for _ in exs]
_corpus = [ex for exs in EXEMPLARS.values() for ex in exs]
_vectorizer = TfidfVectorizer().fit(_corpus)
_exemplar_vectors = _vectorizer.transform(_corpus)


def classify(text: str) -> tuple[str, float]:
    """Возвращает (категория, confidence) — cosine similarity к ближайшему few-shot примеру."""
    vec = _vectorizer.transform([text])
    sims = cosine_similarity(vec, _exemplar_vectors)[0]
    best_idx = int(np.argmax(sims))
    return _labels[best_idx], float(sims[best_idx])
