# 🚀 Инструкция по обновлению OCR-сервиса

## Что было обновлено (Апрель 2026):

1. **PaddleOCR-VL 1.5** интегрирован как основной OCR движок
2. **Умная предобработка** для узбекских паспортов
3. **Контекстная коррекция ошибок** OCR
4. **Приоритет PaddleOCR** над EasyOCR и Tesseract

---

## 📋 Чеклист обновления:

### 1. Проверка зависимостей

```bash
cd "/home/mrnurali/LOW PROJECTS/ocr-service"

# Проверка PaddleOCR
python -c "from paddleocr import PaddleOCR; print('OK')"

# Проверка всех модулей
python -c "
from app.services.paddleocr_service import paddleocr_service
from app.services.ocr_service import ocr_pipeline
print('✓ Все модули импортируются')
"
```

### 2. Перезапуск сервиса

```bash
# Остановить текущий процесс (если работает)
pkill -f "uvicorn|python.*main.py"

# Запустить заново
cd src && python main.py

# Или через uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8443
```

### 3. Тестирование

```bash
# Тест через API
curl -X POST "http://localhost:8443/test-ocr" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@passport_test.jpg"
```

### 4. Проверка логов

```bash
# Логи должны показывать:
tail -f uvicorn.log | grep "PaddleOCR-VL"

# Ожидаемый вывод:
# "Запуск PaddleOCR-VL (основной)..."
# "PaddleOCR-VL: X строк, confidence=0.XX"
```

---

## 🎯 Ожидаемые улучшения:

### До обновления:
```
Имя: NURALIKKKKKKKKKKKK ❌
Пол: ERKKAK ❌
Номер паспорта: Не найден ❌
Overall: 52%
```

### После обновления:
```
Имя: NURALI ✓ (conf: 0.95)
Пол: ERKAK ✓ (conf: 0.98)
Номер паспорта: AM79792 ✓ (conf: 0.87)
Overall: 87%+
```

---

## 🔧 Обновленные файлы:

```
app/services/
├── paddleocr_service.py    # Обновлен: PaddleOCR-VL + предобработка
├── ocr_service.py          # Обновлен: приоритет PaddleOCR-VL
└── ocr_analyzer.py         # Без изменений (использует ocr_service)

app/modules/
├── ocr_paddle_vl.py        # Новый: отдельный PaddleOCR модуль
├── parser_smart.py         # Новый: умный парсер
└── preprocessing.py        # Обновлен: preprocess_uzbek_passport()
```

---

## ⚠️ Возможные проблемы:

### 1. PaddleOCR не загружается
```bash
# Решение: переустановить
pip uninstall paddlepaddle paddleocr -y
pip install paddlepaddle paddleocr
```

### 2. Ошибка "CUDA out of memory"
```bash
# PaddleOCR по умолчанию использует CPU
# Для GPU нужно установить paddlepaddle-gpu
pip install paddlepaddle-gpu
```

### 3. Медленная обработка
```bash
# Первое запущение скачивает модели (~100MB)
# Последующие запуски быстрее
# Для ускорения: использовать GPU
```

---

## 📊 Метрики качества:

Запустите тест на 10-20 паспортах и сравните:

```python
# test_comparison.py
import requests

test_images = [
    "passport_test.jpg",
    "passport_test2.jpg",
    # ... больше файлов
]

for img in test_images:
    with open(img, 'rb') as f:
        response = requests.post(
            "http://localhost:8443/test-ocr",
            files={"file": f}
        )
        result = response.json()
        print(f"{img}:")
        print(f"  OCR Confidence: {result['ocr_confidence']:.2%}")
        print(f"  Overall: {result['overall_confidence']:.2%}")
        print(f"  MRZ Valid: {result['mrz_valid']}")
        print()
```

---

## 📞 Контакты

При проблемах:
1. Проверь логи: `tail -f uvicorn.log`
2. Проверь PaddleOCR: `python -c "from paddleocr import PaddleOCR"`
3. Перезапусти сервис: `pkill -f uvicorn && python src/main.py`

---

**Дата обновления:** Апрель 2026  
**Версия:** 2.0 (PaddleOCR-VL integration)
