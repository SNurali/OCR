import cv2
import numpy as np
from app.services.paddleocr_service import paddleocr_service

img = cv2.imread("debug_input_image.jpg")
if img is not None:
    max_c = np.max(img, axis=2)
    bgr_max = cv2.cvtColor(max_c, cv2.COLOR_GRAY2BGR)
    
    text, conf = paddleocr_service.recognize_with_confidence(bgr_max, langs=["en"])
    print("MAX TRICK TEXT:")
    print(text)
    print("-----")
    
    # Original test
    text_orig, _ = paddleocr_service.recognize_with_confidence(img, langs=["en"])
    print("ORIGINAL TEXT:")
    print(text_orig)
