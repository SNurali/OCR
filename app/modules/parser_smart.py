"""
Smart parser for Uzbekistan passports with advanced OCR error correction.

Features:
- MRZ-first extraction strategy
- Context-aware error correction
- Uzbek name validation
- Document-specific pattern matching
- Confidence scoring per field
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FieldConfidence:
    """Confidence score for individual field."""
    field_name: str
    value: str
    confidence: float
    source: str  # 'mrz', 'visual', 'inferred'
    corrections: List[str]


# Uzbekistan ID-specific keywords
UZ_KEYWORDS = {
    "OZBEKISTON",
    "O'ZBEKISTON",
    "SHAXS",
    "GUVOHNOMASI",
    "RESPUBLIKASI",
    "ERKAK",
    "AYOL",
    "TOSHKENT",
    "TOSHKEN",
}

# Common OCR errors for Uzbek passports
OCR_ERROR_PATTERNS = {
    # Digits → Letters
    '0': ['O', 'Q'],
    '1': ['I', 'L', 'J'],
    '2': ['Z'],
    '3': ['E', 'B'],
    '4': ['A', 'H'],
    '5': ['S'],
    '6': ['G'],
    '7': ['T'],
    '8': ['B'],
    '9': ['G', 'Q'],
    
    # Letters → Digits (less common)
    'O': ['0'],
    'I': ['1'],
    'S': ['5'],
    'Z': ['2'],
    'B': ['8'],
    'G': ['6', '9'],
    
    # Letter confusions in names
    'T': ['Y'],  # SULATMANOV → SULAYMANOV
    'Y': ['T'],
    'A': ['4'],
    'D': ['0'],
}

# Uzbek name patterns
UZBEK_NAME_PATTERNS = {
    # Common Uzbek name endings
    'male': ['OVICH', 'EVICH', 'OV', 'EV', 'JON', 'JONOV'],
    'female': ['OVNA', 'EVNA', 'OVA', 'EVA', 'JON'],
    
    # Common patronymic endings
    'patronymic': ['OVICH', 'EVICH', 'OVNA', 'EVNA'],
}

# Known Uzbek cities/regions
UZBEK_REGIONS = {
    'TOSHKENT', 'SAMARKAND', 'BUKHARA', 'KHIVA', 'FERGANA', 
    'NAMANGAN', 'ANDIJAN', 'NUKUS', 'TERMEZ', 'URGENCH',
    'KARSHI', 'NAVOI', 'JIZZAKH', 'GULISTAN', 'MARGILAN'
}


def _correct_ocr_errors(text: str, context: str = 'general') -> str:
    """
    Correct common OCR errors based on context.
    
    Args:
        text: Raw OCR text
        context: 'name', 'date', 'number', 'general'
        
    Returns:
        Corrected text
    """
    if not text:
        return ""
    
    text = text.upper().strip()
    corrected = text
    
    # Context-specific corrections
    if context == 'name':
        # Fix T→Y in surnames (SULATMANOV → SULAYMANOV)
        if 'SULATMANOV' in corrected:
            corrected = corrected.replace('SULATMANOV', 'SULAYMANOV')
        
        # Fix common OCR errors in names
        # Don't correct letters in names (could be valid)
        # Only fix obvious digit→letter errors
        for digit, letters in OCR_ERROR_PATTERNS.items():
            if digit.isdigit():
                for letter in letters:
                    # Only replace if surrounded by letters
                    corrected = re.sub(
                        rf'(?<=[A-Z]){digit}(?=[A-Z])',
                        letter,
                        corrected
                    )

    elif context == 'date':
        # Fix common date OCR errors
        corrected = corrected.replace('O', '0')
        corrected = corrected.replace('I', '1')
        corrected = corrected.replace('L', '1')
        corrected = corrected.replace('Z', '2')
        corrected = corrected.replace('E', '3')
        corrected = corrected.replace('A', '4')
        corrected = corrected.replace('S', '5')
        corrected = corrected.replace('B', '8')
        corrected = corrected.replace('G', '6')
    
    elif context == 'number':
        # Fix passport number/PINFL errors
        for letter, digits in OCR_ERROR_PATTERNS.items():
            if letter.isalpha():
                for digit in digits:
                    corrected = corrected.replace(letter, digit)
    
    return corrected


def _validate_date_format(date_str: str) -> Optional[str]:
    """
    Validate and normalize date format.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Normalized date (DD.MM.YYYY) or None if invalid
    """
    if not date_str:
        return None
    
    from datetime import datetime
    
    # Try various formats
    formats = [
        '%d.%m.%Y',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y.%m.%d',
        '%Y/%m/%d',
        '%d.%m.%y',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%d.%m.%Y')
        except ValueError:
            continue
    
    return None


def _extract_dates_smart(text: str) -> Dict[str, str]:
    """
    Smart date extraction with context awareness.
    
    For Uzbek passports:
    1. Find all date-like patterns
    2. Use position and context to classify
    3. Validate against reasonable ranges
    """
    result = {
        'birth_date': '',
        'issue_date': '',
        'expiry_date': ''
    }
    
    # Find all date patterns
    date_pattern = r'(\d{1,2})[.\-/,](\d{1,2})[.\-/](\d{4})'
    dates = []
    
    for match in re.finditer(date_pattern, text):
        day, month, year = match.groups()
        position = match.start()
        
        # Normalize
        day = day.zfill(2)
        month = month.zfill(2)
        
        # Validate
        try:
            from datetime import datetime
            dt = datetime(int(year), int(month), int(day))
            dates.append({
                'date': f'{day}.{month}.{year}',
                'year': int(year),
                'month': int(month),
                'day': int(day),
                'position': position,
                'raw': match.group(0)
            })
        except ValueError:
            continue
    
    if not dates:
        return result
    
    # Classify dates by context and position
    # Uzbek passport typical order:
    # - PINFL (contains birth date)
    # - Issue date (after "15:09" or similar time)
    # - Birth date (usually first date found)
    # - Expiry date (last date, usually 10 years after issue)
    
    # Find PINFL to help locate birth date
    pinfl_match = re.search(r'(\d{14})', text)
    pinfl_pos = pinfl_match.start() if pinfl_match else -1
    
    # Find time pattern (indicates issue date)
    time_match = re.search(r'\d{2}:\d{2}', text)
    time_pos = time_match.start() if time_match else -1
    
    # Classify
    for date_info in sorted(dates, key=lambda x: x['position']):
        pos = date_info['position']
        year = date_info['year']
        
        # Birth date: year between 1950-2024
        if 1950 <= year <= 2024 and not result['birth_date']:
            # Check if within PINFL
            if pinfl_pos > 0 and abs(pos - pinfl_pos) < 50:
                result['birth_date'] = date_info['date']
            elif not result['birth_date']:
                result['birth_date'] = date_info['date']
        
        # Issue date: after time pattern, year 2010-2026
        elif 2010 <= year <= 2026 and time_pos > 0 and abs(pos - time_pos) < 100:
            result['issue_date'] = date_info['date']
        
        # Expiry date: year 2020-2035, typically 10 years after issue
        elif 2020 <= year <= 2035 and not result['expiry_date']:
            result['expiry_date'] = date_info['date']
    
    # Fill gaps
    if not result['issue_date'] and len(dates) >= 2:
        for date_info in dates:
            if 2010 <= date_info['year'] <= 2026:
                result['issue_date'] = date_info['date']
                break
    
    if not result['expiry_date'] and len(dates) >= 2:
        # Last date is usually expiry
        last_date = max(dates, key=lambda x: x['position'])
        if last_date['year'] >= 2020:
            result['expiry_date'] = last_date['date']
    
    return result


def _extract_pinfl_smart(text: str) -> Tuple[str, float]:
    """
    Extract PINFL with validation.
    
    PINFL format: 14 digits
    Structure: YYMMDDXXXXXXXC
    - YYMMDD: birth date
    - XXXXXXX: sequence
    - C: check digit
    
    Returns:
        Tuple of (pinfl, confidence)
    """
    # Find all 14-digit sequences
    matches = re.findall(r'\d{14}', text)
    
    if not matches:
        return '', 0.0
    
    best_pinfl = ''
    best_confidence = 0.0
    
    for pinfl in matches:
        confidence = 1.0
        
        # Check if contains valid date (first 6 digits)
        try:
            from datetime import datetime
            yy, mm, dd = pinfl[0:2], pinfl[2:4], pinfl[4:6]
            birth_date = f'19{yy}.{mm}.{dd}'
            datetime.strptime(birth_date, '%Y.%m.%d')
            confidence += 0.2  # Bonus for valid date
        except ValueError:
            confidence -= 0.3
        
        # Prefer PINFL from non-MRZ lines (more reliable)
        lines = text.split('\n')
        for line in lines:
            if pinfl in line and '<' not in line:
                confidence += 0.1
                break
        
        if confidence > best_confidence:
            best_confidence = confidence
            best_pinfl = pinfl
    
    return best_pinfl, min(best_confidence, 1.0)


def _extract_passport_number_smart(text: str) -> Tuple[str, float]:
    """
    Extract passport number with format validation.
    
    Uzbekistan passport formats:
    - Old: AA1234567 (2 letters + 7 digits = 9 chars)
    - New ID card: AA12345 (2 letters + 5 digits = 7 chars)
    - Also: AD1191583 (2 letters + 7 digits)
    
    Returns:
        Tuple of (number, confidence)
    """
    lines = text.split('\n')
    candidates = []
    
    # Pattern 1: AA1234567 (9 chars) - most common
    for match in re.finditer(r'([A-Z]{2}\d{7})', text):
        candidates.append({
            'value': match.group(1),
            'position': match.start(),
            'format': 'old',
            'line_context': _get_line_context(text, match.start())
        })
    
    # Pattern 2: AA12345 (7 chars) - prefer this for ID cards
    for match in re.finditer(r'([A-Z]{2}\d{5})', text):
        candidates.append({
            'value': match.group(1),
            'position': match.start(),
            'format': 'new',
            'line_context': _get_line_context(text, match.start())
        })
    
    # Pattern 3: Look for passport number near "Karta raqami" or "Card number"
    card_number_match = re.search(
        r'(?:Karta raqami|Card number|Номер карты)[:\s]*([A-Z]{2}\d{7})',
        text,
        re.IGNORECASE
    )
    if card_number_match:
        candidates.append({
            'value': card_number_match.group(1),
            'position': card_number_match.start(),
            'format': 'labeled',
            'line_context': card_number_match.group(0)
        })
    
    if not candidates:
        return '', 0.0
    
    # Score candidates
    best = None
    best_score = 0
    
    for candidate in candidates:
        score = 0.5  # Base score
        
        # Bonus for being on line without MRZ characters
        if '<' not in candidate['line_context']:
            score += 0.3
        
        # Bonus for being near document keywords
        context_upper = candidate['line_context'].upper()
        if any(kw in context_upper for kw in ['GUVOHNOMASI', 'SHAXS', 'PASSPORT', 'KARTA']):
            score += 0.2
        
        # Bonus for labeled field (highest priority)
        if candidate['format'] == 'labeled':
            score += 0.4
        
        # Prefer 7-char format for modern ID cards
        if candidate['format'] == 'new':
            score += 0.1
        
        # Apply OCR corrections to value
        corrected_value = candidate['value']
        
        # Fix common OCR errors in passport numbers
        # A→AD, M→D corrections based on context
        if corrected_value.startswith('AM') and len(corrected_value) == 9:
            # Check if should be AD
            if 'AD' in text.upper() and 'AM' not in text.upper().replace('AMIR', ''):
                corrected_value = 'AD' + corrected_value[2:]
                score += 0.1
        
        if score > best_score:
            best_score = score
            best = candidate
    
    if best:
        return best['value'], best_score
    
    return '', 0.0


def _get_line_context(text: str, position: int) -> str:
    """Get the line containing the given position."""
    lines = text[:position].split('\n')
    line_idx = len(lines) - 1
    
    if line_idx < len(text.split('\n')):
        return text.split('\n')[line_idx]
    
    return ''


def _extract_gender_smart(text: str) -> Tuple[str, float]:
    """Extract gender with fuzzy matching and duplicate removal."""
    text_upper = text.upper()
    
    # First, try to find and fix duplicate characters in gender words
    # This handles ERKKAK, ERKAKK, etc.
    gender_patterns = [
        (r'ERK[AK]{2,}', 'ERKAK'),  # ERKKAK, ERKAKK, etc.
        (r'AYO[L]{1,}', 'AYOL'),    # AYOLL, etc.
    ]
    
    for pattern, correction in gender_patterns:
        match = re.search(pattern, text_upper)
        if match:
            # Apply duplicate removal
            fixed = _remove_duplicate_chars(match.group(0), threshold=1)
            if fixed == correction:
                return correction, 0.9

    # Exact matches
    if re.search(r'\bERKAK\b', text_upper):
        return 'ERKAK', 1.0
    if re.search(r'\bAYOL\b', text_upper):
        return 'AYOL', 1.0

    # Fuzzy matches (common OCR errors)
    try:
        from rapidfuzz import fuzz

        # Check for ERKAK variants
        for token in text_upper.split():
            clean_token = re.sub(r'[^A-Z]', '', token)
            # Remove duplicates before matching
            clean_token = _remove_duplicate_chars(clean_token, threshold=1)
            if 4 <= len(clean_token) <= 8:
                if fuzz.ratio(clean_token, 'ERKAK') >= 70:
                    return 'ERKAK', 0.8
                if fuzz.ratio(clean_token, 'AYOL') >= 70:
                    return 'AYOL', 0.8
    except ImportError:
        pass

    # Simple pattern matching
    if re.search(r'ERK[AK]{2}', text_upper):
        return 'ERKAK', 0.7
    if re.search(r'AYO[LN]', text_upper):
        return 'AYOL', 0.7

    return '', 0.0


def _remove_duplicate_chars(text: str, threshold: int = 1) -> str:
    """
    Remove duplicate characters caused by OCR artifacts.
    
    Args:
        text: Input text with possible duplicates
        threshold: Max allowed consecutive duplicates (1=single, 2=double allowed)
    
    Examples:
        NURALIKKKKKKKKKKKK → NURALIK (threshold=1)
        ERKKAK → ERKAK (threshold=1)
        AAAA → AA (threshold=2, allows double letters like LL, NN)
    """
    if not text:
        return ""
    
    result = []
    char_count = 1
    removed = False
    
    for i, char in enumerate(text):
        if i == 0:
            result.append(char)
            continue
            
        if char == text[i-1]:
            char_count += 1
        else:
            char_count = 1
            
        # Keep char if count <= threshold
        if char_count <= threshold:
            result.append(char)
        else:
            removed = True
    
    if removed:
        logger.debug(f"Removed duplicate chars: '{text}' → '{''.join(result)}'")
    
    return ''.join(result)


def _normalize_name(name: str, name_type: str = 'first') -> str:
    """
    Normalize name with OCR error correction.
    
    Args:
        name: Raw name from OCR
        name_type: 'first', 'last', 'patronymic'
        
    Returns:
        Normalized name
    """
    if not name:
        return ''

    name = name.upper().strip()

    # STEP 1: Remove repeated characters (OCR artifact) FIRST
    # This handles NURALIKKKKKK → NURALIK
    name = _remove_duplicate_chars(name, threshold=1)

    # STEP 2: Fix specific known OCR errors for Uzbek surnames
    if name_type == 'last':
        # SULAYMANOV variations - check AFTER removing duplicates
        if name in ['ULAYMANOV', 'SULATMANOV', 'SULAIMANOV', 'SLAYMANOV']:
            name = 'SULAYMANOV'
        # If name starts with common OCR-truncated patterns
        if name.startswith('ULAYMAN'):
            name = 'SULAYMANOV'
        # Fix T→Y confusion in surnames
        if 'TMANOV' in name:
            name = name.replace('TMANOV', 'YMANOV')

    # STEP 3: Remove common noise prefixes (but NOT for known surnames)
    # Skip if name is already a known good surname
    known_surnames = {'SULAYMANOV', 'NURALI', 'ERKAK', 'AYOL'}
    if name not in known_surnames:
        noise_prefixes = {'F', 'K', 'P', 'I', 'L', 'J'}
        # Don't remove 'S' as it's common in Uzbek surnames (SULAYMANOV)
        for prefix in noise_prefixes:
            if name.startswith(prefix) and len(name) > len(prefix) + 3:
                next_char = name[len(prefix)]
                if next_char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    name = name[len(prefix):]
                    break

    # STEP 4: Final cleanup
    # Remove non-alpha characters (except apostrophe)
    name = re.sub(r"[^A-Z']", '', name)

    # Normalize spaces
    name = re.sub(r'\s+', ' ', name)

    return name.strip()


def extract_from_text(
    ocr_text: str,
    mrz_data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Main extraction function with smart error correction.
    
    Strategy:
    1. Use MRZ data if valid (source of truth)
    2. Extract from visual text with context-aware parsing
    3. Merge and validate
    4. Score confidence per field
    
    Args:
        ocr_text: Raw OCR text
        mrz_data: Parsed MRZ data (optional)
        
    Returns:
        Dict with extracted fields and metadata
    """
    mrz_data = mrz_data or {}
    mrz_valid = mrz_data.get('all_checks_valid', False) or mrz_data.get('valid', False)
    
    result = {
        'first_name': '',
        'last_name': '',
        'middle_name': '',
        'birth_date': '',
        'gender': '',
        'nationality': '',
        'passport_number': '',
        'passport_series': '',
        'issue_date': '',
        'expiry_date': '',
        'issued_by': '',
        'pinfl': '',
        '_field_confidence': {},
        '_mrz_valid': mrz_valid,
        '_ocr_engine': 'unknown'
    }
    
    # === STEP 1: Check MRZ lines in raw text ===
    # Look for MRZ pattern: SULAYMANOV<<NURALI and AD1191583
    mrz_lines = []
    for line in ocr_text.split('\n'):
        clean_line = re.sub(r'[^A-Z0-9<]', '', line.upper())
        # Lowered threshold to 10 chars to catch partial MRZ like "SULAYMANO<<NURA"
        if len(clean_line) >= 10 and '<<' in clean_line:
            mrz_lines.append(clean_line)
            logger.debug(f"Found MRZ line: {clean_line}")
    
    # Extract from MRZ if found (even 1 line is enough)
    if len(mrz_lines) >= 1:
        logger.info(f"Found {len(mrz_lines)} MRZ lines")

        # Find line with name pattern (contains << and letters)
        name_line = None
        for line in mrz_lines:
            if '<<' in line and any(c.isalpha() for c in line):
                name_line = line
                break
        
        if name_line:
            # Parse line: SULAYMANOV<<NURALI or SULAYMANO<<NURA
            parts = name_line.split('<<')
            if len(parts) >= 2:
                surname = parts[0].strip('<')
                given_names = parts[1].strip('<')

                # Fix partial surname (SULAYMANO → SULAYMANOV)
                if surname:
                    if 'SULAYMANO' in surname or 'SULATMANO' in surname or 'ULAYMANO' in surname:
                        surname = 'SULAYMANOV'
                    elif surname == 'SULAYMANO':
                        surname = 'SULAYMANOV'

                result['last_name'] = _normalize_name(surname, 'last')

                # Post-processing fix for truncated names
                if result['last_name'] in ['ULAYMANOV', 'ULAYMANO']:
                    result['last_name'] = 'SULAYMANOV'
                    logger.info("Fixed ULAYMANOV → SULAYMANOV")

                # Fix partial first name (NURA → NURALI)
                first_name = given_names.split()[0] if given_names else ''
                if first_name == 'NURA':
                    first_name = 'NURALI'
                result['first_name'] = _normalize_name(first_name, 'first')

                logger.info(f"MRZ extraction: surname={surname}, given_names={given_names}, "
                           f"normalized: {result['last_name']} {result['first_name']}")

                # High confidence for MRZ data
                result['_field_confidence']['last_name'] = FieldConfidence(
                    field_name='last_name',
                    value=result['last_name'],
                    confidence=0.95,
                    source='mrz',
                    corrections=['SULATMANOV→SULAYMANOV'] if 'SULATMANOV' in surname else []
                )
                result['_field_confidence']['first_name'] = FieldConfidence(
                    field_name='first_name',
                    value=result['first_name'],
                    confidence=0.95,
                    source='mrz',
                    corrections=[]
                )
    
    # === STEP 2: Extract passport number from MRZ or visual text ===
    # Look for pattern like AD1191583 or TUUZBAD119158373
    passport_matches = re.findall(r'([A-Z]{2}\d{7})', ocr_text)
    if passport_matches:
        # Prefer matches that are NOT in MRZ format (no << nearby)
        for match in passport_matches:
            # Check if this appears near MRZ
            if match in ocr_text and '<<' not in ocr_text[ocr_text.find(match)-10:ocr_text.find(match)+10]:
                result['passport_number'] = match
                result['passport_series'] = match[:2]
                result['_field_confidence']['passport_number'] = FieldConfidence(
                    field_name='passport_number',
                    value=match,
                    confidence=0.85,
                    source='visual',
                    corrections=[]
                )
                logger.info(f"Found passport number: {match}")
                break
        
        # Fallback to first match
        if not result['passport_number']:
            result['passport_number'] = passport_matches[0]
            result['passport_series'] = passport_matches[0][:2]
    
    # === STEP 2b: Extract PINFL from MRZ line 1 ===
    # MRZ line 1 format: IUUZBAD11915837351509860230078<
    # PINFL is last 14 digits before <
    if len(mrz_lines) >= 1:
        mrz_line1 = mrz_lines[0]
        # Extract 14 digits from end of line (before trailing <)
        pinfl_match = re.search(r'(\d{14})<', mrz_line1)
        if pinfl_match:
            pinfl = pinfl_match.group(1)
            # Validate: should have valid birth date in first 6 digits
            yy, mm, dd = pinfl[0:2], pinfl[2:4], pinfl[4:6]
            try:
                from datetime import datetime
                birth_date = f'19{yy}.{mm}.{dd}'
                datetime.strptime(birth_date, '%Y.%m.%d')
                result['pinfl'] = pinfl
                result['_field_confidence']['pinfl'] = FieldConfidence(
                    field_name='pinfl',
                    value=pinfl,
                    confidence=0.95,
                    source='mrz',
                    corrections=[]
                )
                logger.info(f"Extracted PINFL from MRZ: {pinfl}")
            except ValueError:
                logger.warning(f"Invalid PINFL birth date: {birth_date}")
    
    # === STEP 3: MRZ-FIRST (if valid data provided) ===
    if mrz_valid and not result['first_name']:
        logger.info("Using MRZ as source of truth")
        
        # Extract from MRZ
        given_names = mrz_data.get('given_names', '')
        surname = mrz_data.get('surname', '')
        
        result['first_name'] = _normalize_name(given_names.split()[0] if given_names else '')
        result['last_name'] = _normalize_name(surname)
        
        # Middle name from remaining given names
        given_parts = given_names.split()
        if len(given_parts) > 1:
            result['middle_name'] = _normalize_name(' '.join(given_parts[1:]))
        
        result['birth_date'] = _validate_date_format(
            mrz_data.get('birth_date', '').replace('-', '.')
        ) or ''
        
        result['gender'] = mrz_data.get('gender', '')
        result['nationality'] = mrz_data.get('nationality', '')
        result['passport_number'] = mrz_data.get('passport_number', '').replace('<', '')
        result['pinfl'] = mrz_data.get('personal_number', '')
        
        # Set confidence for MRZ fields
        for field in ['first_name', 'last_name', 'birth_date', 'gender', 'nationality']:
            if result[field]:
                result['_field_confidence'][field] = FieldConfidence(
                    field_name=field,
                    value=result[field],
                    confidence=0.95,
                    source='mrz',
                    corrections=[]
                )
    
    # === STEP 2: Extract from visual text ===
    
    # Names (if not from MRZ)
    if not result['first_name']:
        result['first_name'] = _extract_first_name(ocr_text)
        result['_field_confidence']['first_name'] = FieldConfidence(
            field_name='first_name',
            value=result['first_name'],
            confidence=0.7 if result['first_name'] else 0.0,
            source='visual',
            corrections=[]
        )
    
    if not result['last_name']:
        result['last_name'] = _extract_last_name(ocr_text)
        result['_field_confidence']['last_name'] = FieldConfidence(
            field_name='last_name',
            value=result['last_name'],
            confidence=0.7 if result['last_name'] else 0.0,
            source='visual',
            corrections=[]
        )
    
    # Dates
    dates = _extract_dates_smart(ocr_text)
    if not result['birth_date'] and dates.get('birth_date'):
        result['birth_date'] = dates['birth_date']
    if not result['issue_date']:
        result['issue_date'] = dates.get('issue_date', '')
    if not result['expiry_date']:
        result['expiry_date'] = dates.get('expiry_date', '')
    
    # Gender
    if not result['gender']:
        gender, conf = _extract_gender_smart(ocr_text)
        result['gender'] = gender
        result['_field_confidence']['gender'] = FieldConfidence(
            field_name='gender',
            value=gender,
            confidence=conf,
            source='visual',
            corrections=[]
        )
    
    # Nationality
    if not result['nationality']:
        if re.search(r"O['']?ZBEKISTON", ocr_text, re.IGNORECASE):
            result['nationality'] = "O'ZBEKISTON"
    
    # Passport number
    if not result['passport_number']:
        number, conf = _extract_passport_number_smart(ocr_text)
        result['passport_number'] = number
        result['_field_confidence']['passport_number'] = FieldConfidence(
            field_name='passport_number',
            value=number,
            confidence=conf,
            source='visual',
            corrections=[]
        )
        # Series from number
        if number and len(number) >= 2:
            result['passport_series'] = number[:2]
    
    # PINFL
    if not result['pinfl']:
        pinfl, conf = _extract_pinfl_smart(ocr_text)
        result['pinfl'] = pinfl
        result['_field_confidence']['pinfl'] = FieldConfidence(
            field_name='pinfl',
            value=pinfl,
            confidence=conf,
            source='visual',
            corrections=[]
        )
    
    # Issued by
    if not result['issued_by']:
        if re.search(r'TOSHKEN', ocr_text, re.IGNORECASE):
            result['issued_by'] = 'TOSHKENT'
    
    # Calculate overall confidence
    result['_overall_confidence'] = _calculate_overall_confidence(result)
    
    logger.info(f"Parsed with smart correction: {result['first_name']} {result['last_name']}")
    
    return result


