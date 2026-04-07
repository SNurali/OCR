#!/usr/bin/env python3
"""Скрипт для прогона всех тестовых изображений через VLM OCR API."""
import os
import sys
import json
import time
import requests

UPLOAD_DIR = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy"
API_URL = "http://localhost:8005/api/passport/test-ocr"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIiwidHlwZSI6ImRhc2hib2FyZCIsImV4cCI6MTc3NTUxNzMwN30.l8s6suhd9kWI7NSMAi2K6kNRTr1ffap1YzxgEDf5N3s"

FILES = [
    "1362837818.jpg",
    "1543260236_85061df6-a325-4c35-b837-5a8d4345c478.jpeg",
    "168742_900.jpg",
    "4.jpg",
    "468985_original.jpg",
    "IMG-20161019-WA0029-1.jpeg",
    "n_5281_94106313.jpg",
    "photo_2026-04-04_14-55-19.jpg",
    "stateborderrr2.jpg",
    "Uzbekistan_Pasport_(old).jpg",
    "Снимок экрана от 2026-04-01 22-08-07.png",
    "Снимок экрана от 2026-04-02 10-29-26.png",
    "2a1706cf8d5e231484caa9f93as6.jpg",
]

EXPECTED = {
    "1362837818.jpg": {"last_name": "SHIN", "first_name": "MARINA", "birth_date": "22.10.1979", "gender": "F", "passport_number": "AA6555552"},
    "1543260236_85061df6-a325-4c35-b837-5a8d4345c478.jpeg": {"last_name": "RAMETULLAEV", "first_name": "ERNAZAR", "birth_date": "13.07.1993", "gender": "M", "passport_number": "KA1120011"},
    "168742_900.jpg": {"last_name": "DANIKAHN0V", "first_name": "ERZHAN", "birth_date": "14.11.1986", "gender": "M", "passport_number": "N08382095"},
    "4.jpg": {"last_name": "ASANOV", "first_name": "USON", "birth_date": "01.01.1991", "gender": "M", "passport_number": "AN1234567"},
    "468985_original.jpg": {"last_name": "POLTAVSKII", "first_name": "ALEKSANDR", "birth_date": "25.05.1970", "gender": "M", "passport_number": "752007752"},
    "IMG-20161019-WA0029-1.jpeg": {"last_name": "PRIGOZHIN", "first_name": "EFIM", "birth_date": "22.04.1989", "gender": "M", "passport_number": "4510200787"},
    "n_5281_94106313.jpg": {"last_name": "MAMADJANOV", "first_name": "DILSHOD", "birth_date": "24.05.1988", "gender": "M", "passport_number": "AA2085855"},
    "photo_2026-04-04_14-55-19.jpg": {"last_name": "SULAYMANOVA", "first_name": "UMIDA", "birth_date": "24.02.1999", "gender": "F", "passport_number": "AD00045668"},
    "stateborderrr2.jpg": {"last_name": "RADJABOV", "first_name": "MUZAFFAR", "birth_date": "07.03.1989", "gender": "M", "passport_number": "AA3260443"},
    "Uzbekistan_Pasport_(old).jpg": {"last_name": "AKHMEDOV", "first_name": "SHUKHRAT", "birth_date": "16.06.1984", "gender": "M", "passport_number": "CA1580788"},
    "Снимок экрана от 2026-04-01 22-08-07.png": {"last_name": "SULAYMANOV", "first_name": "NURALI", "birth_date": "15.09.1986", "gender": "M", "pinfl": "31509860230078"},
    "Снимок экрана от 2026-04-02 10-29-26.png": {"last_name": "SULAYMANOV", "first_name": "NURALI", "birth_date": "15.09.1986", "gender": "M", "pinfl": "31509860230078"},
    "2a1706cf8d5e231484caa9f93as6.jpg": {"last_name": "KNYAZ", "first_name": "ELENA", "birth_date": "14.08.2000", "gender": "F", "passport_number": "3618951557"},
}


def test_file(filename, idx, total):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        print(f"  ⚠️  Файл не найден: {filepath}")
        return None

    exp = EXPECTED.get(filename, {})

    print(f"\n{'='*70}")
    print(f"  [{idx}/{total}] {filename}")
    print(f"  Ожидаю: {exp}")
    print(f"{'='*70}")

    try:
        with open(filepath, "rb") as f:
            files = {"file": (filename, f, "image/jpeg")}
            headers = {"Authorization": f"Bearer {TOKEN}"}
            start = time.time()
            resp = requests.post(API_URL, files=files, headers=headers, timeout=120)
            elapsed = time.time() - start

        if resp.status_code != 200:
            print(f"  ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        extracted = data.get("extracted_fields", {})
        validation = data.get("validation", {})

        print(f"  ⏱️  Время: {elapsed:.1f}с")
        print(f"  📊 Confidence: {validation.get('overall_confidence', 0):.2f}")
        print(f"  ✅ All valid: {validation.get('all_valid', False)}")
        print()

        # Печатаем извлечённые поля
        fields = [
            "last_name", "first_name", "middle_name", "birth_date",
            "gender", "nationality", "passport_number",
            "issue_date", "expiry_date", "pinfl"
        ]
        for f_name in fields:
            actual = extracted.get(f_name, "")
            expected_val = exp.get(f_name, "")
            if expected_val:
                match = "✅" if expected_val.upper() in actual.upper() else "❌"
                print(f"  {match} {f_name:20s}: {actual:30s} (ожидал: {expected_val})")
            else:
                print(f"     {f_name:20s}: {actual}")

        return extracted

    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return None


def main():
    print("=" * 70)
    print("  VLM OCR — ПРОГОН ТЕСТОВЫХ ИЗОБРАЖЕНИЙ")
    print(f"  API: {API_URL}")
    print(f"  Файлов: {len(FILES)}")
    print("=" * 70)

    results = []
    for i, filename in enumerate(FILES, 1):
        result = test_file(filename, i, len(FILES))
        results.append((filename, result))

    # Итоговая таблица
    print("\n\n" + "=" * 70)
    print("  ИТОГОВАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print("=" * 70)
    print(f"  {'Файл':45s} {'Фамилия':15s} {'Имя':12s} {'Дата рожд.':12s} {'Пол':4s} {'PINFL':16s}")
    print("-" * 70)

    for filename, extracted in results:
        if extracted:
            ln = extracted.get("last_name", "?")[:14]
            fn = extracted.get("first_name", "?")[:11]
            bd = extracted.get("birth_date", "?")
            g = extracted.get("gender", "?")
            p = extracted.get("pinfl", "")[:15] or "-"
        else:
            ln = fn = bd = "?"
            g = "-"
            p = "-"
        print(f"  {filename:45s} {ln:15s} {fn:12s} {bd:12s} {g:4s} {p}")

    print("-" * 70)
    success = sum(1 for _, r in results if r)
    print(f"\n  Обработано: {success}/{len(FILES)} успешно")


if __name__ == "__main__":
    main()
