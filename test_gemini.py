#!/usr/bin/env python3
"""
Тест Google Gemini API для OCR
Получи API ключ: https://aistudio.google.com/apikey
"""

import json
import httpx

# Вставь свой API ключ сюда или используй .env
API_KEY = ""  # AIzaSy...
MODEL = "gemini-2.0-flash"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def test_gemini_text():
    """Тест извлечения текста"""
    if not API_KEY:
        print("❌ API ключ не задан!")
        print("📝 Получи ключ: https://aistudio.google.com/apikey")
        return False

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
    """

    prompt = f"""Ты эксперт по извлечению данных из паспортов.

OCR текст:
{ocr_text}

Извлеки данные в JSON формате:
{{
  "surname": "фамилия",
  "given_names": "имя",
  "passport_number": "номер паспорта",
  "nationality": "гражданство",
  "date_of_birth": "YYYY-MM-DD",
  "sex": "M/F",
  "date_of_issue": "YYYY-MM-DD",
  "date_of_expiry": "YYYY-MM-DD"
}}

Верни ТОЛЬКО JSON, без markdown."""

    try:
        client = httpx.Client(timeout=60)

        response = client.post(
            f"{BASE_URL}/models/{MODEL}:generateContent",
            params={"key": API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
            },
        )

        response.raise_for_status()
        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

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

        print("✅ Gemini извлёк данные:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        return True

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP ошибка: {e.response.status_code}")
        print(e.response.text)
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_gemini_vision():
    """Тест Vision API (изображение напрямую)"""
    import base64

    if not API_KEY:
        print("❌ API ключ не задан!")
        return False

    image_path = "passport_test.jpg"

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """Ты эксперт по распознаванию паспортов.
Извлеки все данные в JSON формате:
{
  "surname": "фамилия",
  "given_names": "имя", 
  "passport_number": "номер",
  "nationality": "гражданство",
  "date_of_birth": "YYYY-MM-DD",
  "sex": "M/F",
  "date_of_issue": "YYYY-MM-DD",
  "date_of_expiry": "YYYY-MM-DD"
}

Верни ТОЛЬКО JSON."""

        client = httpx.Client(timeout=60)

        response = client.post(
            f"{BASE_URL}/models/{MODEL}:generateContent",
            params={"key": API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": image_b64,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000},
            },
        )

        response.raise_for_status()
        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

        # Очистка
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        parsed = json.loads(content)

        print("✅ Gemini Vision извлёк данные:")
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        return True

    except FileNotFoundError:
        print(f"❌ Файл {image_path} не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Тест 1: Gemini Text API")
    print("=" * 60)
    test_gemini_text()

    print("\n" + "=" * 60)
    print("🧪 Тест 2: Gemini Vision API (изображение)")
    print("=" * 60)
    test_gemini_vision()

    print("\n" + "=" * 60)
    print("📚 Получи API ключ: https://aistudio.google.com/apikey")
    print("💰 Бесплатно: 1000 запросов/день")
    print("=" * 60)
