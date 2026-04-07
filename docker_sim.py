import cv2
import json
import logging
from unittest.mock import patch
logging.basicConfig(level=logging.INFO)

# Force face_extractor to act as if InsightFace isn't loaded
with patch('app.services.face_extractor.FaceExtractor._get_best_face', return_value=None):
    from app.services.face_extractor import extractor
    extractor.model_loaded = False
    extractor.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    
    from app.services.ocr_analyzer import analyze_passport_image
    
    image = cv2.imread("photo_2026-04-04_14-55-19.jpg")
    analysis = analyze_passport_image(image)
    
    print("==== OCR CONFIDENCE ====")
    print(analysis["ocr_result"].get("confidence", 0.0))
    print("==== RAW TEXT ====")
    print(analysis["ocr_result"]["combined"][:100])
