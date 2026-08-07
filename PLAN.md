# План: System Design Case — «Автоматизация обработки тикетов поддержки»

## Контекст
Кейс на поступление (трек «Искусственный интеллект»): спроектировать AI/ML-систему для автоматизации обработки тикетов поддержки крупного онлайн-сервиса и подтвердить дизайн минимальным PoC. Тайм-бокс — 4 часа, реальный прогон. Формулировка кейса намеренно короткая — часть задачи в том, чтобы явно зафиксировать допущения и обосновать выбор метрик/подхода.

Роль AI в этой сессии: соавтор — пишет код и документацию вместе с кандидатом, на каждом значимом решении коротко объясняя рассуждение (альтернативы, trade-off), чтобы кандидат мог сам защитить решение на собеседовании. Предложения AI и отклонённые альтернативы фиксируются в `AI_USAGE.md` по ходу работы, включая реальные ошибки/неверные предположения AI в процессе — не постфактум.

## Вводные (даны в задании)
- Масштаб: ~5М активных пользователей, ~200k тикетов/день (≈2.3 тикета/сек в среднем), всплески при инцидентах — 10–20k тикетов за 10 минут (≈17–33 тикета/сек, до ~14x от базовой нагрузки).
- Каналы: чат, email, веб-форма, моб. приложение — разный формат текста.
- Поток неоднородный: часть типовые/повторяющиеся (~40% по внутренней оценке), часть требует ручного разбора, часть содержит PII.
- Hot path (классификация + маршрутизация) — ориентир ≤500 мс/тикет. Генерация ответа может быть асинхронной.
- Обязательна корректная деградация при недоступности LLM API; стоимость LLM-инференса должна быть под контролем.
- Рискованные категории — ответ модели не уходит пользователю без проверки оператора; все автоматические решения логируются и аудируемы.
- Бизнес-цифры: обработка тикета оператором ≈150₽ (≈8 мин); целевой SLA первого ответа — 15 мин; текущий CSAT 4.2/5; reopen rate 9%; доля типовых обращений ~40%.

## Допущения о домене (фиксируем в README/architecture.md)
- Тикет: `ticket_id`, `customer_id`, `channel`, `text`, `created_at`.
- Категории: `order_status`, `account_access`, `billing_refund`, `technical_bug`, `abuse_or_complaint`, `other`.
- Автоответ (happy path) — только для информационных, не денежных, не связанных с безопасностью категорий, покрытых базой знаний (`order_status`, часть `technical_bug`).
- Жёсткая эскалация на человека (risky path) — `billing_refund`, `account_access`, `abuse_or_complaint`, низкая уверенность классификатора/ретривала, обнаружен PII сверх необходимого, признак prompt injection.
- Во время инцидентных всплесков многие тикеты об одном и том же — предусмотреть дедупликацию/кластеризацию похожих тикетов, чтобы не звать LLM на каждый дубликат отдельно (экономия стоимости и снижение нагрузки).

## Что НЕ делаем (жёстко)
- Не строим production-ready систему, не пишем код ради объёма.
- Не обучаем модель на большом датасете — только baseline (правила + few-shot TF-IDF), без обучения.
- Никакого Kubernetes/feature store/полноценного MLOps — очередь и хранилище только как простые in-process абстракции с пометкой "в проде заменить на X".
- Не проектируем UI оператора — эскалация оператору = запись в escalation-очередь/лог, этого достаточно.
- Документация — компактная и по делу (каждый .md — по существу, не маркетинг), а не максимально подробная.
- Ориентир: компактный честный репозиторий важнее большого сгенерированного.

## Чек-лист перед сдачей (сверим в конце)
- Все обязательные для трека «ИИ» артефакты на месте (см. список ниже).
- PoC поднимается и прогоняется строго по инструкции из README.
- Есть минимальный smoke-test/demo-скрипт, реально проходящий.
- Mermaid-диаграммы рендерятся (проверить синтаксис).
- Внутренние ссылки между .md-файлами не битые.
- История коммитов честно отражает ход работы (для обсуждения на собеседовании).

