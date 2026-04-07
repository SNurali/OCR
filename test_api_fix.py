"""
Тест API после исправлений.
"""
import requests
import time

API_URL = "http://localhost:8001"
IMAGE_PATH = "test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

def test_ocr_api():
    # Upload file
    with open(IMAGE_PATH, "rb") as f:
        files = {"file": ("passport.png", f, "image/png")}
        response = requests.post(
            f"{API_URL}/api/passport/scan",
            files=files,
            headers={"Authorization": "Bearer test"}  # May need auth
        )
    
    if response.status_code == 401:
        print("⚠ Требуется авторизация. Пропускаю API тест.")
        return None
    
    if response.status_code != 200:
        print(f"✗ API Error: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    task_id = result.get("task_id")
    print(f"✓ Задача создана: {task_id}")
    
    # Wait and check result
    print("⏳ Ожидание результата...")
    time.sleep(5)
    
    # Get result
    result_resp = requests.get(
        f"{API_URL}/api/passport/result/{task_id}",
        headers={"Authorization": "Bearer test"}
    )
    
    if result_resp.status_code != 200:
        print(f"✗ Error getting result: {result_resp.status_code}")
        return False
    
    data = result_resp.json()
    extracted = data.get("extracted_data", {})
    
    print("\n=== Результаты OCR ===")
    fields = [
        ("first_name", "NURALI"),
        ("last_name", "SULAYMANOV"),
        ("passport_number", "AD1191583"),
        ("gender", "ERKAK"),
        ("pinfl", "31509860230078"),
    ]
    
    all_ok = True
    for field, expected in fields:
        value = extracted.get(field, "")
        status = "✓" if value == expected else "✗"
        if value != expected:
            all_ok = False
        print(f"{status} {field:20s}: '{value}' (ожидалось: '{expected}')")
    
    print(f"\nИтоговая оценка: {data.get('confidence', 0):.1%}")
    
    return all_ok

if __name__ == "__main__":
    print("Тестирование OCR API после исправлений...\n")
    success = test_ocr_api()
    if success is None:
        print("\n⚠ Требуется авторизация для API теста")
    else:
        print("\n" + ("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!" if success else "✗ ЕСТЬ ОШИБКИ"))
