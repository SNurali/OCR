# 📝 Настройка Alibaba Qwen API для OCR Service

## ⚠️ Проблема с текущим API ключом

Твой текущий ключ `sk-sp-aadd4a10ec6544e3950eed157d9fda29` - это **Plan-Specific API Key** для Alibaba Cloud Code Studio. Он работает только внутри их платформы и не поддерживает стандартные модели Qwen.

## ✅ Решение

### Вариант 1: Получить обычный DashScope API Key

1. Зарегистрируйся на https://dashscope.console.aliyun.com/
2. Создай обычный API ключ (не plan-specific)
3. Добавь в `.env`:

```bash
# LLM (Alibaba Qwen - обычный API ключ)
LLM_PROVIDER=alibaba
LLM_MODEL=qwen-turbo
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_TIMEOUT=60
```

### Вариант 2: Использовать OpenAI API

```bash
# LLM (OpenAI)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_TIMEOUT=60
```

### Вариант 3: Использовать Ollama (локально)

```bash
# LLM (Ollama - локально)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=
LLM_TIMEOUT=60
```

## 📋 Доступные модели Qwen

| Модель | Описание | Скорость | Качество |
|--------|----------|----------|----------|
| qwen-turbo | Быстрая, дешёвая | ⚡⚡⚡ | ⭐⭐ |
| qwen-plus | Сбалансированная | ⚡⚡ | ⭐⭐⭐⭐ |
| qwen-max | Максимальное качество | ⚡ | ⭐⭐⭐⭐⭐ |
| qwen-long | Для длинных текстов | ⚡⚡ | ⭐⭐⭐⭐ |

## 🧪 Тестирование

После настройки API ключа запусти тест:

```bash
cd /path/to/ocr-service
source venv/bin/activate  # или .venv/bin/activate
python test_alibaba_qwen.py
```

## 🔧 Обновление конфига

1. Скопируй `.env.example` в `.env`:
```bash
cp .env.example .env
```

2. Отредактируй `.env` и добавь API ключ:
```bash
LLM_API_KEY=sk-your-actual-api-key-here
```

3. Перезапусти сервис:
```bash
docker-compose restart
```

## 📊 Мониторинг использования

Логи вызовов LLM:
```bash
docker-compose logs -f app | grep LLM
```

## 🆘 Troubleshooting

### Ошибка 401 Unauthorized
- Неверный API ключ
- Ключ истёк
- Ключ не активирован

### Ошибка 400 Bad Request
- Модель не поддерживается
- Неверный формат запроса

### Ошибка 429 Too Many Requests
- Превышен лимит запросов
- Нужно увеличить квоту в консоли Alibaba

### Ошибка Timeout
- Увеличь `LLM_TIMEOUT` в `.env`
- Проверь сетевое подключение
