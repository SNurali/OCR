# 🚀 Быстрый старт: Настройка LLM для OCR

## ⚡ Проблема

Твой API-ключ `sk-sp-aadd4a10ec6544e3950eed157d9fda29` - это **Plan-Specific Key** для Alibaba Cloud Code Studio. Он **не работает** с обычными Qwen моделями.

## ✅ Решение (3 варианта)

### Вариант 1: Ollama (БЕСПЛАТНО, локально)

1. Установи Ollama:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

2. Скачай модель:
```bash
ollama pull qwen2.5:7b
```

3. В `.env` оставь как есть:
```bash
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
```

### Вариант 2: Alibaba DashScope (платно, нужен новый ключ)

1. Получи обычный API ключ: https://dashscope.console.aliyun.com/
2. В `.env`:
```bash
LLM_PROVIDER=alibaba
LLM_MODEL=qwen-turbo
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### Вариант 3: OpenAI (платно)

1. Получи API ключ: https://platform.openai.com/
2. В `.env`:
```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
```

## 🧪 Тест

```bash
cd /path/to/ocr-service
source venv/bin/activate
python test_llm_api.py
```

## 📝 Что изменилось в коде

1. **`app/config.py`** - добавлена поддержка мульти-провайдера
2. **`app/services/llm_extractor.py`** - переписан для OpenAI-совместимого API
3. **`.env.example`** - обновлён с примерами для всех провайдеров

## 📄 Документация

- `ALIBABA_QWEN_SETUP.md` - подробная инструкция по Alibaba Qwen
- `QUICK_START_LLM.md` - этот файл, быстрый старт

---

**Рекомендация:** Начни с **Ollama** (бесплатно, быстро), потом переключишься на облачный API если нужно лучшее качество.
