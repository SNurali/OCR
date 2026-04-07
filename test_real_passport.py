#!/usr/bin/env python3
"""
Тест OCR с VLM Nemotron на реальном изображении паспорта
"""

import httpx
import json
import base64
from pathlib import Path

IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

def test_vlm_direct():
    """Тестируем VLM экстрактор напрямую"""
    print("📋 Загрузка изображения...")
    image_bytes = Path(IMAGE_PATH).read_bytes()
    print(f"   Размер: {len(image_bytes) / 1024:.1f} KB")
    
    # Импортируем экстрактор
    import sys
    sys.path.insert(0, "/home/mrnurali/LOW PROJECTS/ocr-service")
    from app.services.vlm_extractor import vlm_extractor
    
    print(f"\n🤖 Провайдер: {vlm_extractor.provider}")
    print(f"   Модель: {vlm_extractor.model}")
    print(f"   Base URL: {vlm_extractor.base_url}\n")
    
    print("⏳ Извлечение данных через VLM...")
    result = vlm_extractor.extract(image_bytes)
    
    print("\n✅ Результат:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    filled = sum(1 for v in result.values() if v)
    print(f"\n📊 Заполнено полей: {filled}/{len(result)}")
    
    return result

def test_api_upload():
    """Тестируем через API эндпоинт"""
    print("\n" + "="*60)
    print("Тест через API (порт 8001)")
    print("="*60)
    
    image_bytes = Path(IMAGE_PATH).read_bytes()
    
    try:
        response = httpx.post(
            "http://localhost:8001/api/v1/ocr/process",
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            timeout=120
        )
        
        print(f"Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
        else:
            print(response.text)
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
        print("   Убедись, что сервис запущен: docker-compose up -d")

if __name__ == "__main__":
    print("="*60)
    print("Тест OCR с Nemotron на изображении паспорта")
    print("="*60 + "\n")
    
    # Тест VLM напрямую
    test_vlm_direct()
    
    # Тест через API
    test_api_upload()
