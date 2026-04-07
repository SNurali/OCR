"""Быстрый тест Qwen API без авторизации."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from pathlib import Path
from app.services.ocr_analyzer import analyze_passport_image

img_path = Path("test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png")
print(f"📷 {img_path.name} ({img_path.stat().st_size / 1024:.0f} KB)")
print("🔄 Отправляю в Qwen API...")

with open(img_path, "rb") as f:
    result = analyze_passport_image(f.read())

ex = result["extracted"]
v = result["validation"]

print("\n📋 РЕЗУЛЬТАТ:")
fields = {
    "last_name": "Фамилия", "first_name": "Имя", "middle_name": "Отчество",
    "birth_date": "Дата рождения", "gender": "Пол", "nationality": "Гражданство",
    "passport_number": "Паспорт", "issue_date": "Дата выдачи",
    "expiry_date": "Срок действия", "issued_by": "Кем выдан", "pinfl": "ПИНФЛ",
}
for k, label in fields.items():
    val = ex.get(k, "")
    print(f"  {'✅' if val else '❌'} {label:18s} → {val or '(пусто)'}")

print(f"\n📊 Confidence: {v.get('overall_confidence', 0):.0%}")
print(f"📊 All valid: {v.get('all_valid', False)}")
