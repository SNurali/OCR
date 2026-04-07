"""
Test script for Uzbek passport OCR with PaddleOCR-VL.

Usage:
    python test_paddle_ocr.py <path_to_passport_image>

Example:
    python test_paddle_ocr.py passport_test.jpg
"""

import sys
import cv2
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_paddle_ocr(image_path: str):
    """Test PaddleOCR-VL on passport image."""
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return None
    
    logger.info(f"Loaded image: {image.shape}")
    
    # Initialize OCR engine
    from app.modules.ocr import OCREngine
    ocr_engine = OCREngine()
    
    # Run OCR
    logger.info("Running PaddleOCR-VL...")
    ocr_result = ocr_engine.ocr_full(image)
    
    print("\n" + "="*60)
    print("OCR RESULT")
    print("="*60)
    print(f"Engine: {ocr_result['engine']}")
    print(f"Confidence: {ocr_result['confidence']:.2%}")
    print(f"\nRaw text:\n{ocr_result['text']}")
    print("="*60 + "\n")
    
    # Parse result
    from app.modules.parser_smart import extract_from_text
    
    parsed = extract_from_text(ocr_result['text'])
    
    print("\n" + "="*60)
    print("PARSED DATA")
    print("="*60)
    
    fields = [
        'first_name',
        'last_name',
        'middle_name',
        'birth_date',
        'gender',
        'nationality',
        'passport_number',
        'passport_series',
        'issue_date',
        'expiry_date',
        'issued_by',
        'pinfl'
    ]
    
    for field in fields:
        value = parsed.get(field, '')
        confidence = parsed.get('_field_confidence', {}).get(field, None)
        conf_score = confidence.confidence if confidence else 0.0
        source = confidence.source if confidence else 'unknown'
        
        # Color code based on confidence
        if conf_score >= 0.8:
            status = "✓"
        elif conf_score >= 0.5:
            status = "⚠"
        else:
            status = "✗"
        
        print(f"{status} {field:20s}: {value:30s} (conf: {conf_score:.2%}, source: {source})")
    
    print(f"\nOverall confidence: {parsed.get('_overall_confidence', 0.0):.2%}")
    print(f"MRZ valid: {parsed.get('_mrz_valid', False)}")
    print("="*60 + "\n")
    
    # Save detailed result
    output_file = Path(image_path).stem + '_result.json'
    
    # Convert FieldConfidence to dict for JSON serialization
    parsed_serializable = {}
    for key, value in parsed.items():
        if key == '_field_confidence':
            parsed_serializable[key] = {
                k: {
                    'field_name': v.field_name,
                    'value': v.value,
                    'confidence': v.confidence,
                    'source': v.source,
                    'corrections': v.corrections
                }
                for k, v in value.items()
            }
        else:
            parsed_serializable[key] = value
    
    result = {
        'image': image_path,
        'ocr': ocr_result,
        'parsed': parsed_serializable
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Result saved to: {output_file}")
    
    return result


def test_preprocessing(image_path: str):
    """Test preprocessing pipeline."""
    from app.modules.preprocessing import preprocess_uzbek_passport
    
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return
    
    logger.info("Applying Uzbek passport preprocessing...")
    enhanced = preprocess_uzbek_passport(image)
    
    # Save enhanced image
    output_path = Path(image_path).stem + '_enhanced.jpg'
    cv2.imwrite(output_path, enhanced)
    
    logger.info(f"Enhanced image saved to: {output_path}")
    
    return output_path


def compare_ocr_engines(image_path: str):
    """Compare all OCR engines."""
    from app.modules.ocr import OCREngine
    
    image = cv2.imread(image_path)
    if image is None:
        logger.error(f"Failed to load image: {image_path}")
        return
    
    ocr_engine = OCREngine()
    
    print("\n" + "="*60)
    print("OCR ENGINE COMPARISON")
    print("="*60)
    
    # PaddleOCR
    logger.info("Testing PaddleOCR-VL...")
    paddle_text, paddle_conf, _ = ocr_engine.run_paddleocr(image)
    print(f"\nPaddleOCR-VL:")
    print(f"  Confidence: {paddle_conf:.2%}")
    print(f"  Text length: {len(paddle_text)} chars")
    
    # EasyOCR
    logger.info("Testing EasyOCR...")
    easy_text, easy_conf, _ = ocr_engine.run_easyocr(image)
    print(f"\nEasyOCR:")
    print(f"  Confidence: {easy_conf:.2%}")
    print(f"  Text length: {len(easy_text)} chars")
    
    # Tesseract
    logger.info("Testing Tesseract...")
    tess_text, tess_conf, _ = ocr_engine.run_tesseract(image)
    print(f"\nTesseract:")
    print(f"  Confidence: {tess_conf:.2%}")
    print(f"  Text length: {len(tess_text)} chars")
    
    print("\n" + "="*60)
    print("WINNER:")
    
    engines = [
        ('PaddleOCR-VL', paddle_text, paddle_conf),
        ('EasyOCR', easy_text, easy_conf),
        ('Tesseract', tess_text, tess_conf)
    ]
    
    winner = max(engines, key=lambda x: x[2] if x[1].strip() else 0)
    print(f"  {winner[0]} (confidence: {winner[2]:.2%})")
    print("="*60 + "\n")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not Path(image_path).exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)
    
    # Run tests
    print(f"\nTesting OCR on: {image_path}\n")
    
    # Test preprocessing
    enhanced_path = test_preprocessing(image_path)
    
    # Test PaddleOCR
    result = test_paddle_ocr(image_path)
    
    # Compare engines
    compare_ocr_engines(image_path)
    
    print("\n✅ All tests completed!\n")
