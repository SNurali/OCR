# 🔄 Статус пересборки Docker

## Проблема

Дашборд показывал старые данные (мусор из OCR) потому что Docker контейнер использовал **старый код** без LLM интеграции.

## Решение

### 1. Исправлена версия olmocr
```bash
# requirements.txt
olmocr>=0.4.0  # было olmocr>=2.0.0 (не существует)
```

### 2. Пересобран Docker образ
```bash
docker compose down
docker rmi ocr-service-api ocr-service-celery_worker
docker compose build api
docker compose up -d
```

### 3. Изменения в коде

**app/modules/parser.py:**
- Добавлен параметр `ocr_confidence`
- LLM вызывается при confidence < 50%
- LLM переписывает ВСЕ поля при плохом качестве OCR

**app/services/llm_extractor.py:**
- Улучшенный промпт с подсказками для Uzbekistan ID
- Подсказки по форматам (фамилии -OV/-EV, имена, PINFL 14 цифр)

**app/services/pipeline.py:**
- Передаёт `ocr_result.confidence` в парсер

## Ожидаемый результат

**До пересборки:**
```
Фамилия: В ❌
Имя: O9S5M32O3237XXKXULB ❌
Дата рождения: Не найдено ❌
```

**После пересборки:**
```
Фамилия: SULAYMANOV ✅
Имя: NURALI ✅
Дата рождения: 15.02.1996 ✅
Пол: M ✅
Гражданство: UZB ✅
ПИНФЛ: 51509860290078 ✅
```

## Проверка

```bash
# Проверить что контейнер использует новый образ
docker ps | grep ocr-service-api

# Посмотреть логи
docker compose logs --tail=50 api | grep -E '(LLM|Groq)'

# Тест API
curl http://localhost:8001/
```

## Время сборки

~10-15 минут (зависит от интернета и CPU)

---

**Статус:** ⏳ Docker строится...
