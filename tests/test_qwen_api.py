"""Тест интеграции с Qwen Vision API."""
import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vlm_extractor import vlm_extractor
from app.services.ocr_analyzer import analyze_passport_image


def test_qwen_extractor():
    """Тестируем Qwen VLM экстрактор на тестовом изображении."""
    # Ищем тестовое изображение
    test_images = [
        "passport_test.jpg",
        "passport_test_valid.jpg",
        "passport_test_processed.jpg",
        "debug_input_image.jpg",
    ]

    image_path = None
    for img in test_images:
        if os.path.exists(img):
            image_path = img
            break

    if not image_path:
        # Попробуем найти любое jpg изображение
        for f in os.listdir("."):
            if f.endswith(".jpg") or f.endswith(".png"):
                image_path = f
                break

    if not image_path:
        print("❌ Не найдено тестовое изображение")
        return False

    print(f"📷 Тестируем на: {image_path}")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    print(f"📏 Размер изображения: {len(image_bytes) / 1024:.1f} KB")
    print("🔄 Отправляем в Qwen API...")

    # Тестируем экстрактор напрямую
    result = vlm_extractor.extract(image_bytes)

    print("\n📋 Результат экстракции:")
    print("-" * 40)
    filled = 0
    for key, value in result.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {value or '(пусто)'}")
        if value:
            filled += 1

    print("-" * 40)
    print(f"\n📊 Заполнено полей: {filled}/{len(result)}")

    if filled > 0:
        print("✅ Qwen Vision API работает!")
        return True
    else:
        print("❌ API вернул пустой результат")
        return False


def test_full_pipeline():
    """Тестируем полный pipeline с валидацией."""
    test_images = [f for f in os.listdir(".") if f.endswith(".jpg") or f.endswith(".png")]

    if not test_images:
        print("❌ Не найдено тестовое изображение")
        return False

    image_path = test_images[0]
    print(f"🔄 Полный pipeline на: {image_path}")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    analysis = analyze_passport_image(image_bytes)

    print("\n📋 Извлечённые поля:")
    for key, value in analysis["extracted"].items():
        status = "✅" if value else "  "
        print(f"  {status} {key}: {value or '(пусто)'}")

    print("\n🔍 Валидация:")
    checks = analysis["validation"].get("checks", {})
    for key, valid in checks.items():
        status = "✅" if valid else "❌"
        print(f"  {status} {key}")

    print(f"\n📊 Overall confidence: {analysis['validation'].get('overall_confidence', 0):.2f}")
    print(f"📊 All valid: {analysis['validation'].get('all_valid', False)}")

    return True


if __name__ == "__main__":
    print("=" * 50)
    print("🧪 Тест интеграции с Qwen Vision API")
    print("=" * 50)

    print("\n1️⃣ Тест экстрактора...")
    test_qwen_extractor()

    print("\n2️⃣ Тест полного pipeline...")
    test_full_pipeline()