## Требуемые артефакты (трек «Искусственный интеллект» — «для всех» + «обязательно для ИИ»; product.md/WORKLOG.md пропускаем — они только для AI Product)
```
ai_system_design_project/
  README.md                      # для всех: что делает, как запустить, что реально/что дизайн, допущения, 3-5 предл. бизнес-ценности
  docs/
    architecture.md               # обязательно для ИИ: компоненты, поток данных, sync/async, хранилища, human-in-the-loop, mermaid-диаграммы
    ml.md                          # обязательно для ИИ: правила vs ML vs embeddings/retrieval vs LLM, где LLM не нужен, baseline, валидация без большого датасета, low-confidence, происхождение моделей/данных
    monitoring.md                  # обязательно для ИИ: технические+ML+бизнес метрики, алерты, деградация модели vs дрейф входа, мониторинг стоимости LLM
    risks-and-ops.md                # для всех: highload/надёжность (3-4 пункта), privacy/safety/risk (3-4 пункта)
  AI_USAGE.md                       # для всех: роль AI по этапам, отклонённые предложения, реальные ошибки AI и как их поймали
  SELF_REVIEW.md                     # для всех: слабое место, допущения, риски, что доделать за 2 дня, что нельзя автоматизировать, какие данные пилота остановили бы проект
  docker-compose.yml
  Dockerfile
  requirements.txt
  app/
    main.py                          # FastAPI: POST /tickets, GET /tickets/{id}, GET /escalations
    models.py                         # Ticket, Category, TicketResult
    guard.py                           # PII / prompt-injection эвристики
    classifier.py                       # baseline: TF-IDF + cosine similarity к few-shot примерам категорий → confidence
    rag.py                                # retrieval по мини-базе FAQ: тот же TF-IDF + cosine similarity, без внешней vector DB
    llm_client.py                          # MockLLM (детерминированный) + опциональный реальный провайдер по env var; имитация timeout/недоступности
    router.py                               # auto-reply vs escalate, идемпотентность по ticket_id, дедуп похожих тикетов
    storage.py                               # in-memory: тикеты, audit-лог решений, escalation-очередь
  data/faq/*.md                              # мини-база знаний (3-5 документов) под категории
  data/eval/sample_tickets.jsonl              # 15-20 размеченных примеров для мини-валидации классификатора
  scripts/demo.py                              # demo-скрипт: happy / risky / llm-fallback вызовы API
  tests/
    test_happy_path.py
    test_escalation_path.py
    test_llm_fallback.py
```

## Архитектура (для docs/architecture.md, mermaid)
```
Ticket in (любой канал) → Ingestion API (sync, быстрый accept + запись в очередь, идемпотентность по ticket_id)
  → Queue (амортизирует всплески 10-20k/10мин, отвязывает приём от обработки)
    → Worker: PII/prompt-injection guard (sync, регэксп/эвристика, мс)
    → Worker: Fast classifier (sync, similarity, ориентир ≤500мс) — категория + confidence
        ├─ high confidence + safe category → Dedup/cluster check → RAG retrieval → LLM generation (async, может быть медленным)
        │     ├─ LLM/ретривал доступны и confidence retrieval высокий → черновик ответа → happy path → auto-reply + audit log
        │     └─ LLM недоступен/timeout (circuit breaker) → деградация: canned-ответ по категории ИЛИ эскалация
        └─ low confidence / risky category / PII / injection → risky path → escalation queue оператору, без автоответа, audit log
  Storage: ticket store, audit log (все решения), knowledge base, escalation queue
  Мониторинг: hot-path latency, confidence distribution, queue backlog, LLM error rate, cost per ticket
```
Что помечаем «спроектировано, не развёрнуто» ради тайм-бокса (PoC-масштаб) и чем заменить в проде:
- Очередь → in-memory/asyncio-очередь в PoC; в проде — Kafka/SQS с автоскейлингом воркеров под всплески.
- Хранилище → in-memory dict в PoC; в проде — БД + отдельный append-only audit log.
- Ретривал/классификация → TF-IDF + cosine similarity (scikit-learn, без скачивания embedding-моделей) в PoC; в проде — sentence embeddings + managed vector DB, дообученные на исторических тикетах.
- Дедуп/кластеризация во время инцидентов → упрощённая (хэш/similarity threshold) в PoC, в architecture.md описываем полноценный подход.

