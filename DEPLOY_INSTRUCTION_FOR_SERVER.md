# Инструкция для деплоя на боевой сервер

## Статус проекта

**Дата:** 7 апреля 2026
**Репозиторий:** https://github.com/SNurali/ocr-service.git
**API:** http://YOUR_SERVER_IP:PORT/

---

## ⚠️ ИСПРАВЛЕНИЯ В ЭТОЙ ВЕРСИИ

1. **Первоначальная настройка** — адаптация конфигурации под `ocr-service`
2. **База данных** — настройка изолированной БД `ocr_service_db`
3. **API URL** — добавлен внутренний и внешний URL для OCR

---

## Промпт-инструкция для ИИ-Агента (С доступами к VPN-серверу)
*(Если будете просить ИИ задеплоить этот проект, отправьте ему этот текст)*

Привет! Ты выступаешь в роли Senior DevOps Инженера. Тебе предстоит развернуть проект **ocr-service** на Production-сервере. 

⚠️ ВАЖНЫЙ КОНТЕКСТ: На этом сервере УЖЕ РАБОТАЮТ другие проекты (например, `nodir_hdd_fixer`). Ты должен деплоить новый проект максимально "хирургически", чтобы никак не задеть "соседей".

Вот креды для прямого деплоя:
- **Server IP (VPN):** `172.16.252.32`
- **Пользователь SSH:** `yoyo`
- **Пароль (для SSH и Sudo):** `01200120`

🔴 КРИТИЧЕСКИЕ ПРАВИЛА (СТРОГО СОБЛЮДАТЬ):
- ЗАПРЕЩЕНО использовать `docker system prune`, `docker container prune` или массовые остановки `docker stop $(docker ps -a -q)`.
- ЗАПРЕЩЕНО использовать глобальные команды `docker-compose down` без привязки к твоему `docker-compose.yml`.
- Все контейнеры должны иметь префикс `ocr_service_`.
- Используй `sshpass -p '01200120' ssh -o StrictHostKeyChecking=no yoyo@172.16.252.32 "echo '01200120' | sudo -S bash -c 'ТВОЯ_КОМАНДА'"`

---

## Команды для ручного обновления на сервере

### 1. Перейти в директорию проекта
```bash
cd /home/yoyo/ocr-service
```

### 2. Остановить текущие контейнеры проекта
```bash
docker compose -f docker-compose.prod.yml down
```

### 3. Получить последние изменения
```bash
git fetch origin
git reset --hard origin/main
```

### 4. Пересобрать и запустить (ВАЖНО: --build!)
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 5. Проверить здоровье сервисов
```bash
# Проверить что API доступен
curl http://localhost:<ВАШ_ПОРТ>/health
```

### 6. Проверить логи
```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## Переменные окружения (.env.prod)

Файл должен содержать уникальные параметры для OCR-сервиса:

```env
# Database
DB_HOST=ocr_postgres
DB_PORT=5432
DB_USERNAME=ocr_service
DB_PASSWORD=SECURE_PASSWORD
DB_DATABASE=ocr_service_db

# Redis (если нужен)
REDIS_HOST=ocr_redis
REDIS_PORT=6379

# API
APP_PORT=3000
NODE_ENV=production
```

---

## Volumes (для сохранения данных)

| Volume | Назначение |
|--------|------------|
| ocr_pgdata_prod | База данных PostgreSQL |
| ocr_redisdata_prod | Данные Redis (кэш/очереди) |
| ocr_uploads_prod | Загруженные сканы/фото паспортов |

---

## Быстрая проверка

```bash
# Проверить статус контейнеров
docker compose -f docker-compose.prod.yml ps

# Проверить логи API
docker compose -f docker-compose.prod.yml logs -f api

# Проверить подключение к БД
docker exec ocr_service_postgres_prod psql -U ocr_service -d ocr_service_db -c "SELECT 1"
```

---

## Откат (если что-то пошло не так)

```bash
# Остановить всё
docker compose -f docker-compose.prod.yml down

# Вернуться к предыдущей версии
git log --oneline -5  # найти нужный коммит
git reset --hard <commit_hash>

# Пересобрать и запустить
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Контакты

- GitHub: https://github.com/SNurali/ocr-service
- Разработчик: @SNurali
