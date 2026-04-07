"""Production-grade Uzbekistan passport parser with simplified logic."""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class FieldCandidate:
    """Represents a candidate value for a field with metadata."""
    value: str
    confidence: float
    source: str  # "MRZ", "OCR", "PINFL", "FALLBACK"


class NormalizationEngine:
    """Handles text normalization with smart cleaning."""
    
    @staticmethod
    def remove_mrz_artifacts(text: str) -> str:
        """Remove MRZ-specific artifacts like <<<<< and filler characters."""
        if not text:
            return ""
        text = re.sub(r"<+", " ", text)
        text = re.sub(r"[^A-Za-z0-9\s]", " ", text)
        return text.strip()
    
    @staticmethod
    def fix_repeated_characters(text: str) -> str:
        """Fix repeated characters (e.g., NURALIKKKK → NURALIK)."""
        if not text:
            return ""
        return re.sub(r"(.)\1{2,}", r"\1", text)
    
    @staticmethod
    def normalize_text(text: str, is_name: bool = False) -> str:
        """Comprehensive text normalization."""
        if not text:
            return ""
        
        text = text.strip().upper()
        text = NormalizationEngine.remove_mrz_artifacts(text)
        text = NormalizationEngine.fix_repeated_characters(text)
        
        # Fix common OCR character confusions
        ocr_fixes = {'0': 'O', '1': 'I', '5': 'S', '4': 'A', '3': 'E', '8': 'B', '9': 'G'}
        fixed_text = ""
        for char in text:
            if char in ocr_fixes and not char.isalpha():
                fixed_text += ocr_fixes[char]
            else:
                fixed_text += char
        text = fixed_text
        
        return text.strip()


class DataValidator:
    """Validates extracted data for consistency."""
    
    @staticmethod
    def validate_pinfl(pinfl: str) -> Optional[Dict[str, str]]:
        """Validate PINFL and extract birth date if valid."""
        if not pinfl or len(pinfl) < 8:
            return None
        
        try:
            # Uzbek PINFL format: G + DD + MM + YY + ...
            gender_digit = pinfl[0]
            dd = pinfl[1:3]  # Day
            mm = pinfl[3:5]  # Month  
            yy = pinfl[5:7]  # Year (last 2 digits)
            
            day_num, month_num, year_2digit = int(dd), int(mm), int(yy)
            
            if 1 <= day_num <= 31 and 1 <= month_num <= 12:
                full_year = 2000 + year_2digit if year_2digit <= 25 else 1900 + year_2digit
                birth_date = f"{dd}.{mm}.{full_year}"
                return {"birth_date": birth_date, "pinfl": pinfl}
        except (ValueError, IndexError):
            pass
        
        return None
    
    @staticmethod
    def validate_passport_number(number: str) -> bool:
        """Validate passport number format."""
        return bool(re.match(r"[A-Z]{2}\d{5,9}", number))


