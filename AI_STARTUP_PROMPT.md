# 🤖 Промт для ИИ: Запуск OCR Service с Groq LLM

## 📋 Контекст проекта

Это **OCR сервис для распознавания паспортов** с интеграцией **Groq LLM** для улучшения извлечения данных.

**Стек:**
- Backend: FastAPI + Python 3.12
- Database: PostgreSQL + SQLAlchemy
- Cache: Redis + Celery
- OCR: EasyOCR + PaddleOCR
- **LLM: Groq (Llama 3.3 70B)** ⭐
- Frontend: HTML Dashboard

---

## 🚀 Как запустить проект

### Быстрый старт (5 минут)

```bash
# 1. Перейди в директорию проекта
cd /home/mrnurali/LOW\ PROJECTS/ocr-service

# 2. Активируй виртуальное окружение
source venv/bin/activate

# 3. Проверь зависимости
pip install -r requirements.txt

# 4. Проверь конфигурацию
cat .env

# 5. Запусти сервис
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Через Docker (если работает)

```bash
docker-compose up -d
docker-compose logs -f app
```

---

## 🔑 Критичные конфигурации

### 1. LLM Provider (Groq)

**Файл:** `.env`

```bash
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<YOUR_GROQ_API_KEY>
LLM_TIMEOUT=60
```

**Важно:** 
- ✅ Groq активен и работает
- ⚠️ Лимит: 800 запросов/день
- 🔄 Альтернативы: Gemini, Ollama (см. `.env.example`)

### 2. Database

```bash
DB_HOST=localhost
DB_PORT=5432
DB_USER=ocr_user
DB_PASSWORD=ocr_secure_password
DB_NAME=ocr_service
```

### 3. Redis

```bash
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
```

---

## 🧪 Как работает LLM интеграция

### Поток данных

```
1. Пользователь загружает изображение паспорта
   ↓
2. OCR извлекает текст (EasyOCR/PaddleOCR)
   ↓
3. Parser извлекает поля (regex + словари)
   ↓
4. LLM (Groq) улучшает результат
   ↓
5. Финальные данные → Dashboard
```

### Ключевые файлы

| Файл | Описание |
|------|----------|
| `app/services/llm_extractor.py` | LLM экстрактор (Groq/Gemini/Ollama) |
| `app/modules/parser.py` | Парсер с LLM enhancement |
| `app/services/gemini_service.py` | Gemini API сервис |
| `app/config.py` | Конфигурация LLM |

### Пример использования LLM

```python
from app.services.llm_extractor import llm_extractor

ocr_text = "Surname: IBRAGIMOV\nGiven names: RUSTAM\n..."
mrz_data = {"surname": "IBRAGIMOV", "given_names": "RUSTAM"}

# Извлечение через LLM
result = llm_extractor.extract_fields(ocr_text, mrz_data)
print(result)
# {'surname': 'IBRAGIMOV', 'given_names': 'RUSTAM', ...}
```

---

## 📊 API Endpoints

### Основные

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/api/passport/` | POST | Загрузка паспорта |
| `/api/passport/{id}` | GET | Получение результата |
| `/api/admin/` | GET | Admin dashboard |
| `/api/auth/login` | POST | Логин |

### Тестовые

```bash
# Health check
curl http://localhost:8000/

# Загрузка паспорта
curl -X POST http://localhost:8000/api/passport/ \
  -F "file=@passport.jpg"

# Swagger UI
open http://localhost:8000/docs
```

---

## 🔍 Диагностика

### Проверка LLM

```bash
python -c "
from app.services.llm_extractor import llm_extractor
print(f'Provider: {llm_extractor.provider}')
print(f'Model: {llm_extractor.model}')
print(f'Enabled: {llm_extractor.enabled}')
"
```

### Проверка парсера

```bash
python -c "
from app.modules.parser import extract_from_text
result = extract_from_text('Surname: IBRAGIMOV\\nGiven names: RUSTAM', {})
print(result)
"
```

### Логи

```bash
# Uvicorn логи
tail -f uvicorn.log

# Приложение логи
docker-compose logs -f app
```

---

## ⚠️ Частые проблемы

### 1. LLM не работает

**Проблема:** `LLM API key is not configured`

**Решение:**
```bash
# Проверь .env
cat .env | grep LLM_API_KEY

# Если пусто, добавь:
LLM_API_KEY=<YOUR_GROQ_API_KEY>
```

### 2. Permission denied: /app

**Проблема:** Сервис пытается создать `/app/uploads`

**Решение:**
```bash
sudo mkdir -p /app/uploads/passports
sudo chmod 777 /app/uploads/passports
```

### 3. Docker не запускается

**Проблема:** `http+docker` схема не поддерживается

**Решение:** Запустить через uvicorn напрямую:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Лимит Groq исчерпан

**Проблема:** `429 Too Many Requests`

**Решение:**
1. Подождать сброса (24 часа)
2. Переключиться на Gemini:
   ```bash
   LLM_PROVIDER=google
   LLM_API_KEY=AIzaSyBTznnVVNgK7hAVGgNJEkzSYzugPeLKExA
   ```
3. Или на Ollama (локально):
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull qwen2.5:7b
   LLM_PROVIDER=ollama
   ```

---

## 📚 Документация

| Файл | Описание |
|------|----------|
| `SESSION_REPORT_GROQ_INTEGRATION.md` | Полный отчёт о сессии |
| `GROQ_SETUP.md` | Настройка Groq |
| `GEMINI_SETUP.md` | Настройка Gemini |
| `ALIBABA_QWEN_SETUP.md` | Настройка Alibaba Qwen |
| `QUICK_START_LLM.md` | Быстрый старт LLM |
| `README.md` | Основная документация проекта |

---

## 🎯 Чеклист перед запуском

- [ ] Проверь `.env` (LLM_API_KEY, DB, Redis)
- [ ] Запусти PostgreSQL (`docker-compose up -d postgres`)
- [ ] Запусти Redis (`docker-compose up -d redis`)
- [ ] Проверь зависимости (`pip install -r requirements.txt`)
- [ ] Тест LLM (`python -c "from app.services.llm_extractor import llm_extractor; print(llm_extractor.provider)"`)
- [ ] Запусти сервис (`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`)
- [ ] Проверь API (`curl http://localhost:8000/`)

---

## 💡 Советы

1. **Горячая перезагрузка:** `--reload` флаг для авто-рестарта
2. **Workers:** `--workers 2` для многопоточности
3. **Logs:** Включи JSON логи в `.env`: `LOG_FORMAT=json`
4. **Кэширование:** Redis кэширует результаты OCR
5. **LLM fallback:** Если Groq недоступен → парсинг правилами

---

**Готово!** 🚀 Сервис готов к работе.

**API:** http://localhost:8000  
**Dashboard:** http://localhost:8000/api/admin/  
**Swagger:** http://localhost:8000/docs