## Технический план реализации (минимально рабочая, учебная версия)
Цель — не "правдоподобный ML", а показать сквозной поток решений с реальными, но простыми компонентами. Никаких скачиваемых моделей/внешних сервисов по умолчанию — PoC должен подниматься офлайн за секунды.

### Стек (сознательно лёгкий)
- Python 3.11+, FastAPI + uvicorn, pydantic v2
- **scikit-learn** (`TfidfVectorizer` + `cosine_similarity`) — единственный "ML"-компонент, используется и для классификации (similarity к few-shot примерам категорий), и для retrieval (similarity к FAQ-документам). Осознанно НЕ берём FAISS/Chroma/sentence-transformers/LangChain: для 3-6 категорий и 3-5 FAQ-документов это оверинжиниринг, а TF-IDF не требует скачивания весов — важно для надёжного запуска за 4 часа. Это явное упрощение, фиксируется в `ml.md` с указанием, чем заменить в проде.
- Никакой очереди/брокера — `router.py` вызывается синхронно из хендлера; в `architecture.md` описывается, как это разносится на очередь+воркеры в проде.
- Хранилище — два `dict`/`list` в памяти процесса (`tickets_db`, `audit_log`, `escalation_queue`).
- pytest + `fastapi.testclient.TestClient` — тесты без поднятия реального сервера.

### Сквозной поток обработки (router.handle_ticket)
1. **Идемпотентность**: если `ticket_id` уже есть в `tickets_db` → вернуть сохранённый результат, не переобрабатывать.
2. **guard.py**: `check_pii(text)` (regex: email, телефон, номер карты) и `check_prompt_injection(text)` (regex/keyword-эвристика: "ignore previous instructions", "system:", попытки переопределить роль). Возвращают списки найденных флагов.
3. **classifier.py**: `classify(text) -> (category, confidence)`. Захардкоженные few-shot примеры (3-5 фраз) на категорию в `EXEMPLARS: dict[str, list[str]]`. `TfidfVectorizer` фитится на всех exemplars + входящий текст, cosine similarity текста к центроиду каждой категории → категория с максимальным score, `confidence = max_score`. Порог `CONFIDENCE_THRESHOLD = 0.35` (подобрать эмпирически на eval-датасете, значение и обоснование — в `ml.md`).
4. **router.py — решение**:
   - `category in RISKY_CATEGORIES` (`billing_refund`, `account_access`, `abuse_or_complaint`) ИЛИ `pii_flags` ИЛИ `injection_flags` ИЛИ `confidence < THRESHOLD` → **risky path**: записать в `escalation_queue` + `audit_log` с причиной, `response=None`, вернуть клиенту `path="escalated"`.
   - иначе → **happy path**: `rag.retrieve(text)` находит лучший FAQ-документ (та же TF-IDF-механика) → `llm_client.generate(text, retrieved_doc)`.
5. **llm_client.py**: интерфейс `LLMClient.generate(prompt) -> str`. Реализация `MockLLM` — детерминированный шаблон, собирающий ответ из найденного FAQ-сниппета (без реального вызова API — не нужен ключ, воспроизводимо для проверяющего). Параметр/env `LLM_FAILURE_MODE` (или явный флаг в запросе для теста) заставляет `MockLLM` бросить `TimeoutError`, чтобы показать деградацию. Класс написан так, что `RealLLMClient(OpenAI/Anthropic)` подключается заменой одной зависимости — это фиксируется как design decision, не реализуется.
6. **Деградация**: `router.py` оборачивает вызов `llm_client.generate` в try/except — при `TimeoutError` НЕ роняем запрос: либо canned-ответ по категории (если есть в `FAQ`), либо эскалация с причиной `"llm_unavailable"`. Это и есть fallback/risky path сценарий №6 из примера в задании.
7. **storage.py**: каждое решение (успех/эскалация/фолбэк) пишется в `audit_log` одной записью: `ticket_id, category, confidence, path, flags, timestamp, reason`. Это и есть "аудит автоматических решений" из требований.

