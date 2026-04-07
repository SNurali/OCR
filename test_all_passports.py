#!/usr/bin/env python3
"""Batch test all passport images and output results for comparison."""

import cv2
import json
import os
import sys
import logging

# Suppress verbose logs
logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

from app.services.ocr_analyzer import analyze_passport_image

TEST_DIR = "test image pasport copy"


def test_image(filepath, filename):
    """Test a single passport image."""
    print(f"\n{'=' * 80}")
    print(f"FILE: {filename}")
    print(f"Path: {filepath}")
    print(f"{'=' * 80}")

    image = cv2.imread(filepath)
    if image is None:
        print(f"ERROR: Could not read image")
        return None

    try:
        analysis = analyze_passport_image(image)
        return analysis
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def main():
    test_dir = os.path.join(os.path.dirname(__file__), TEST_DIR)
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        sys.exit(1)

    # Include all image files
    files = sorted(
        [
            f
            for f in os.listdir(test_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"))
        ]
    )

    print(f"Found {len(files)} passport images to test")

    for i, filename in enumerate(files, 1):
        filepath = os.path.join(test_dir, filename)

        result = test_image(filepath, filename)
        if result is None:
            continue

        extracted = result.get("extracted", {})
        mrz = result.get("mrz_parsed", {})
        ocr_result = result.get("ocr_result", {})

        print(f"\n--- OCR CONFIDENCE ---")
        print(f"{ocr_result.get('confidence', 0):.3f}")

        print(f"\n--- RAW OCR TEXT ---")
        raw_text = ocr_result.get("combined", "")[:1000]  # Limit length
        print(raw_text)
        if len(ocr_result.get("combined", "")) > 1000:
            print("... (text truncated)")

        print(f"\n--- MRZ DATA ---")
        print(f"Valid: {mrz.get('valid', 'N/A')}")
        print(f"Type: {mrz.get('type', 'N/A')}")
        print(f"Issuing Country: {mrz.get('issuing_country', 'N/A')}")
        print(f"Surname: {mrz.get('surname', 'N/A')}")
        print(f"Given Names: {mrz.get('given_names', 'N/A')}")
        print(f"Birth Date: {mrz.get('birth_date', 'N/A')}")
        print(f"Gender: {mrz.get('gender', 'N/A')}")
        print(f"Nationality: {mrz.get('nationality', 'N/A')}")
        print(f"Passport Number: {mrz.get('passport_number', 'N/A')}")

        print(f"\n--- EXTRACTED DATA ---")
        print(f"Last Name: '{extracted.get('last_name', 'EMPTY')}'")
        print(f"First Name: '{extracted.get('first_name', 'EMPTY')}'")
        print(f"Middle Name: '{extracted.get('middle_name', 'EMPTY')}'")
        print(f"Birth Date: '{extracted.get('birth_date', 'EMPTY')}'")
        print(f"Gender: '{extracted.get('gender', 'EMPTY')}'")
        print(f"Nationality: '{extracted.get('nationality', 'EMPTY')}'")
        print(f"Passport Number: '{extracted.get('passport_number', 'EMPTY')}'")
        print(f"Issue Date: '{extracted.get('issue_date', 'EMPTY')}'")
        print(f"Expiry Date: '{extracted.get('expiry_date', 'EMPTY')}'")
        print(f"PINFL: '{extracted.get('pinfl', 'EMPTY')}'")
        print(f"Issued By: '{extracted.get('issued_by', 'EMPTY')}'")

        # Check for common issues
        issues = []
        if extracted.get("last_name") and "Y" in str(extracted.get("last_name")):
            issues.append("Possible Y→U OCR error in last_name")
        if extracted.get("first_name") and "Ы" in str(extracted.get("first_name")):
            issues.append("Possible Ы→И OCR error in first_name")
        if extracted.get("expiry_date", "").startswith("<<<<"):
            issues.append("Invalid expiry_date (<<<<<)")
        if not extracted.get("gender") and "AYOL" in raw_text.upper():
            issues.append("Gender 'AYOL' in text but not extracted")
        if not extracted.get("gender") and "ERKAK" in raw_text.upper():
            issues.append("Gender 'ERKAK' in text but not extracted")

        if issues:
            print(f"\n--- ISSUES DETECTED ---")
            for issue in issues:
                print(f"- {issue}")
        else:
            print(f"\n--- STATUS ---")
            print("No obvious issues detected")


if __name__ == "__main__":
    main()
