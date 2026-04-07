#!/usr/bin/env python3
"""
Тест Ollama Nemotron для OCR сервиса
"""

import json
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "nemotron-3-super:cloud")
API_KEY = os.getenv("OLLAMA_API_KEY", "")
BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1").rstrip("/")

print(f"📋 Конфигурация Ollama Nemotron:")
print(f"  Модель: {MODEL}")
print(f"  Base URL: {BASE_URL}")
print(f"  API Key: {'***' + API_KEY[-4:] if API_KEY else 'не задан'}")
print()


def test_ollama_basic():
    """Базовый тест Ollama API"""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    client = httpx.Client(base_url=BASE_URL, timeout=120, headers=headers)

    try:
        response = client.post(
            "/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "Return ONLY valid JSON."},
                    {
                        "role": "user",
                        "content": "Extract name and age from: 'John Doe, 25 years old'",
                    },
                ],
                "temperature": 0.1,
                "max_tokens": 200,
            },
        )

        response.raise_for_status()
        data = response.json()
        print("✅ Успешный ответ от Ollama Nemotron:")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
        return True

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP ошибка: {e.response.status_code}")
        print(e.response.text)
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_passport_extraction():
    """Тест извлечения данных паспорта"""
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    client = httpx.Client(base_url=BASE_URL, timeout=120, headers=headers)

    ocr_text = """
    REPUBLIC OF UZBEKISTAN
    PASSPORT
    FA 1234567
    Surname: IBRAGIMOV
    Given names: RUSTAM
    Nationality: UZB
    Date of birth: 15 JAN 1990
    Sex: M
    Date of issue: 10 FEB 2020
    Date of expiry: 10 FEB 2030
    MRZ: P<UZBIBRAGIMOV<<RUSTAM<<<<<<<<<<<<<<<<<<
         FA12345679UZB9001155M3002102<<<<<<<<<<<<<<04
    """

    prompt = f"""
На основе OCR текста извлеки данные паспорта в JSON формате:

{ocr_text}

Верни JSON со следующими полями:
- surname (фамилия)
- given_names (имя)
- passport_number (номер паспорта)
- nationality (гражданство)
- date_of_birth (дата рождения, формат YYYY-MM-DD)
- sex (пол)
- date_of_issue (дата выдачи, формат YYYY-MM-DD)
- date_of_expiry (дата истечения, формат YYYY-MM-DD)

Важно: Верни ТОЛЬКО JSON, без markdown и дополнительных символов.
"""

    try:
        response = client.post(
            "/chat/completions",
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a passport data extraction expert. Return ONLY valid JSON without any markdown formatting.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 500,
            },
        )

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Очистка от markdown
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)

        print("✅ Извлечённые данные паспорта:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Тест 1: Базовый запрос к Ollama Nemotron")
    print("=" * 60)
    test_ollama_basic()

    print("\n" + "=" * 60)
    print("Тест 2: Извлечение данных паспорта")
    print("=" * 60)
    test_passport_extraction()

    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
    print("=" * 60)
