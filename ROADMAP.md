# OCR Service — Roadmap до 10/10

> Статус: Early-stage SaaS (pre-scale)
> Архитектура: 10/10 | Backend: 10/10 | Production readiness: 9.7/10 | Бизнес готовность: 8/10

---

## 🔴 HIGH — Делать в первую очередь (влияет на деньги)

### 1. Billing — довести до денег

**Проблема:** `cost_cents` всегда 0, `SubscriptionPlan` не привязан к `APIKey`, monthly quota не enforced.

**Что сделать:**
- [ ] Добавить pricing логику (cost_cents расчёт на основе плана)
- [ ] Привязать `SubscriptionPlan` к `APIKey` (foreign key)
- [ ] Monthly quota enforcement (documents_per_month проверка)
- [ ] Endpoint `GET /api/billing/current` → usage + estimated bill
- [ ] Soft limits (warning при 80%) + hard limits (block при 100%)
- [ ] Response header: `X-Billing-Cost` per request

**Файлы:** `app/models.py`, `app/api_key_auth.py`, `app/routers/analytics.py`, новый `app/routers/billing.py`

**Оценка:** 2-3 дня

---

### 2. Audit Trail — для B2B клиентов

**Проблема:** `AccessLog` слишком минимальный, `compliance.py` — мёртвый код, `trace_id` не хранится в БД.

**Что сделать:**
- [ ] Расширить `AccessLog`: `api_key_id`, `resource_id`, `response_status`, `request_details` (JSON), `user_agent`
- [ ] `trace_id` из `tracing.py` → сохранять в БД
- [ ] Audit trail для API key usage (кто что запросил)
- [ ] Immutable audit log (soft delete only)
- [ ] Endpoint `GET /api/audit/logs` с фильтрацией
- [ ] Удалить или реализовать мёртвые модели в `compliance.py`

**Файлы:** `app/models.py`, `app/middleware/` (создать), `app/routers/audit.py`, `app/services/compliance.py`

**Оценка:** 2 дня

---

### 3. Zero-Trust Security

**Проблема:** CORS `allow_origins=["*"]`, нет IP whitelist, нет HMAC signing.

**Что сделать:**
- [ ] CORS lockdown: `allow_origins` из env config
- [ ] IP whitelist для B2B клиентов (поле в `APIKey`)
- [ ] Middleware для проверки IP whitelist
- [ ] HMAC request signing (опционально — для enterprise)
- [ ] API key rotation mechanism

**Файлы:** `app/config.py`, `app/main.py`, `app/api_key_auth.py`, `app/models.py`

**Оценка:** 1-2 дня

---

## 🟡 MEDIUM — Важно для стабильности

### 4. Smart Retry System

**Проблема:** Фиксированный retry delay 60s, нет exponential backoff, нет DLQ.

**Что сделать:**
- [ ] Exponential backoff: 30s → 2m → 8m → 32m
- [ ] Jitter (random ±20%) чтобы не было thundering herd
- [ ] Retry classification:
  - RETRY: OCR fail, network error, timeout
  - NO RETRY: validation failed, fraud detected, invalid file
- [ ] Dead letter queue для permanently failed tasks
- [ ] Retry-aware rate limiting (retries не считаются против quota)

**Файлы:** `app/tasks/ocr_task.py`, `app/celery_app.py`

**Оценка:** 1-2 дня

---

### 5. SLO / Error Budget

**Проблема:** Метрики есть, но нет контрактов качества.

**Что сделать:**
- [ ] Определить SLO:
  - `success_rate ≥ 99.5%`
  - `latency_p95 < 2s`
  - `ocr_accuracy > 98%`
- [ ] Error budget: 0.5% допустимых ошибок
- [ ] Prometheus alerting на burn rate (1h, 6h, 1d windows)
- [ ] Endpoint `GET /api/system/slo-status`
- [ ] Response header `X-SLO-Budget-Remaining`

**Файлы:** `prometheus/alerts.yml`, `app/routers/system.py`, `app/services/slo_tracker.py`

**Оценка:** 1-2 дня

---

### 6. Model Feedback Loop

**Проблема:** Нет механизма собирать ошибки OCR для дообучения.

**Что сделать:**
- [ ] Endpoint `POST /api/feedback/{record_id}` — клиент репортит ошибку
- [ ] Модель `OCRError`: `ocr_result`, `corrected_result`, `error_type`, `field_name`
- [ ] Dashboard: low confidence fields aggregation
- [ ] Confusion matrix / error pattern analysis
- [ ] Экспорт ошибок для retraining (CSV/JSON)

**Файлы:** `app/models.py`, `app/routers/feedback.py`, `app/services/feedback_collector.py`

**Оценка:** 2 дня

---

## 🟢 LOW — Уже достаточно хорошо

### 7. Performance Optimization

**Текущее состояние:** Async + Celery + circuit breakers + dedup — всё есть.

**Что можно улучшить (позже):**
- [ ] Stress test: 1000 req/min, 5000 req/min
- [ ] Redis caching layer для повторяющихся запросов
- [ ] Batch processing endpoint
- [ ] Database read replicas
- [ ] Async database sessions

**Оценка:** 3-5 дней (не срочно)

---

## 🚀 Что продавать СЕЙЧАС

Уже работает:
- ✅ API с JWT auth
- ✅ Async processing через Celery
- ✅ Analytics dashboard
- ✅ API key management с rate limits
- ✅ Usage tracking (UsageRecord)
- ✅ Prometheus + Grafana observability
- ✅ Circuit breaker + fallback chain
- ✅ Anti-fraud engine
- ✅ Image deduplication

Не хватает только:
- Pricing → 1 день
- Monthly quotas → 1 день
- Billing endpoint → полдня

---

## 📊 Итоговая оценка

| Компонент | Оценка | Готово |
|---|---|---|
| Архитектура | 10/10 | ✅ |
| Backend | 10/10 | ✅ |
| OCR Pipeline | 9/10 | ✅ |
| Observability | 9/10 | ✅ |
| Безопасность | 7/10 | ⚠️ |
| Billing | 5/10 | ⚠️ |
| Audit Trail | 4/10 | ⚠️ |
| Feedback Loop | 2/10 | ❌ |

**Общий production readiness: 9.7/10**
**Бизнес готовность: 8/10 → можно быстро поднять**

---

## ⚠️ Главная опасность

> НЕ начинать бесконечно "допиливать"
> Нужно идти в пользователей

### Правильная стратегия:
1. Подключить 3-5 реальных пользователей
2. Собрать ошибки
3. Улучшить модель на реальных данных

---

*Создано: 2026-04-04*
*Статус: План утверждён, реализация отложена до после тестирования*
