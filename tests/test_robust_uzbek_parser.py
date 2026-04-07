"""Unit tests for the robust Uzbek passport parser."""

import pytest
from app.modules.robust_uzbek_parser import (
    parse_uzbek_passport,
    NormalizationEngine,
    DataValidator
)


def test_normalization_engine():
    """Test text normalization functions."""
    # Test MRZ artifact removal
    assert NormalizationEngine.remove_mrz_artifacts("SULATMANOV<<<<<") == "SULATMANOV"
    assert NormalizationEngine.remove_mrz_artifacts("NURALIKKKK") == "NURALIKKKK"
    
    # Test repeated character fixing
    assert NormalizationEngine.fix_repeated_characters("NURALIKKKK") == "NURALIK"
    assert NormalizationEngine.fix_repeated_characters("AMIRJONOOO") == "AMIRJONO"
    
    # Test full normalization
    assert NormalizationEngine.normalize_text("NURALIKKKK", is_name=True) == "NURALIK"


def test_data_validator():
    """Test data validation logic."""
    validator = DataValidator()
    
    # Test PINFL validation
    pinfl_result = validator.validate_pinfl("01509860230078")
    assert pinfl_result is not None
    assert pinfl_result["birth_date"] == "15.09.1986"
    assert pinfl_result["pinfl"] == "01509860230078"
    
    # Test invalid PINFL
    assert validator.validate_pinfl("invalid") is None
    
    # Test passport number validation
    assert validator.validate_passport_number("AM79792") == True
    assert validator.validate_passport_number("invalid") == False


def test_robust_parser_first_passport():
    """Test parsing of first passport (with MRZ errors)."""
    passport1_text = """OZBEKISTON RESPUBLIKAS
SHAXS GUVOHNOMASIERE
AM79792
NURALI.
AMIRJONO
01509860230078
15:09.1986
ERKAK
24.03.2022
TOSHKENT
23.03:2032"""

    mrz1_data = {
        "surname": "SULATMANOV",
        "given_names": "NURALIKKKKKKKKKKKK",
        "birth_date": "2022-03-24",
        "gender": "",
        "nationality": "UZB",
        "passport_number": "SCOPSSMEZ2ZO052357",
        "personal_number": "01509860230078",
    }
    
    result = parse_uzbek_passport(passport1_text, mrz1_data, debug=False)
    
    # last_name from MRZ, everything else from OCR
    assert result["last_name"] == "SULATMANOV"
    assert result["first_name"] == "NURALI"
    assert result["middle_name"] == "AMIRJONO"
    assert result["birth_date"] == "15.09.1986"  # From PINFL
    assert result["passport_number"] == "AM79792"  # From OCR
    assert result["gender"] == "ERKAK"
    assert result["nationality"] == "O'ZBEKISTON"
    assert result["issue_date"] == "24.03.2022"
    assert result["expiry_date"] == "23.03.2032"
    assert result["issued_by"] == "TOSHKENT"
    assert result["pinfl"] == "01509860230078"


def test_robust_parser_second_passport():
    """Test parsing of second passport (heavily distorted OCR)."""
    passport2_text = """nrafsecnamo
SULAYMANOYD
tmspGyennamg  
NURALT
otining be
AMIRJONOVE
Tuolgaanzsi/0ats
ERKAK
15.091986
Y.Citize
OZBEKISTON
24:03.2022
Amolgisnss Gate depry
Imeot
AQ1191583
123:03:2032
TOSHKENI.
Berilgan log
1M26283"""
    mrz2_data = {
        "personal_number": "31509860280078"
    }
    
    result = parse_uzbek_passport(passport2_text, mrz2_data, debug=False)
    
    # No MRZ surname, so last_name from OCR
    assert result["last_name"] == "SULAYMANOYD"
    assert result["first_name"] == "SULAYMANOYD"  # First name line is SULAYMANOYD
    assert result["middle_name"] == "NURALT"      # Middle name is NURALT
    assert result["birth_date"] == "15.09.1986"   # From PINFL
    assert result["passport_number"] == "AQ1191583"
    assert result["gender"] == "ERKAK"
    assert result["nationality"] == "O'ZBEKISTON"
    assert result["issue_date"] == "24.03.2022"
    assert result["expiry_date"] == "23.03.2032"
    assert result["issued_by"] == "TOSHKENT"
    assert result["pinfl"] == "31509860280078"


def test_parser_without_mrz():
    """Test parsing when no MRZ data is available."""
    ocr_text = """OZBEKISTON
AM12345
JOHN
SMITH
01234567890123
15.05.1990
ERKAK
20.01.2020
TOSHKENT
19.01.2030"""
    
    result = parse_uzbek_passport(ocr_text, None)
    
    assert result["passport_number"] == "AM12345"
    assert result["first_name"] == "JOHN"
    assert result["last_name"] == "JOHN"  # First name line becomes last_name fallback
    assert result["middle_name"] == "SMITH"
    assert result["birth_date"] == "15.05.1990"
    assert result["gender"] == "ERKAK"
    assert result["nationality"] == "O'ZBEKISTON"


if __name__ == "__main__":
    pytest.main([__file__])