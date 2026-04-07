#!/usr/bin/env python3
"""Тест Qwen3.5-plus с Cloud Plan URL"""

import httpx
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("QWEN_API_KEY", "sk-sp-aadd4a10ec6544e3950eed157d9fda29")
MODEL = os.getenv("QWEN_MODEL", "qwen3.5-plus")
BASE_URL = os.getenv("QWEN_BASE_URL", "https://coding-intl.dashscope.aliyuncs.com/v1").rstrip("/")

IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

print(f"📋 Конфигурация Qwen Cloud Plan:")
print(f"  Модель: {MODEL}")
print(f"  Base URL: {BASE_URL}")
print(f"  API Key: {'***' + API_KEY[-4:] if API_KEY else 'нет'}\n")

# Тест 1: Базовый текстовый запрос
print("🧪 Тест 1: Текстовый запрос...")
try:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE_URL}/chat/completions", json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Say hello in JSON"}],
            "temperature": 0.1, "max_tokens": 100
        }, headers=headers)
        
        print(f"  Статус: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  ✅ {resp.json()['choices'][0]['message']['content'][:100]}")
        else:
            print(f"  ❌ {resp.text[:300]}")
except Exception as e:
    print(f"  ❌ {e}")

# Тест 2: С изображением паспорта
print("\n🧪 Тест 2: Извлечение данных паспорта...")
image_bytes = Path(IMAGE_PATH).read_bytes()
image_b64 = base64.b64encode(image_bytes).decode('utf-8')

SYSTEM_PROMPT = """Extract data from this passport image and return ONLY valid JSON:
{
  "first_name": "",
  "last_name": "",
  "middle_name": "",
  "birth_date": "DD.MM.YYYY",
  "gender": "M/F",
  "nationality": "",
  "passport_number": "",
  "issue_date": "DD.MM.YYYY",
  "expiry_date": "DD.MM.YYYY",
  "issued_by": "",
  "pinfl": "14 digits"
}
If a field is unreadable, use empty string. Return ONLY JSON, no markdown."""

try:
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    with httpx.Client(timeout=180) as client:
        resp = client.post(f"{BASE_URL}/chat/completions", json={
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 1024
        }, headers=headers)
        
        print(f"  Статус: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            content = data['choices'][0]['message']['content']
            print(f"  ✅ Raw response:")
            print(f"  {content[:500]}")
            
            # Parse JSON
            content_clean = content.strip()
            if content_clean.startswith("```json"):
                content_clean = content_clean[7:]
            elif content_clean.startswith("```"):
                content_clean = content_clean[3:]
            if content_clean.endswith("```"):
                content_clean = content_clean[:-3]
            
            try:
                parsed = json.loads(content_clean)
                print(f"\n  📋 Parsed JSON:")
                print(f"  {json.dumps(parsed, indent=2, ensure_ascii=False)}")
                filled = sum(1 for v in parsed.values() if v)
                print(f"\n  📊 Заполнено полей: {filled}/{len(parsed)}")
            except:
                print(f"\n  ⚠️ Не JSON или ошибка парсинга")
        else:
            print(f"  ❌ {resp.text[:500]}")
except Exception as e:
    print(f"  ❌ {e}")
