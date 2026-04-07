"""
Test script for fixing SULATMANOV → SULAYMANOV and passport number extraction.
"""

import cv2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test image
IMAGE_PATH = "/home/mrnurali/LOW PROJECTS/ocr-service/test image pasport copy/Снимок экрана от 2026-04-01 22-08-07.png"

def test_parser_fixes():
    """Test the parser fixes for known issues."""
    
    # Load image
    image = cv2.imread(IMAGE_PATH)
    if image is None:
        logger.error(f"Failed to load image: {IMAGE_PATH}")
        return
    
    logger.info(f"Loaded image: {image.shape}")
    
    # Run OCR
    from app.services.ocr_service import ocr_pipeline
    
    logger.info("Running OCR pipeline...")
    ocr_result = ocr_pipeline.ocr_full(image)
    
    print("\n" + "="*60)
    print("OCR RESULT")
    print("="*60)
    print(f"Engine confidence: {ocr_result['confidence']:.2%}")
    print(f"\nRaw OCR text:\n{ocr_result['combined']}")
    print("="*60 + "\n")
    
    # Parse with smart parser
    from app.modules.parser_smart import extract_from_text
    
    logger.info("Parsing with smart parser...")
    parsed = extract_from_text(ocr_result['combined'])
    
    print("\n" + "="*60)
    print("PARSED DATA")
    print("="*60)
    
    # Expected values
    expected = {
        'first_name': 'NURALI',
        'last_name': 'SULAYMANOV',  # Not SULATMANOV
        'passport_number': 'AD1191583',  # Not AM79792
        'pinfl': '31509860230076',  # From QR code area
    }
    
    fields_to_check = [
        'first_name',
        'last_name',
        'middle_name',
        'birth_date',
        'gender',
        'passport_number',
        'passport_series',
        'pinfl',
    ]
    
    print("\nField validation:")
    for field in fields_to_check:
        value = parsed.get(field, '')
        confidence = parsed.get('_field_confidence', {}).get(field, None)
        conf_score = confidence.confidence if confidence else 0.0
        
        # Check against expected
        if field in expected:
            status = "✓" if value == expected[field] else "✗"
            expected_str = f" (expected: {expected[field]})"
        else:
            status = "•"
            expected_str = ""
        
        print(f"{status} {field:20s}: {value:30s} (conf: {conf_score:.2f}){expected_str}")
    
    print("\n" + "="*60)
    
    # Specific fixes check
    print("\nSPECIFIC FIXES CHECK:")
    print("-" * 60)
    
    # Fix 1: SULATMANOV → SULAYMANOV
    if parsed.get('last_name') == 'SULAYMANOV':
        print("✓ SULAYMANOV correction: PASSED")
    elif 'SULATMANOV' in parsed.get('last_name', ''):
        print("✗ SULATMANOV correction: FAILED (still has T instead of Y)")
    else:
        print(f"? SULAYMANOV correction: UNKNOWN (got: {parsed.get('last_name')})")
    
    # Fix 2: Passport number extraction
    passport_num = parsed.get('passport_number', '')
    if passport_num == 'AD1191583':
        print("✓ Passport number extraction: PASSED")
    elif passport_num:
        print(f"? Passport number extraction: PARTIAL (got: {passport_num}, expected: AD1191583)")
    else:
        print("✗ Passport number extraction: FAILED (not found)")
    
    print("="*60 + "\n")
    
    return parsed


if __name__ == '__main__':
    test_parser_fixes()
