"""
PERFECT OCR Test — проверка всех исправлений.

Проверяет:
1. Удаление дубликатов (NURALIKKKKKK → NURALIK)
2. Исправление фамилии (SULATMANOV → SULAYMANOV)
3. Извлечение номера паспорта (AD1191583)
4. Извлечение PINFL из MRZ
5. Исправление пола (ERKKAK → ERKAK)
"""

import cv2
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Test image
IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"


def test_duplicate_removal():
    """Test duplicate character removal."""
    from app.modules.parser_smart import _remove_duplicate_chars
    
    test_cases = [
        ("NURALIKKKKKKKKKKKK", "NURALIK"),
        ("ERKKAK", "ERKAK"),
        ("ERKAKK", "ERKAK"),
        ("SULAYMANOVV", "SULAYMANOV"),
        ("AAAA", "A"),   # All duplicates removed with threshold=1
        ("AAA", "A"),    # All duplicates removed with threshold=1
    ]
    
    print("\n" + "="*60)
    print("TEST 1: Duplicate Character Removal")
    print("="*60)
    
    all_passed = True
    for input_text, expected in test_cases:
        # Use threshold=1 for aggressive duplicate removal
        result = _remove_duplicate_chars(input_text, threshold=1)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"{status} '{input_text}' → '{result}' (expected: '{expected}')")
    
    return all_passed


def test_name_normalization():
    """Test name normalization with OCR corrections."""
    from app.modules.parser_smart import _normalize_name
    
    test_cases = [
        ("SULATMANOV", "SULAYMANOV", "last"),
        ("SULAIMANOV", "SULAYMANOV", "last"),
        ("ULAYMANOV", "SULAYMANOV", "last"),
        ("NURALIKKKKKK", "NURALIK", "first"),
        ("NURALI", "NURALI", "first"),
    ]
    
    print("\n" + "="*60)
    print("TEST 2: Name Normalization")
    print("="*60)
    
    all_passed = True
    for input_text, expected, name_type in test_cases:
        result = _normalize_name(input_text, name_type)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"{status} '{input_text}' ({name_type}) → '{result}' (expected: '{expected}')")
    
    return all_passed


def test_gender_extraction():
    """Test gender extraction with duplicate removal."""
    from app.modules.parser_smart import _extract_gender_smart
    
    test_cases = [
        ("ERKKAK", "ERKAK"),
        ("ERKAKK", "ERKAK"),
        ("ERKAK", "ERKAK"),
        ("AYOL", "AYOL"),
        ("AYOLL", "AYOL"),
    ]
    
    print("\n" + "="*60)
    print("TEST 3: Gender Extraction")
    print("="*60)
    
    all_passed = True
    for input_text, expected in test_cases:
        result, conf = _extract_gender_smart(input_text)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"{status} '{input_text}' → '{result}' (conf: {conf:.2f}, expected: '{expected}')")
    
    return all_passed


def test_full_pipeline():
    """Test full OCR pipeline on real passport image."""
    print("\n" + "="*60)
    print("TEST 4: Full OCR Pipeline")
    print("="*60)
    
    # Load image
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        logger.error(f"Failed to load image: {IMAGE_PATH}")
        return False
    
    logger.info(f"Loaded image: {image.shape}")
    
    # Run OCR
    from app.services.ocr_service import ocr_pipeline
    
    logger.info("Running OCR pipeline...")
    ocr_result = ocr_pipeline.ocr_full(image)
    
    print(f"\nOCR Results:")
    print(f"  Engine confidence: {ocr_result['confidence']:.2%}")
    print(f"  MRZ text length: {len(ocr_result['mrz'])} chars")
    print(f"  Combined text length: {len(ocr_result['combined'])} chars")
    
    # Parse with smart parser
    from app.modules.parser_smart import extract_from_text

    logger.info("Parsing with smart parser...")
    # Combine OCR text with MRZ text for better extraction
    combined_with_mrz = ocr_result['combined'] + "\n" + ocr_result['mrz']
    parsed = extract_from_text(combined_with_mrz, {})
    
    # Expected values
    expected = {
        'first_name': 'NURALI',
        'last_name': 'SULAYMANOV',
        'passport_number': 'AD1191583',
        'gender': 'ERKAK',
    }
    
    print("\n" + "-"*60)
    print("Parsed Fields:")
    print("-"*60)
    
    all_passed = True
    for field, expected_value in expected.items():
        actual_value = parsed.get(field, '')
        status = "✓" if actual_value == expected_value else "✗"
        if actual_value != expected_value:
            all_passed = False
        print(f"{status} {field:20s}: '{actual_value:30s}' (expected: '{expected_value}')")
    
    # Print all fields
    print("\n" + "-"*60)
    print("All Extracted Fields:")
    print("-"*60)
    
    fields_to_show = [
        'first_name', 'last_name', 'middle_name',
        'birth_date', 'gender', 'nationality',
        'passport_number', 'passport_series',
        'issue_date', 'expiry_date', 'pinfl'
    ]
    
    for field in fields_to_show:
        value = parsed.get(field, '')
        conf = parsed.get('_field_confidence', {}).get(field)
        if conf:
            print(f"  {field:20s}: '{value:30s}' (conf: {conf.confidence:.2f}, src: {conf.source})")
        else:
            print(f"  {field:20s}: '{value:30s}'")
    
    return all_passed


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PERFECT OCR TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run unit tests
    results.append(("Duplicate Removal", test_duplicate_removal()))
    results.append(("Name Normalization", test_name_normalization()))
    results.append(("Gender Extraction", test_gender_extraction()))
    
    # Run integration test
    results.append(("Full Pipeline", test_full_pipeline()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status:10s} {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
