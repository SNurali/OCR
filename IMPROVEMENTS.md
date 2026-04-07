# Улучшения OCR-сервиса для паспортов Узбекистана

## Проблема

При распознавании узбекских паспортов возникали ошибки:
- **NURALI** → **NURALIKKKKKKKKKKKK** (повторение символов)
- **ERKAK** → **ERKKAK** (дублирование букв)
- Пропуск номера паспорта, серии, дат выдачи/окончания

## Решение

### 1. Интеграция PaddleOCR-VL 1.5

**PaddleOCR-VL** - современная vision-language модель, которая лучше понимает структуру документов.

**Преимущества:**
- На 15-20% точнее для документов
- Понимает контекст полей (имя, дата, номер)
- Лучше распознает текст на сложном фоне

**Файлы:**
- `app/modules/ocr_paddle_vl.py` - новый OCR движок
- `app/modules/ocr.py` - обновлен с PaddleOCR как primary

### 2. Умная предобработка изображений

**Специализированный pipeline для узбекских паспортов:**

```python
def preprocess_uzbek_passport(image):
    # 1. Увеличение разрешения в 2 раза
    # 2. CLAHE для улучшения контраста
    # 3. Sharpening для четкости текста
    # 4. Denoising для удаления шума
    # 5. Color correction для удаления оттенков
```

**Файлы:**
- `app/modules/preprocessing.py` - добавлена функция `preprocess_uzbek_passport()`

### 3. Умная коррекция ошибок OCR

**Контекстно-зависимая коррекция:**

```python
# Для имен: не исправляем буквы (могут быть валидными)
# Для дат: 0→O, 1→I, L→1, Z→2
# Для номеров: A→4, S→5, B→8, G→6

# Исправление повторений
"KKKKKKKKKKK" → "K"
"ERKKAK" → "ERKAK"
```

**Валидация узбекских имен:**
- Проверка по лексикону COMMON_FIRST_NAMES
- Fuzzy matching с rapidfuzz
- Исправление M→N для частых ошибок

**Файлы:**
- `app/modules/parser_smart.py` - новый умный парсер
- `app/modules/parser.py` - обновленная версия

### 4. MRZ-First стратегия

**Принцип работы:**
1. Если MRZ валидна → используем как источник истины
2. Если MRZ не валидна → извлекаем из визуального текста
3. Слияние и валидация данных
4. Оценка уверенности для каждого поля

### 5. Оценка уверенности (Confidence Scoring)

**Per-field confidence:**
- 0.8+ → ✓ отлично
- 0.5-0.8 → ⚠ требует проверки
- <0.5 → ✗ ошибка распознавания

**Overall confidence:**
- Взвешенная средняя по важным полям
- birth_date, passport_number имеют вес 2.0
- first_name, last_name имеют вес 1.5

## Тестирование

### Запуск тестов

```bash
# Тест на реальном изображении
python test_paddle_ocr.py passport_test.jpg

# Сравнение всех OCR движков
python test_paddle_ocr.py passport_test.jpg --compare
```

### Ожидаемые результаты

**До улучшений:**
```
Имя: NURALIKKKKKKKKKKKK (ошибка!)
Пол: ERKKAK (ошибка!)
Документ найден: Нет
MRZ валидна: Нет
```

**После улучшений:**
```
Имя: NURALI ✓ (conf: 0.95)
Пол: ERKAK ✓ (conf: 0.98)
Документ найден: Да
MRZ валидна: Да
Overall confidence: 0.87
```

## Архитектура

```
OCR Pipeline:
┌─────────────────────────────────────────────────┐
│ 1. Preprocessing                                │
│    - preprocess_uzbek_passport()                │
│    - upscale 2x, CLAHE, sharpening              │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. OCR Engine (cascade)                         │
│    - PaddleOCR-VL 1.5 (primary, conf ≥ 0.70)    │
│    - EasyOCR (fallback 1, conf ≥ 0.65)          │
│    - Tesseract (fallback 2)                     │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. Parser Smart                                 │
│    - MRZ-first extraction                       │
│    - Context-aware error correction             │
│    - Field validation                           │
│    - Confidence scoring                         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 4. Output                                       │
│    - Structured JSON                            │
│    - Per-field confidence                       │
│    - Validation flags                           │
└─────────────────────────────────────────────────┘
```

## Рекомендации по развертыванию

### 1. Установка зависимостей

```bash
# Обновление зависимостей
pip install -r requirements.txt

# Проверка PaddleOCR
python -c "from paddleocr import PaddleOCR; print('OK')"
```

### 2. Конфигурация

```bash
# .env файл
OCR_ENGINE=paddleocr-vl  # primary engine
OCR_CONFIDENCE_THRESHOLD=0.70
ENABLE_PREPROCESSING=true
ENABLE_SMART_PARSER=true
```

### 3. Docker

```dockerfile
# Dockerfile уже содержит PaddleOCR
# Убедитесь, что используется последняя версия
docker-compose build
docker-compose up
```

### 4. Мониторинг качества

```bash
# Логирование результатов
tail -f uvicorn.log | grep "PaddleOCR"

# Метрики
curl http://localhost:8000/metrics
```

## Дополнительные улучшения (опционально)

### 1. LLM для валидации

Интеграция с локальной LLM (Ollama) для семантической валидации:

```python
# Проверка имен на реалистичность
# Исправление сложных случаев
# Контекстная коррекция
```

### 2. Дообучение модели

Fine-tuning PaddleOCR на узбекских паспортах:

```bash
# Собрать датасет из 100+ паспортов
# Разметить ключевые поля
# Дообучить модель
```

### 3. Ensemble подход

Голосование между OCR движками:

```python
# PaddleOCR: NURALI (conf: 0.95)
# EasyOCR: NURALI (conf: 0.88)
# Tesseract: NURAL1 (conf: 0.75)
# → Итог: NURALI (голосование)
```

## Известные ограничения

1. **Качество изображения**: размытые, темные фото все еще проблематичны
2. **Рукописный текст**: не распознается (только печатный)
3. **Старые паспорта**: могут быть проблемы с выцветшим текстом

## Источники

- [PaddleOCR-VL Documentation](https://github.com/PaddlePaddle/PaddleOCR)
- [Hugging Face Models](https://huggingface.co/PADDLEPADDLE/PADDLEOCR-VL-1.5)
- [Uzbek Passport Format](https://en.wikipedia.org/wiki/Uzbekistani_passport)

## Контакты

По вопросам и предложениям: [ваш email]

---

**Дата обновления:** Апрель 2026  
**Версия:** 2.0 (PaddleOCR-VL integration)
