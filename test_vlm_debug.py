#!/usr/bin/env python3
"""
Дебаг VLM запроса с изображением
"""

import httpx
import json
import base64
from pathlib import Path

IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

from dotenv import load_dotenv
import os
load_dotenv()

API_KEY = os.getenv("OLLAMA_API_KEY", "")
MODEL = os.getenv("OLLAMA_MODEL", "nemotron-3-super:cloud")
BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1").rstrip("/")

print(f"📋 Конфигурация:")
print(f"  Модель: {MODEL}")
print(f"  Base URL: {BASE_URL}")
print(f"  API Key: {'***' + API_KEY[-4:] if API_KEY else 'нет'}\n")

# Загружаем изображение
image_bytes = Path(IMAGE_PATH).read_bytes()
image_b64 = base64.b64encode(image_bytes).decode('utf-8')
image_url = f"data:image/png;base64,{image_b64}"

print(f"📷 Изображение: {len(image_bytes) / 1024:.1f} KB")
print(f"   Base64 размер: {len(image_b64) / 1024:.1f} KB\n")

SYSTEM_PROMPT = """Ты — эксперт по извлечению данных идентификации KYC. Тебе дано фото паспорта или ID-карты.

Твоя задача: ВИЗУАЛЬНО прочитать данные и вернуть строго валидный JSON документ с ключами:
- first_name: имя (латиницей)
- last_name: фамилия (латиницей)
- middle_name: отчество (латиницей)
- birth_date: дата рождения (DD.MM.YYYY)
- gender: пол (M/F)
- nationality: гражданство
- passport_number: номер паспорта
- issue_date: дата выдачи (DD.MM.YYYY)
- expiry_date: дата окончания (DD.MM.YYYY)
- issued_by: кем выдан
- pinfl: ПИНФЛ (строго 14 цифр)

ПРАВИЛА:
1. Узбекистан: Фамилии на -OV/-EV, отчества на -OVICH/-QIZI. Пол: ERKAK=M, AYOL=F.
2. ПИНФЛ: 14 цифр. Если 15 — возьми первые 14.
3. Даты: DD.MM.YYYY.
4. Паспорт Узбекистана: 2 буквы + 7 цифр.
5. Если нечитаемо — пустая строка. Не выдумывай.
6. Верни ТОЛЬКО JSON.
"""

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": SYSTEM_PROMPT},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ],
    "temperature": 0.1,
    "max_tokens": 4096
}

headers = {
    "Content-Type": "application/json"
}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

print("⏳ Отправка запроса к Nemotron...")
print(f"   Payload size: {len(json.dumps(payload)) / 1024:.1f} KB\n")

try:
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{BASE_URL}/chat/completions",
            json=payload,
            headers=headers
        )
        
        print(f"📡 Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            print("\n✅ Ответ Nemotron:")
            print("="*60)
            print(content[:2000])
            print("="*60)
            
            # Пробуем распарсить JSON
            content_clean = content.strip()
            if content_clean.startswith("```json"):
                content_clean = content_clean[7:]
            elif content_clean.startswith("```"):
                content_clean = content_clean[3:]
            if content_clean.endswith("```"):
                content_clean = content_clean[:-3]
            content_clean = content_clean.strip()
            
            try:
                parsed = json.loads(content_clean)
                print("\n✅ Распарсенный JSON:")
                print(json.dumps(parsed, indent=2, ensure_ascii=False))
            except:
                print("\n⚠️ Не удалось распарсить JSON")
                
        else:
            print(f"\n❌ Ошибка:")
            print(response.text[:1000])
            
except Exception as e:
    print(f"\n❌ Исключение: {e}")
