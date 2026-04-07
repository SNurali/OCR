import requests
import time
import json
import os

API_URL = "http://localhost:8002/api/v2/ocr/recognize"
TEST_IMAGE_PATH = "passport_test_valid.jpg"

def test_recognize(image_path, model="auto", lang="uz"):
    """Тестирует endpoint распознавания"""
    if not os.path.exists(image_path):
        print(f"Ошибка: Файл {image_path} не найден.")
        return

    print(f"--- Тестирование {image_path} с моделью {model} ---")
    start_time = time.time()
    
    with open(image_path, 'rb') as f:
        files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
        data = {'model': model, 'lang': lang, 'output_format': 'json'}
        
        response = requests.post(API_URL, files=files, data=data)
        
    duration = time.time() - start_time
    print(f"Статус: {response.status_code}")
    print(f"Время запроса: {duration:.3f} сек (HTTP)")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Модель: {result.get('model')}")
        print(f"Задержка (backend): {result.get('latency_sec')} сек")
        print("Извлеченные поля:")
        print(json.dumps(result.get('extracted_fields'), indent=2, ensure_ascii=False))
        
        # Проверка МРЗ
        if result.get('extracted_fields', {}).get('mrz_found'):
            print("✅ MRZ зона успешно найдена.")
        else:
            print("⚠️ MRZ зона не обнаружена.")
    else:
        print(f"Ошибка: {response.text}")

if __name__ == "__main__":
    # 1. Автоматический режим (выберет HunyuanOCR)
    test_recognize(TEST_IMAGE_PATH, model="auto")
    
    print("\n" + "="*40 + "\n")
    
    # 2. Режим olmOCR-2 (для сложного распознавания структуры)
    test_recognize(TEST_IMAGE_PATH, model="olmocr")
