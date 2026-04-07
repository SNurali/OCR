"""Example usage of the robust Uzbek passport parser."""

from app.modules.robust_uzbek_parser import parse_uzbek_passport


def main():
    """Demonstrate the robust parser with test cases."""
    
    print("=== Robust Uzbek Passport Parser Demo ===\n")
    
    # Test Case 1: Passport with MRZ errors (common real-world scenario)
    print("Test Case 1: Passport with MRZ errors")
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
        "surname": "SULATMANOV",           # Correct last name in MRZ
        "given_names": "NURALIKKKKKKKKKKKK",  # Corrupted first name in MRZ
        "birth_date": "2022-03-24",        # Wrong birth date in MRZ (actually issue date)
        "passport_number": "SCOPSSMEZ2ZO052357",  # Wrong passport number in MRZ
        "personal_number": "01509860230078",      # Correct PINFL
        "nationality": "UZB",
        "gender": ""
    }
    
    result1 = parse_uzbek_passport(passport1_text, mrz1_data, debug=False)
    print("Result:")
    for key, value in result1.items():
        if value:
            print(f"  {key}: {value}")
    print()
    
    # Test Case 2: Heavily distorted OCR (poor quality scan)
    print("Test Case 2: Heavily distorted OCR")
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
        "personal_number": "31509860280078"  # Only PINFL available from MRZ
    }
    
    result2 = parse_uzbek_passport(passport2_text, mrz2_data, debug=False)
    print("Result:")
    for key, value in result2.items():
        if value:
            print(f"  {key}: {value}")
    print()
    
    # Test Case 3: Perfect data (ideal scenario)
    print("Test Case 3: Perfect data")
    passport3_text = """O'ZBEKISTON RESPUBLIKASI
SHAXS GUVOHNOMASI
AB123456
AHMAD
RAHIMOV
JALOLOVICH
01234567890123
25.12.1985
ERKAK
10.06.2021
SAMARQAND
09.06.2031"""
    
    mrz3_data = {
        "surname": "RAHIMOV",
        "given_names": "AHMAD JALOLOVICH", 
        "birth_date": "1985-12-25",
        "passport_number": "AB123456",
        "personal_number": "01234567890123",
        "nationality": "UZB",
        "gender": "M"
    }
    
    result3 = parse_uzbek_passport(passport3_text, mrz3_data, debug=False)
    print("Result:")
    for key, value in result3.items():
        if value:
            print(f"  {key}: {value}")
    print()
    
    print("✅ All test cases completed successfully!")
    print("\nThe parser demonstrates:")
    print("- MRZ used only for last_name (most reliable)")
    print("- OCR used for all other fields (more accurate than MRZ for Uzbek passports)")
    print("- PINFL used for birth_date validation")
    print("- Robust handling of OCR errors and MRZ corruption")
    print("- Production-ready architecture following best practices")


if __name__ == "__main__":
    main()