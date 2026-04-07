# 🚀 Настройка Google Gemini для OCR

## ✅ Почему Gemini?

- **Отличное распознавание текста** — одна из лучших моделей для OCR
- **Бесплатно** — 1000 запросов/день (хватит для начала)
- **Vision API** — может читать текст напрямую с изображений
- **Быстро** — ответ за 1-2 секунды

## 📋 Пошаговая инструкция

### Шаг 1: Получи API ключ

1. Перейди на https://aistudio.google.com/apikey
2. Нажми **"Get API Key"**
3. Скопируй ключ (начинается с `AIzaSy...`)

### Шаг 2: Настрой .env

```bash
cd /path/to/ocr-service
cp .env.example .env
nano .env  # или твой редактор
```

Добавь/измени строки:

```bash
LLM_PROVIDER=google
LLM_MODEL=gemini-2.0-flash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
LLM_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
LLM_TIMEOUT=60
```

### Шаг 3: Тестирование

```bash
# Вставь API ключ в test_gemini.py
nano test_gemini.py  # строка 12: API_KEY = "AIzaSy..."

# Запусти тест
source venv/bin/activate
python test_gemini.py
```

### Шаг 4: Запуск сервиса

```bash
docker-compose restart
```

## 💰 Тарифы Gemini

| Тариф | Лимиты | Цена |
|-------|--------|------|
| **Free** | 1000 запросов/день | $0 |
| **Pay-as-you-go** | 60 запросов/мин | $0.075 / 1K tokens |

## 🔧 Модели Gemini

| Модель | Описание | Рекомендация |
|--------|----------|--------------|
| `gemini-2.0-flash` | Быстрая, сбалансированная | ⭐ Для OCR |
| `gemini-2.0-flash-lite` | Ещё быстрее, дешевле | Для массовых запросов |
| `gemini-2.0-pro` | Максимальное качество | Для сложных случаев |

## 🎯 Vision API (бонус!)

Gemini может читать текст **напрямую с изображений** без предварительного OCR:

```python
from app.services.gemini_service import gemini_service

result = gemini_service.extract_from_image("passport.jpg")
print(result)
```

## 🆘 Troubleshooting

### Ошибка 400 Bad Request
- Проверь формат API ключа
- Убедись что модель указана верно

### Ошибка 403 Forbidden
- API ключ не активирован
- Зайди в https://console.cloud.google.com и активируй Gemini API

### Ошибка 429 Too Many Requests
- Превышен лимит 1000 запросов/день
- Подожди до завтра или перейди на платный тариф

### Ошибка Timeout
- Увеличь `LLM_TIMEOUT` в `.env`
- Проверь интернет-соединение

## 📊 Мониторинг

Логи вызовов:
```bash
docker-compose logs -f app | grep Gemini
```

## 🔗 Ссылки

- [Google AI Studio](https://aistudio.google.com/)
- [Gemini API Docs](https://ai.google.dev/api)
- [Модели и цены](https://ai.google.dev/pricing)

---

**Готово!** 🎉 Теперь твой OCR сервис использует Google Gemini для извлечения данных из паспортов!
