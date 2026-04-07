#!/usr/bin/env python3
"""Test script for the fixed parser with the problematic OCR text."""

from app.modules.parser_fixed import extract_from_text_fixed

# Raw OCR text from the screenshot
RAW_OCR_TEXT = """OZBEKISTON RESPUBLIKAS
SHAXS GUVOHNOMASIERE
AM79792
NURALI.
AMIRJONO
01509860230078
15:09.1986
ERKAK
24.03.2022
TOSHKENT
23.03:2032
126283
U07040119158373509860230078<
0009155M3203237
SULAREANOVANURALLIKSRSSSE"""

# MRZ data (simulated from the screenshot)
MRZ_DATA = {
    "valid": False,
    "all_checks_valid": False,
    "surname": "SULATMANOV",
    "given_names": "NURALIKKKKKKKKKKKK",
    "birth_date": "2022-03-24",
    "gender": "",
    "nationality": "UZB",
    "passport_number": "SCOPSSMEZ2ZO052357",
    "personal_number": "01509860230078",
}


def test_fixed_parser():
    print("Testing fixed parser with problematic OCR text...")
    print("=" * 60)

    result = extract_from_text_fixed(RAW_OCR_TEXT, MRZ_DATA)

    print("Parsed Results:")
    for key, value in result.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value}")

    print("\nExpected vs Actual:")
    expected = {
        "first_name": "NURALI",
        "last_name": "SULATMANOV",
        "middle_name": "AMIRJONOVICH",
        "birth_date": "24.03.2022",
        "gender": "ERKAK",
        "nationality": "O'ZBEKISTON",
        "passport_number": "AM79792",
        "issue_date": "23.03.2022",
        "expiry_date": "23.03.2032",
        "issued_by": "TOSHKENT",
        "pinfl": "01509860230078",
    }

    all_correct = True
    for key, expected_value in expected.items():
        actual_value = result.get(key, "")
        if actual_value == expected_value:
            print(f"✅ {key}: {actual_value}")
        else:
            print(f"❌ {key}: expected '{expected_value}', got '{actual_value}'")
            all_correct = False

    print(f"\nOverall: {'✅ ALL CORRECT' if all_correct else '❌ NEEDS MORE WORK'}")


if __name__ == "__main__":
    test_fixed_parser()
