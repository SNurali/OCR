#!/usr/bin/env python3
"""Тест Qwen-VL API"""

import httpx
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("QWEN_API_KEY", "sk-fcfd6347fb58477daeb5ddd0174f6c5c")
MODEL = os.getenv("QWEN_MODEL", "qwen-vl-max-latest")
BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")

IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

print(f"📋 Конфигурация Qwen:")
print(f"  Модель: {MODEL}")
print(f"  Base URL: {BASE_URL}")
print(f"  API Key: {'***' + API_KEY[-4:] if API_KEY else 'нет'}\n")

# Тест 1: Базовый текстовый запрос
print("Тест 1: Текстовый запрос...")
try:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Say hello in JSON"}],
                "temperature": 0.1,
                "max_tokens": 100
            },
            headers=headers
        )
        
        print(f"  Статус: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  ✅ Ответ: {resp.json()['choices'][0]['message']['content'][:100]}")
        else:
            print(f"  ❌ Ошибка: {resp.text[:300]}")
except Exception as e:
    print(f"  ❌ Исключение: {e}")

# Тест 2: С изображением
print("\nТест 2: Запрос с изображением...")
image_bytes = Path(IMAGE_PATH).read_bytes()
image_b64 = base64.b64encode(image_bytes).decode('utf-8')
image_url = f"data:image/png;base64,{image_b64}"

try:
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{BASE_URL}/chat/completions",
            json={
                "model": MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image briefly in JSON format"},
                        {"type": "image_url", "image_url": {"url": image_url, "detail": "high"}}
                    ]
                }],
                "temperature": 0.1,
                "max_tokens": 500
            },
            headers=headers
        )
        
        print(f"  Статус: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Ответ: {data['choices'][0]['message']['content'][:300]}")
        else:
            print(f"  ❌ Ошибка: {resp.text[:500]}")
except Exception as e:
    print(f"  ❌ Исключение: {e}")
