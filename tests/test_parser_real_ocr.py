"""Test parser with real OCR output from Uzbekistan ID card."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.parser import extract_from_text, normalize_name

RAW_OCR_TEXT = """OZBEKISTON RESPUBLIKASI
SHAXS GUVOHNOMASI
5
FSULAYMAMOV
KmURALI
AMIRJONOVIC
71Daln n
15,09.1996
ERKAK
Пlata neNi
24.03.2022
0 ZHEKISTON
{ala demplry
23,03.2032
4DII91583
AN79792
91509860230078
TOSHKEN
IIV 26283
IUUZBAD11 915 837315 0986 0230078 <
8 6 0 915 5 М3 203237XXXUZB <<<<<<<< 0
S U LAY MAN 0V< <NU RALI<<<<<<<<<<< <"""


def test_parser():
    result = extract_from_text(RAW_OCR_TEXT)

    print("=" * 60)
    print("PARSER RESULTS")
    print("=" * 60)

    expected = {
        "last_name": "SULAYMANOV",
        "first_name": "NURALI",
        "middle_name": "AMIRJONOVICH",
        "birth_date": "15.09.1996",
        "gender": "ERKAK",
        "nationality": "O'ZBEKISTON",
        "passport_number": "AN79792",
        "passport_series": "AN",
        "issue_date": "24.03.2022",
        "expiry_date": "23.03.2032",
        "issued_by": "TOSHKENT",
        "pinfl": "91509860230078",
    }

    passed = 0
    failed = 0
    for field, exp_val in expected.items():
        actual = result.get(field, "")
        status = "PASS" if actual == exp_val else "FAIL"
        if actual != exp_val:
            failed += 1
        else:
            passed += 1
        print(f"{status} {field:20s} expected={exp_val:25s} actual={actual}")

    print("=" * 60)
    print(f"Passed: {passed}/{len(expected)}")
    print(f"Failed: {failed}/{len(expected)}")

    print("\n" + "=" * 60)
    print("NORMALIZE_NAME TESTS")
    print("=" * 60)
    tests = [
        ("FSULAYMAMOV", "SULAYMAMOV"),
        ("KmURALI", "MURALI"),
        ("AMIRJONOVIC", "AMIRJONOVIC"),
    ]
    for inp, expected_norm in tests:
        result_norm = normalize_name(inp)
        status = "PASS" if result_norm == expected_norm else "FAIL"
        print(
            f"{status} normalize_name('{inp}') = '{result_norm}' (expected: '{expected_norm}')"
        )


if __name__ == "__main__":
    test_parser()
