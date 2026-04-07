#!/usr/bin/env python3
"""
Тест интеграции с Alibaba Qwen API
"""

import json
import httpx

API_KEY = "sk-sp-aadd4a10ec6544e3950eed157d9fda29"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-turbo"


def test_qwen_api():
    """Простой тест API"""
    client = httpx.Client(
        base_url=BASE_URL,
        timeout=60,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

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
        print("✅ Успешный ответ от Qwen API:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
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
    client = httpx.Client(
        base_url=BASE_URL,
        timeout=60,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

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
    print("=" * 50)
    print("Тест 1: Базовый запрос к Qwen API")
    print("=" * 50)
    test_qwen_api()

    print("\n" + "=" * 50)
    print("Тест 2: Извлечение данных паспорта")
    print("=" * 50)
    test_passport_extraction()
