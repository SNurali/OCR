import cv2
import sys

image = cv2.imread("photo_2026-04-04_14-55-19.jpg")
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

rotations = [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]
for rot in rotations:
    current_img = cv2.rotate(image, rot) if rot is not None else image
    gray = cv2.cvtColor(current_img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    print(f"Rot {rot}: {len(faces)} faces")