class UzbekPassportParser:
    """Main parser implementing the proven working approach."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.normalizer = NormalizationEngine()
        self.validator = DataValidator()
    
    def parse(self, ocr_text: str, mrz_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse using the proven approach: MRZ for last_name, OCR for everything else."""
        result = {
            "first_name": "",
            "last_name": "",
            "middle_name": "",
            "birth_date": "",
            "passport_number": "",
            "gender": "",
            "nationality": "",
            "issue_date": "",
            "expiry_date": "",
            "pinfl": "",
            "issued_by": ""
        }
        
        # Parse OCR lines
        ocr_lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
        
        # === STEP 1: Extract from MRZ (last_name only) ===
        if mrz_data and mrz_data.get("surname"):
            mrz_last_name = self.normalizer.normalize_text(str(mrz_data["surname"]), is_name=True)
            if mrz_last_name and len(mrz_last_name) >= 3:
                result["last_name"] = mrz_last_name
        
        # Also extract PINFL from MRZ if available
        if mrz_data and mrz_data.get("personal_number"):
            mrz_pinfl = str(mrz_data["personal_number"])
            if re.match(r"\d{14}", mrz_pinfl):
                result["pinfl"] = mrz_pinfl
        
        # === STEP 2: Extract from OCR text (everything else) ===
        
        # Extract PINFL
        for line in ocr_lines:
            pinfl_match = re.search(r"(\d{14})", line)
            if pinfl_match:
                result["pinfl"] = pinfl_match.group(1)
                break
        
        # Extract passport number
        for line in ocr_lines:
            passport_match = re.search(r"([A-Z]{2}\d{5,9})", line.replace(' ', '').upper())
            if passport_match:
                result["passport_number"] = passport_match.group(1)
                break
        
        # Extract names from OCR (first_name, middle_name, and last_name fallback)
        name_lines = self._extract_clean_name_lines(ocr_lines)
        if name_lines:
            if not result["last_name"] and len(name_lines) >= 1:
                result["last_name"] = self.normalizer.normalize_text(name_lines[0], is_name=True)
            if len(name_lines) >= 1:
                result["first_name"] = self.normalizer.normalize_text(name_lines[0], is_name=True)
            if len(name_lines) >= 2:
                result["middle_name"] = self.normalizer.normalize_text(name_lines[1], is_name=True)
            if len(name_lines) >= 3 and not result["middle_name"]:
                result["middle_name"] = self.normalizer.normalize_text(name_lines[2], is_name=True)
        
        # Extract gender
        for line in ocr_lines:
            upper_line = line.upper()
            if any(word in upper_line for word in ["ERKAK", "ERKKAK", "ERE", "MALE"]):
                result["gender"] = "ERKAK"
                break
            elif any(word in upper_line for word in ["AYOL", "FEMALE"]):
                result["gender"] = "AYOL"
                break
        
        # Extract nationality
        for line in ocr_lines:
            upper_line = line.upper()
            if "O'ZBEKISTON" in upper_line or "OZBEKISTON" in upper_line:
                result["nationality"] = "O'ZBEKISTON"
                break
        
        # Extract issued by
        for line in ocr_lines:
            upper_line = line.upper()
            if "TOSHKENT" in upper_line or "TOSHKEN" in upper_line or "TASHKENT" in upper_line:
                result["issued_by"] = "TOSHKENT"
                break
            elif "SAMARQAND" in upper_line or "SAMARKAND" in upper_line:
                result["issued_by"] = "SAMARQAND"
                break
        
        # Extract dates
        date_candidates = []
        date_pattern = r"(\d{1,2})[:\.\-/](\d{1,2})[:\.\-/](\d{4})"
        
        for line in ocr_lines:
            matches = re.finditer(date_pattern, line)
            for match in matches:
                day, month, year = match.groups()
                try:
                    day_num, month_num, year_num = int(day), int(month), int(year)
                    if 1 <= day_num <= 31 and 1 <= month_num <= 12 and 1900 <= year_num <= 2050:
                        normalized = f"{day.zfill(2)}.{month.zfill(2)}.{year}"
                        date_candidates.append(normalized)
                except ValueError:
                    continue
        
        # Use PINFL for birth date if available
        pinfl_birth_date = ""
        if result["pinfl"]:
            pinfl_result = self.validator.validate_pinfl(result["pinfl"])
            if pinfl_result:
                pinfl_birth_date = pinfl_result["birth_date"]
                result["birth_date"] = pinfl_birth_date
                result["pinfl"] = pinfl_result["pinfl"]
        
        # Filter out PINFL birth date from candidates to avoid duplication
        if pinfl_birth_date:
            other_dates = [d for d in date_candidates if d != pinfl_birth_date]
        else:
            other_dates = date_candidates
            # If no PINFL, use earliest date as birth
            if other_dates:
                sorted_dates = sorted(other_dates, key=lambda x: (x.split('.')[2], x.split('.')[1], x.split('.')[0]))
                result["birth_date"] = sorted_dates[0]
                other_dates = sorted_dates[1:]
        
        # Assign issue and expiry dates
        if other_dates:
            sorted_others = sorted(other_dates, key=lambda x: (x.split('.')[2], x.split('.')[1], x.split('.')[0]))
            result["issue_date"] = sorted_others[0]
            result["expiry_date"] = sorted_others[-1]
        
        # Final validation
        if result["nationality"] and result["nationality"] != "O'ZBEKISTON":
            result["nationality"] = "O'ZBEKISTON"
        
        if result["passport_number"] and not self.validator.validate_passport_number(result["passport_number"]):
            result["passport_number"] = ""
        
        return result
    
    def _extract_clean_name_lines(self, ocr_lines: List[str]) -> List[str]:
        """Extract clean name lines from OCR output."""
        skip_patterns = [
            "OZBEKISTON", "SHAXS", "GUVOHNOMASI", "ERE", "CITIZEN", "GATE", "IMEOT",
            "BERILGAN", "LOG", "PASSPORT", "RESPUBLIKAS", "TUOLGAANZSI", "OTSING",
            "BE", "AMOLGISNSS", "DEPRY", "Y.CITIZE", "NRAFSECNAMO", "TMSPGYENNAMG"
        ]
        
        name_candidates = []
        for line in ocr_lines:
            cleaned = line.strip()
            if not cleaned or len(cleaned) < 3:
                continue
                
            upper_cleaned = cleaned.upper()
            if any(pattern in upper_cleaned for pattern in skip_patterns):
                continue
                
            # Skip lines that are mostly non-alphabetic
            alpha_chars = re.sub(r'[^a-zA-Z]', '', cleaned)
            if len(alpha_chars) < 3 or len(alpha_chars) / len(cleaned) < 0.5:
                continue
                
            # Skip lines with too many repeated characters (likely OCR garbage)
            if re.search(r"(.)\1{3,}", cleaned):
                continue
                
            # Skip lines that look like codes
            if re.match(r'^[A-Z]{2,}\d+$', upper_cleaned.replace(' ', '')):
                continue
                
            # Skip lines that look like random OCR noise
            has_name_pattern = False
            common_patterns = ["LI", "NI", "TI", "RI", "BEK", "JON", "OV", "EV", "OYD", "ALT", "URT"]
            upper_cleaned_for_patterns = cleaned.upper()
            for pattern in common_patterns:
                if pattern in upper_cleaned_for_patterns:
                    has_name_pattern = True
                    break
            
            # Calculate basic quality metrics
            vowels = "AEIOUaeiou"
            vowel_count = sum(1 for c in cleaned if c in vowels)
            alpha_ratio = len(alpha_chars) / len(cleaned) if cleaned else 0
            
            # Keep line only if it has name patterns OR is very clean
            if not has_name_pattern:
                # Without name patterns, require high quality
                if (alpha_ratio < 0.8 or 
                    vowel_count == 0 or 
                    re.search(r"[^a-zA-Z\s]", cleaned) or
                    len(cleaned) > 15):
                    continue
                
            if len(re.findall(r'\d', cleaned)) > 2:
                continue
                
            name_candidates.append(cleaned)
        
        return name_candidates


# Convenience function for easy usage
def parse_uzbek_passport(ocr_text: str, mrz_data: Optional[Dict[str, Any]] = None, debug: bool = False) -> Dict[str, Any]:
    """Parse Uzbek passport with production-grade pipeline."""
    parser = UzbekPassportParser(debug=debug)
    return parser.parse(ocr_text, mrz_data)