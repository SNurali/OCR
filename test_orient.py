import cv2
import sys
import logging
from app.services.face_extractor import extractor
from app.services.preprocessing import preprocess_image

logging.basicConfig(level=logging.INFO)

image = cv2.imread("photo_2026-04-04_14-55-19.jpg")
print("Original shape:", image.shape)

deskewed = extractor.deskew_document(image)
print("Deskewed shape:", deskewed.shape)
cv2.imwrite("test_deskewed.jpg", deskewed)

preprocessed = preprocess_image(deskewed)
print("Preprocessed shape:", preprocessed["full"].shape)

text_roi = extractor.get_document_roi(preprocessed["full"])
print("Text ROI shape:", text_roi.shape)
cv2.imwrite("test_text_roi.jpg", text_roi)
