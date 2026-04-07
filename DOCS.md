# OCRUZ — Сервис распознавания паспортов Узбекистана

## Обзор

OCRUZ — веб-сервис для автоматического извлечения данных из паспортов Узбекистана с использованием Qwen3.5-Plus Vision API (мультимодальная нейросеть). Пользователь загружает фотографию паспорта, сервис возвращает структурированные поля: ФИО, дата рождения, пол, гражданство, номер паспорта, ПИНФЛ и др.

---

## Архитектура

```
┌─────────────┐      ┌──────────┐      ┌───────────────┐      ┌────────────┐
│   Браузер   │─────▶│  Nginx   │─────▶│  FastAPI API   │─────▶│ PostgreSQL │
│  Dashboard  │      │  :8080   │      │  :8001         │      │            │
└─────────────┘      └──────────┘      └───────┬───────┘      └────────────┘
                                               │
                                               ▼
                                       ┌───────────────┐      ┌─────────────┐
                                       │   Celery      │─────▶│    Redis    │
                                       │   Worker      │      │  :6379      │
                                       └───────┬───────┘      └─────────────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │  Qwen API     │
                                       │  (Alibaba)    │
                                       └───────────────┘
```

---

## Технологии

| Компонент | Технология |
|---|---|
| Backend | FastAPI + Uvicorn |
| Язык | Python 3.11 |
| OCR/Vision | Qwen3.5-Plus (Alibaba DashScope) |
| Очередь задач | Celery + Redis |
| База данных | PostgreSQL 16 |
| Reverse Proxy | Nginx |
| Контейнеризация | Docker + Docker Compose |

---

## Деплой на сервере

### Сервер
- **IP:** `172.16.252.32` (VPN)
- **SSH:** `ssh yoyo@172.16.252.32`
- **OS:** Ubuntu 24.04.2 LTS

### Репозиторий
- **GitHub:** `https://github.com/SNurali/OCR.git`
- **Ветка:** `main`

### Docker Compose (5 сервисов)
| Сервис | Контейнер | Порт | Описание |
|---|---|---|---|
| API | `ocr-service-api-1` | `8001:8000` | FastAPI приложение |
| Celery | `ocr-service-celery_worker-1` | — | Фоновая обработка OCR |
| PostgreSQL | `ocr-service-postgres-1` | внутр. | Хранение результатов |
| Redis | `ocr-service-redis-1` | внутр. | Брокер задач |
| Nginx | `ocr-service-nginx-1` | `8080`, `8443` | Прокси + SSL |

### Команды управления
```bash
cd /home/yoyo/ocr-service

# Запуск
docker compose -f docker-compose.prod.yml up -d --build

# Остановка
docker compose -f docker-compose.prod.yml down

# Просмотр логов
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery_worker

# Статус
docker compose -f docker-compose.prod.yml ps

# Обновление кода
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build api celery_worker
```

---

## Адреса и доступы

### Дашборд
| Адрес | Описание |
|---|---|
| `http://172.16.252.32:8080` | Основной дашборд (панель управления) |
| `https://172.16.252.32:8443` | Дашборд через HTTPS |

### API
| Адрес | Описание |
|---|---|
| `http://172.16.252.32:8001/api/health` | Health check |
| `http://172.16.252.32:8001/api/redoc` | 📖 Документация API (открыта) |
| `http://172.16.252.32:8001/api/docs` | Swagger UI (нужен JWT) |

### Авторизация
| | |
|---|---|
| **Логин** | `admin` |
| **Пароль** | `admin123` |

---

## API Endpoints

### Аутентификация
| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/auth/login` | Получить JWT токен (`username` + `password`) |

### Распознавание паспортов
| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/passport/scan` | Загрузить паспорт (асинхронно, возвращает `task_id`) |
| `POST` | `/api/passport/test-ocr` | Синхронный тест OCR (ждёт результат) |
| `GET` | `/api/passport/status/{task_id}` | Статус обработки |
| `GET` | `/api/passport/result/{task_id}` | Результат распознавания |
| `GET` | `/api/passport/list` | Список всех обработанных паспортов |

### Администрирование
| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/admin/users` | Список пользователей |
| `POST` | `/api/admin/users` | Создать пользователя |
| `POST` | `/api/admin/users/{id}/role` | Назначить роль |

### Аналитика
| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/analytics/summary` | Сводка по распознаваниям |
| `GET` | `/api/analytics/report` | Полный отчёт |

