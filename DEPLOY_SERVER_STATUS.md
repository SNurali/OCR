# 🚀 OCR Service — Деплой на сервер

## Статус: ✅ РАБОТАЕТ

- **Сервер:** 172.16.252.32 (VPN)
- **SSH:** `ssh yoyo@172.16.252.32` (пароль: `01200120`)
- **API:** http://172.16.252.32:8001
- **Dashboard:** http://172.16.252.32:8080/dashboard.html
- **Prometheus:** http://172.16.252.32:9090
- **Grafana:** http://172.16.252.32:3000 (admin/admin)

## VLM Модель

- **Провайдер:** Qwen (Alibaba Cloud Plan)
- **Модель:** `qwen3.5-plus`
- **Base URL:** `https://coding-intl.dashscope.aliyuncs.com/v1`
- **API Key:** `sk-sp-aadd4a10ec6544e3950eed157d9fda29`
- **План истекает:** 2026-04-11 (4 дня осталось!)

## Быстрое обновление

```bash
# Подключиться к серверу
sshpass -p '01200120' ssh yoyo@172.16.252.32

# Обновить и перезапустить
cd /home/yoyo/ocr-service
echo '01200120' | sudo -S bash -c '
  git pull origin main &&
  docker compose -f docker-compose.prod.yml down &&
  docker compose -f docker-compose.prod.yml up -d --build &&
  docker compose -f docker-compose.prod.yml logs --tail=20 api
'
```

## Проверить статус

```bash
sshpass -p '01200120' ssh yoyo@172.16.252.32 \
  "echo '01200120' | sudo -S bash -c 'cd /home/yoyo/ocr-service && docker compose -f docker-compose.prod.yml ps'"
```

## Логи

```bash
# API
sshpass -p '01200120' ssh yoyo@172.16.252.32 \
  "echo '01200120' | sudo -S bash -c 'cd /home/yoyo/ocr-service && docker compose -f docker-compose.prod.yml logs -f api'"

# Celery Worker
sshpass -p '01200120' ssh yoyo@172.16.252.32 \
  "echo '01200120' | sudo -S bash -c 'cd /home/yoyo/ocr-service && docker compose -f docker-compose.prod.yml logs -f celery_worker'"

# Nginx
sshpass -p '01200120' ssh yoyo@172.16.252.32 \
  "echo '01200120' | sudo -S bash -c 'cd /home/yoyo/ocr-service && docker compose -f docker-compose.prod.yml logs -f nginx'"
```

## Админка дашборда

- **Username:** `admin`
- **Пароль:** `admin123` (если не работает — запусти `python reset_admin_password.py`)

## Файлы конфигурации

| Файл | Назначение |
|------|-----------|
| `docker-compose.prod.yml` | Production Docker Compose |
| `.env.prod` | Переменные окружения (Qwen API key, DB, etc.) |
| `nginx/nginx.conf` | Nginx конфигурация |
| `nginx/ssl/` | SSL сертификаты (самоподписанные) |

## ⚠️ Важно

1. **Qwen API ключ истекает 11 апреля 2026** — обнови до истечения
2. **Не удаляй volumes** `ocr_pgdata_prod` и `ocr_redisdata_prod` — там данные
3. **Не запускай** `docker system prune` — может удалить нужные образы
4. SSL сертификаты самоподписанные — для продакшена замени на настоящие
