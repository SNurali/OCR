# ⚡ Google Gemini - Быстрый старт за 2 минуты

## 1️⃣ Получи API ключ (30 сек)

👉 https://aistudio.google.com/apikey

1. Нажми **"Get API Key"**
2. Скопируй ключ (`AIzaSy...`)

## 2️⃣ Настрой .env (30 сек)

```bash
cd /path/to/ocr-service
```

Открой `.env` и добавь:

```bash
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
LLM_TIMEOUT=60
```

## 3️⃣ Протестируй (1 мин)

```bash
# Открой test_gemini.py и вставь ключ в строку 12
nano test_gemini.py

# Запусти
python test_gemini.py
```

## ✅ Готово!

Теперь сервис использует Gemini для извлечения данных из паспортов!

---

## 📊 Характеристики

| Параметр | Значение |
|----------|----------|
| Бесплатно | 1000 запросов/день |
| Скорость | 1-2 секунды |
| Качество OCR | ⭐⭐⭐⭐⭐ |
| Vision API | ✅ Да |

## 🔄 Переключение между провайдерами

```bash
# Ollama (локально)
LLM_PROVIDER=ollama

# Google Gemini (облако)
LLM_PROVIDER=google

# OpenAI (облако)
LLM_PROVIDER=openai
```

Просто измени `.env` и перезапусти сервис!
