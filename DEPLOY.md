# Deployment Guide / Руководство по деплою

OCR Service — AI-driven ID extraction system

---

## 📋 Содержание

1. [Требования](#требования)
2. [Локальная разработка](#локальная-разработка)
3. [Деплой на продакшен](#деплой-на-продакшен)
4. [Настройка сервера](#настройка-сервера)
5. [Мониторинг и логи](#мониторинг-и-логи)

---

## Требования

### Минимальные требования
- **OS**: Linux (Ubuntu 20.04+, Debian 11+)
- **CPU**: 4 cores
- **RAM**: 8 GB (рекомендуется для моделей ML)
- **Disk**: 40 GB free space (для образов и кэша моделей)
- **Python**: 3.10+
- **Docker**: 24.x+
- **Docker Compose**: 2.x+

---

## Локальная разработка

### Быстрый старт (Docker)

```bash
# 1. Клонировать репозиторий
git clone https://github.com/SNurali/ocr-service.git
cd ocr-service

# 2. Создать файл .env
cp .env.example .env

# 3. Запустить
docker compose up -d
```

### Сервисы локально

| Сервис | Порт |
|--------|------|
| API | 3000 |
| PostgreSQL | 5432 |
| Redis | 6379 |

---

## Деплой на продакшен

### Docker Compose (рекомендуется)

```bash
# 1. Обновить код
git pull origin main

# 2. Подготовить .env.prod
nano .env.prod

# 3. Запустить Docker контейнеры (prod)
docker compose -f docker-compose.prod.yml up -d --build

# 4. Проверить логи
docker compose -f docker-compose.prod.yml logs -f api
```

---

## Настройка сервера

### Настройка окружения

```bash
# Перейти в директорию проекта
cd /home/yoyo/ocr-service

# Создать .env.prod
nano .env.prod
```

```env
# Database
DB_HOST=ocr_postgres
DB_PORT=5432
DB_USERNAME=ocr_service
DB_PASSWORD=secret
DB_DATABASE=ocr_service_db

# Redis
REDIS_HOST=ocr_redis
REDIS_PORT=6379

# API
APP_PORT=3000
NODE_ENV=production
```

---

## Мониторинг и логи

### Docker Compose логи

```bash
# Все логи
docker compose -f docker-compose.prod.yml logs -f

# Только API
docker compose -f docker-compose.prod.yml logs -f api
```

### Проверка здоровья сервисов

```bash
# API health check
curl http://localhost:3000/health
```