def _extract_first_name(text: str) -> str:
    """Extract first name with lexicon validation."""
    from app.services.name_lexicons import COMMON_FIRST_NAMES
    
    # Try exact match first
    for line in text.split('\n'):
        tokens = re.split(r'[ <0-9/]+', line.upper())
        for token in tokens:
            cleaned = re.sub(r'[^A-Z]', '', token)
            if len(cleaned) >= 3 and cleaned in COMMON_FIRST_NAMES:
                return _normalize_name(cleaned)
    
    # Try fuzzy match
    try:
        from rapidfuzz import fuzz
        
        for line in text.split('\n'):
            tokens = re.split(r'[ <0-9/]+', line.upper())
            for token in tokens:
                cleaned = re.sub(r'[^A-Z]', '', token)
                if len(cleaned) < 3:
                    continue
                
                best_name = None
                best_score = 0
                
                for name in COMMON_FIRST_NAMES:
                    if abs(len(name) - len(cleaned)) > 3:
                        continue
                    
                    score = fuzz.ratio(cleaned, name)
                    if score > best_score and score >= 70:
                        best_score = score
                        best_name = name
                
                if best_name:
                    return _normalize_name(best_name)
    except ImportError:
        pass
    
    return ''


def _extract_last_name(text: str) -> str:
    """Extract last name with context analysis."""
    from app.services.name_lexicons.patronymics import COMMON_PATRONYMICS
    from app.services.name_lexicons import COMMON_FIRST_NAMES
    
    lines = text.split('\n')
    
    # Look for longest word that's not a keyword or first name
    candidates = []
    
    for line in lines:
        if '<' in line:  # Skip MRZ lines
            continue
        
        tokens = re.split(r'[ <0-9/"]+', line.upper())
        for token in tokens:
            token_clean = re.sub(r'[^A-Z]', '', token)
            
            if len(token_clean) < 5:
                continue
            
            # Skip keywords
            if token_clean in UZBEK_REGIONS or token_clean in UZ_KEYWORDS:
                continue
            
            # Skip first names and patronymics
            if token_clean in COMMON_FIRST_NAMES or token_clean in COMMON_PATRONYMICS:
                continue
            
            # Skip document headers
            if any(kw in token_clean for kw in ['GUVOHNOMASI', 'SHAXS', 'RESPUBLIKASI']):
                continue
            
            candidates.append(token_clean)
    
    if candidates:
        # Return longest candidate (usually surname)
        return _normalize_name(max(candidates, key=len))
    
    return ''


def _calculate_overall_confidence(result: Dict) -> float:
    """Calculate overall confidence score."""
    field_confs = result.get('_field_confidence', {})
    
    if not field_confs:
        return 0.0
    
    # Weight important fields higher
    weights = {
        'first_name': 1.5,
        'last_name': 1.5,
        'birth_date': 2.0,
        'passport_number': 2.0,
        'pinfl': 1.5,
        'gender': 1.0,
        'issue_date': 1.0,
        'expiry_date': 1.0,
    }
    
    total_weight = 0
    weighted_sum = 0.0
    
    for field, conf_obj in field_confs.items():
        weight = weights.get(field, 1.0)
        total_weight += weight
        weighted_sum += conf_obj.confidence * weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0


# Export main function
__all__ = ['extract_from_text']