---

## Как работает распознавание

1. **Загрузка** — пользователь загружает фото паспорта через дашборд
2. **Очередь** — задача отправляется в Celery (Redis broker)
3. **Сжатие** — изображение сжимается (JPEG quality 85%, max 1600px)
4. **Qwen API** — изображение отправляется в Qwen3.5-Plus Vision
5. **Извлечение** — модель возвращает JSON с полями паспорта
6. **Валидация** — проверка дат, ПИНФЛ (14 цифр), формата паспорта
7. **Сохранение** — результат записывается в PostgreSQL
8. **Поллинг** — дашборд опрашивает `/status/{task_id}` каждые 2 сек

### Распознаваемые поля
- `first_name` — Имя
- `last_name` — Фамилия
- `middle_name` — Отчество
- `birth_date` — Дата рождения (DD.MM.YYYY)
- `gender` — Пол (M/F)
- `nationality` — Гражданство
- `passport_number` — Номер паспорта (AA1234567)
- `issue_date` — Дата выдачи
- `expiry_date` — Срок действия
- `issued_by` — Кем выдан
- `pinfl` — ПИНФЛ (14 цифр)

### Время обработки
- Успешное: **25-45 секунд**
- С повторными попытками: **60-120 секунд** (3 retry, таймаут 180 сек)

---

## Структура проекта

```
ocr-service/
├── app/
│   ├── main.py                 # FastAPI приложение
│   ├── config.py               # Настройки (Qwen, DB, JWT)
│   ├── models.py               # SQLAlchemy модели
│   ├── schemas.py              # Pydantic схемы
│   ├── celery_app.py           # Celery конфигурация
│   ├── auth.py                 # JWT аутентификация
│   ├── limiter.py              # Rate limiting
│   ├── openapi_i18n.py         # Локализация документации
│   ├── routers/
│   │   ├── passport.py         # OCR endpoints
│   │   ├── auth.py             # Аутентификация
│   │   ├── admin.py            # Админ-панель
│   │   ├── analytics.py        # Аналитика
│   │   └── dashboard_legacy.py # Legacy dashboard
│   ├── services/
│   │   ├── vlm_extractor.py    # Qwen Vision API клиент
│   │   ├── ocr_analyzer.py     # Главный pipeline
│   │   ├── validator.py        # Валидация данных
│   │   ├── analytics_service.py
│   │   └── name_lexicons/      # Словари узбекских имён
│   ├── tasks/
│   │   └── ocr_task.py         # Celery task для OCR
│   ├── middleware/
│   └── utils/
│       ├── logging.py          # JSON логирование
│       └── metrics.py          # Prometheus метрики
├── alembic/                    # Миграции БД
├── tests/                      # Unit тесты
├── nginx/                      # Nginx конфиг + SSL
├── docker-compose.yml          # Локальный деплой
├── docker-compose.prod.yml     # Продакшен деплой
├── Dockerfile                  # API образ
├── Dockerfile.worker           # Celery образ
├── requirements.txt            # Python зависимости
├── .env.example                # Шаблон окружения
├── dashboard.html              # Дашборд (SPA)
└── README.md
```

---

## Переменные окружения (.env.prod)

```env
# Database
DB_HOST=postgres
DB_USER=ocr_service
DB_PASSWORD=ocr_secure_password
DB_NAME=ocr_service_db

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# JWT
JWT_SECRET_KEY=...
ENCRYPTION_KEY=...

# Qwen VLM
QWEN_API_KEY=sk-sp-aadd4a10ec6544e3950eed157d9fda29
QWEN_MODEL=qwen3.5-plus
QWEN_BASE_URL=https://coding-intl.dashscope.aliyuncs.com/v1
VLM_TIMEOUT=180
```

---

## Безопасность

- JWT аутентификация для всех endpoints
- Rate limiting: 60 запросов/минуту
- Валидация размера файла (max 10MB)
- CORS настроен
- SSL через Nginx (самоподписанный сертификат)

---

## Обновление кода

```bash
ssh yoyo@172.16.252.32
echo '01200120' | sudo -S bash -c '
  cd /home/yoyo/ocr-service
  git pull origin main
  docker compose -f docker-compose.prod.yml up -d --build api celery_worker
'
```

---

## Версия

**Текущая версия:** `2.2.0`  
**Последнее обновление:** Апрель 2026  
**OCR движок:** Qwen3.5-Plus Vision (Alibaba DashScope)