### Файлы приложения — что внутри
- `models.py`: `Ticket(BaseModel)` (ticket_id, customer_id, channel, text, created_at), `TicketResult(BaseModel)` (ticket_id, category, confidence, path, response, escalation_reason, flags).
- `main.py`: `POST /tickets` (принимает `Ticket`, вызывает `router.handle_ticket`, возвращает `TicketResult`), `GET /tickets/{id}`, `GET /escalations`, `GET /health`.
- `data/faq/*.md`: 3-5 файлов, по одному на покрываемую тему (`order_status.md`, `technical_bug_known_issue.md`, ...), простой текст — заголовок + ответ.
- `data/eval/sample_tickets.jsonl`: 15-20 строк `{"text": ..., "expected_category": ...}` — вручную составленные, разнородные по каналам/формату, используются в `ml.md` для мини-отчёта precision/recall и подбора порога.

### Тесты (`tests/`, используют `TestClient`, без сети)
- `test_happy_path.py`: тикет-парафраз одного из FAQ (например, "где мой заказ") → `path == "auto_reply"`, `response is not None`, `category == "order_status"`.
- `test_escalation_path.py`: тикет про возврат денег ("верните деньги за заказ") → `path == "escalated"`, `response is None`, тикет появляется в `GET /escalations`.
- `test_llm_fallback.py`: happy-путь категория, но `MockLLM` форсированно падает → тикет не 500-ит, получает либо canned-ответ, либо эскалацию с `reason == "llm_unavailable"`.
- `test_idempotency.py` (опционально, если останется время): повторный `POST` с тем же `ticket_id` возвращает тот же результат, без второй записи в `audit_log`.

### Demo-скрипт (для формального требования "smoke-test/demo")
`scripts/demo.py` — три последовательных вызова API через `httpx`/`requests`: happy-тикет, risky-тикет, тикет с форсированным сбоем LLM — печатает `TicketResult` для каждого. Вызывается одной командой из README (`python scripts/demo.py` при поднятом `uvicorn`, либо через `docker-compose`).

## Порядок выполнения (~4 часа, коммиты по шагам)
1. `git init`, скелет репозитория, README (допущения, что делает, ценность бизнесу) (~25 мин) — "docs: problem framing and assumptions"
2. FastAPI-скелет, модели, in-memory storage + audit log (~25 мин) — "feat: API skeleton and ticket model"
3. Guard (PII/prompt injection) + baseline classifier (TF-IDF + cosine similarity к few-shot примерам, confidence) + мини eval-датасет (~40 мин) — "feat: intake guard and baseline classifier"
4. RAG: мини-база FAQ + retrieval (TF-IDF + cosine similarity, без внешней vector DB) (~30 мин) — "feat: retrieval over FAQ knowledge base"
5. LLM client (Mock + опция реального провайдера), деградация/timeout, дедуп похожих тикетов (~30 мин) — "feat: LLM client with degradation and dedup"
6. Router: happy vs risky path, идемпотентность (~20 мин) — "feat: routing between auto-reply and human escalation"
7. pytest smoke-тесты (happy / escalation / llm-fallback) (~20 мин) — "test: smoke tests for both paths"
8. Dockerfile + docker-compose (~15 мин) — "chore: containerize PoC"
9. docs/architecture.md + docs/ml.md (~30 мин) — "docs: architecture and ML approach"
10. docs/monitoring.md + docs/risks-and-ops.md (~25 мин) — "docs: monitoring and risks"
11. AI_USAGE.md (по ходу работы, финальная сборка) + SELF_REVIEW.md (~20 мин) — "docs: AI usage log and self review"
12. Резерв/финальная проверка (~10-15 мин): `pytest`, `docker-compose up`, ручная проверка happy/risky/fallback.

На каждом шаге — короткое пояснение решения и альтернатив вслух (для AI_USAGE.md и защиты на собеседовании).

## Тестовый план / проверка
- `pytest -q`: (1) FAQ-подобный запрос → auto-reply из RAG; (2) `billing_refund`/низкая уверенность/PII → эскалация, без auto-reply; (3) LLM недоступен (мок кидает timeout) → деградация, тикет не зависает.
- `docker-compose up` — сервис поднимается, `POST /tickets` отвечает.
- Идемпотентность: повторный `POST` с тем же `ticket_id` не дублирует ответ/эскалацию.
- Мини-валидация классификатора на `data/eval/sample_tickets.jsonl` (precision/recall по категориям, порог confidence) — фиксируется в ml.md.
