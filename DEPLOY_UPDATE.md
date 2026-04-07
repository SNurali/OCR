# 🚀 Скрипты развёртывания OCR Service

## Варианты развёртывания

### 1. Docker Compose (рекомендуется)

Для обновления на боевом сервере с Docker:

```bash
cd /home/yoyo/ocr-service
./scripts/deploy-update.sh
```

**Что делает скрипт:**
- ✅ Обновляет код из Git
- ✅ Останавливает Docker контейнеры
- ✅ Устанавливает зависимости
- ✅ Собирает приложение
- ✅ Запускает контейнеры заново `ocr_service_...`
- ✅ Показывает статус сервиса

---

### 2. Ручное обновление (Docker)

```bash
# Перейти в директорию проекта
cd /home/yoyo/ocr-service

# Обновить код
git pull origin main

# Остановить сервис
docker compose -f docker-compose.prod.yml down

# Пересобрать и запустить
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d

# Проверить логи
docker compose -f docker-compose.prod.yml logs -f
```

---

## 📊 Мониторинг

### Docker логи
```bash
# Все логи
docker compose -f docker-compose.prod.yml logs -f

# Только API
docker compose -f docker-compose.prod.yml logs -f api
```

---

## 🆘 Troubleshooting

### Ошибка сборки

```bash
# Очистить всё
rm -rf node_modules
# Установить заново
npm ci
npm run build
```

### Контейнер не запускается

```bash
# Проверить логи
docker compose -f docker-compose.prod.yml logs api

# Пересобрать без кэша
docker compose -f docker-compose.prod.yml build --no-cache api
docker compose -f docker-compose.prod.yml up -d api
```

---

## 📝 Changelog развёртывания

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0 | Возможная дата | Первичный релиз OCR Service |
