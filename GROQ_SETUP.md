# 🚀 Настройка Groq API (БЕСПЛАТНО)

## ⚡ Почему Groq?

- ✅ **Бесплатно** — 30 запросов/минуту, 800/день
- ✅ **Очень быстро** — LPU чипы, быстрее GPU
- ✅ **Отличное качество** — Llama 3.2 90B Vision
- ✅ **Без кредитной карты**

## 📋 Пошаговая инструкция

### Шаг 1: Получи API ключ (30 сек)

1. Перейди на https://console.groq.com/keys
2. Нажми **"Create API Key"**
3. Скопируй ключ (начинается с `gsk_...`)

### Шаг 2: Настрой .env

```bash
cd /path/to/ocr-service
nano .env
```

Замени:
```bash
LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Шаг 3: Тест

```bash
source venv/bin/activate
python test_llm_api.py
```

## 📊 Тарифы Groq

| Тариф | Лимиты | Цена |
|-------|--------|------|
| **Free** | 30 req/min, 800/day | $0 |
| **Scale** | Выше лимиты | $0.15 / 1M tokens |

## 🔄 Переключение на Gemini (когда лимит сбросится)

```bash
# В .env измени:
LLM_PROVIDER=google
LLM_API_KEY=AIzaSyBTznnVVNgK7hAVGgNJEkzSYzugPeLKExA
```

## 🎯 Модели Groq для OCR

| Модель | Качество | Скорость |
|--------|----------|----------|
| `llama-3.2-90b-vision-preview` | ⭐⭐⭐⭐⭐ | ⚡⚡⚡⚡⚡ |
| `llama-3.1-70b-versatile` | ⭐⭐⭐⭐ | ⚡⚡⚡⚡⚡ |

---

**Готово!** 🎉
