# 🚀 Настройка Ollama Nemotron для OCR Service

## ⚡ Быстрый старт

### 1. Убедись, что Ollama установлен

```bash
ollama --version
```

Если не установлен:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Запусти Ollama сервер

```bash
ollama serve
```

Или в фоне (systemd):
```bash
systemctl start ollama
```

### 3. Загрузи модель Nemotron

```bash
ollama pull nemotron-3-super:cloud
```

Проверь, что модель загружена:
```bash
ollama list | grep nemotron
```

### 4. Настрой Docker для доступа к Ollama

**ВАЖНО:** На Linux `host.docker.internal` может не работать из коробки.

#### Вариант A: Используй `--add-host` в docker-compose.yml

Добавь в сервисы `api` и `celery_worker`:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

#### Вариант B: Используй IP хост-машины

1. Узнай IP хоста:
```bash
ip route show | grep default | awk '{print $3}'
```

2. Обновить `.env`:
```bash
OLLAMA_BASE_URL=http://172.17.0.1:11434/v1
```

### 5. Обнови .env (уже сделано)

```env
VLM_PROVIDER=ollama
OLLAMA_MODEL=nemotron-3-super:cloud
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
VLM_TIMEOUT=120
```

### 6. Перезапусти сервис

```bash
docker-compose down
docker-compose up -d
```

### 7. Протестируй

```bash
cd /path/to/ocr-service
source venv/bin/activate
python test_ollama_nemotron.py
```

## 🔧 Troubleshooting

### Ошибка подключения

**Проблема:** `Connection refused` или `Cannot connect to host`

**Решение:**
1. Проверь, что Ollama запущен: `ollama list`
2. Проверь порт: `curl http://localhost:11434/api/tags`
3. Для Docker добавь `extra_hosts` или используй IP хоста

### Модель не найдена

**Проблема:** `model not found`

**Решение:**
```bash
ollama pull nemotron-3-super:cloud
```

### Таймаут запроса

**Проблема:** Request timeout

**Решение:**
- Увеличь `VLM_TIMEOUT` в `.env` (уже стоит 120)
- Проверь нагрузку на GPU

## 📊 Мониторинг

Логи VLM экстракции:
```bash
docker-compose logs -f api | grep VLM
docker-compose logs -f api | grep Ollama
```

## ⚠️ Важные заметки

1. **Vision поддержка:** Nemotron-3-super:cloud должен поддерживать мультимодальные запросы (текст + изображение)
2. **Производительность:** Локальная модель использует твой GPU, скорость зависит от железа
3. **Docker на Linux:** Требуется `extra_hosts` или прямой IP для доступа к хосту

## 🔄 Переключение на резервный провайдер

Если Nemotron не работает, можно переключиться на Qwen:

```bash
# В .env
VLM_PROVIDER=qwen
QWEN_API_KEY=sk-fcfd6347fb58477daeb5ddd0174f6c5c
QWEN_MODEL=qwen-vl-max-latest
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Перезапусти:
```bash
docker-compose restart api
```

## 🎯 Что изменено

- ✅ Добавлен `ollama` как VLM провайдер
- ✅ Обновлён `app/config.py` с настройками Ollama
- ✅ Обновлён `app/services/vlm_extractor.py` с поддержкой Ollama
- ✅ Обновлён `.env` для использования Nemotron
- ✅ Обновлён `.env.example` с документацией
- ✅ Создан `test_ollama_nemotron.py` для тестирования
