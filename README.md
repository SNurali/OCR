# Uzbek Passport OCR Service

Высокоточный OCR-сервис для распознавания данных из паспортов Узбекистана с использованием **Qwen3.5-Plus Vision** (Alibaba Cloud DashScope).

## Возможности

### 🚀 Qwen Vision API — единственный OCR движок
- ✅ **qwen3.5-plus** — мультимодальная модель с визуальным пониманием документов
- ✅ OpenAI API-совместимый протокол
- ✅ Автоматическое сжатие изображений перед отправкой
- ✅ Retry с exponential backoff при ошибках

### 🧠 Умная обработка
- ✅ **Контекстная экстракция** — LLM понимает структуру паспорта
- ✅ **Валидация данных** — проверка дат, номеров, ПИНФЛ (14 цифр)
- ✅ **Оценка уверенности** — per-field confidence scoring
- ✅ **Нормализация** — автоприведение дат к DD.MM.YYYY, пола к M/F

### 🔧 Интеграция
- ✅ **REST API** — FastAPI endpoints
- ✅ **Docker** — полная контейнеризация (API, Celery, Postgres, Redis, Nginx)
- ✅ **Мониторинг** — Prometheus metrics + Grafana dashboards
- ✅ **Асинхронная обработка** — Celery task queue

## Архитектура

```
Upload → FastAPI API → Celery Queue → Qwen Vision API → Validation → PostgreSQL
                                    ↓
                              Image compression
                              JSON extraction
                              Field normalization
```

## Установка

### Требования

- Python 3.11+
- Docker & Docker Compose (рекомендуется)
- API ключ Qwen (Alibaba Cloud DashScope)

### Быстрый старт

```bash
# 1. Клонируйте репозиторий
cd ocr-service

# 2. Настройте API ключ
cp .env.example .env
# Отредактируйте .env, вставьте QWEN_API_KEY

# 3. Запуск через Docker Compose
docker-compose up -d

# API запустится на http://localhost:8001
# Dashboard: http://localhost:8080
```

### Ручной запуск (без Docker)

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск API сервера
cd /home/mrnurali/LOW\ PROJECTS/ocr-service
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/api/health
```

### OCR паспорта (асинхронный)
```bash
curl -X POST "http://localhost:8000/api/passport/scan" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@passport.jpg"
```
Возвращает `task_id` для отслеживания статуса.

### OCR паспорта (синхронный тест)
```bash
curl -X POST "http://localhost:8000/api/passport/test-ocr" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@passport.jpg"
```

### Статус задачи
```bash
curl "http://localhost:8000/api/passport/status/{task_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Результат OCR
```bash
curl "http://localhost:8000/api/passport/result/{task_id}" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Пример ответа API

```json
{
  "success": true,
  "confidence": 0.92,
  "data": {
    "first_name": "NURALI",
    "last_name": "SULATMANOV",
    "middle_name": "AMIRJONOVICH",
    "birth_date": "24.03.2022",
    "gender": "M",
    "nationality": "O'ZBEKISTON",
    "passport_number": "AN7979293",
    "pinfl": "32409860230078",
    "issued_by": "TOSHKENT SHAHAR IIB"
  },
  "validation": {
    "all_valid": true,
    "checks": {
      "first_name": true,
      "last_name": true,
      "birth_date": true,
      "passport_number": true,
      "pinfl": true
    }
  }
}
```

## Структура проекта

```
ocr-service/
├── app/
│   ├── main.py                 # FastAPI приложение
│   ├── config.py               # Настройки (Qwen API, DB, JWT)
│   ├── models.py               # SQLAlchemy модели
│   ├── schemas.py              # Pydantic схемы
│   ├── celery_app.py           # Celery конфигурация
│   ├── routers/
│   │   ├── passport.py         # OCR endpoints
│   │   ├── auth.py             # JWT аутентификация
│   │   ├── admin.py            # Админ-панель
│   │   └── analytics.py        # Аналитика
│   ├── services/
│   │   ├── vlm_extractor.py    # Qwen Vision API клиент
│   │   ├── ocr_analyzer.py     # Главный pipeline
│   │   └── validator.py        # Валидация данных
│   ├── tasks/
│   │   └── ocr_task.py         # Celery task для OCR
│   └── utils/
├── alembic/                    # Миграции БД
├── tests/
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.worker
├── requirements.txt
└── .env
```

## Конфигурация Qwen API

Получите API ключ на [Alibaba Cloud DashScope](https://dashscope.console.aliyun.com/)

| Переменная | Описание | Значение по умолчанию |
|---|---|---|
| `QWEN_API_KEY` | API ключ | `sk-sp-...` |
| `QWEN_MODEL` | Модель | `qwen3.5-plus` |
| `QWEN_BASE_URL` | Base URL | `https://coding-intl.dashscope.aliyuncs.com/v1` |
| `VLM_TIMEOUT` | Timeout (сек) | `60` |

## Docker Compose сервисы

| Сервис | Порт | Описание |
|---|---|---|
| api | 8001:8000 | FastAPI API |
| celery_worker | - | Фоновая обработка задач |
| postgres | 5432:5432 | PostgreSQL БД |
| redis | 6379:6379 | Redis (брокер задач) |
| nginx | 8080, 8443 | Reverse proxy + SSL |
| prometheus | 9090 | Метрики |
| grafana | 3000 | Дашборды |

## Тестирование

```bash
pytest tests/ -v
```

## Лицензия

MIT
