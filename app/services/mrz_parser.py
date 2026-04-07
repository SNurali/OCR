import re
from typing import Dict, Optional, Tuple


class MRZParser:
    """Парсер Machine Readable Zone (MRZ) для паспортов и ID-карт."""

    CHECK_DIGITS = {
        "0": 0,
        "1": 1,
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "<": 0,
        "A": 10,
        "B": 11,
        "C": 12,
        "D": 13,
        "E": 14,
        "F": 15,
        "G": 16,
        "H": 17,
        "I": 18,
        "J": 19,
        "K": 20,
        "L": 21,
        "M": 22,
        "N": 23,
        "O": 24,
        "P": 25,
        "Q": 26,
        "R": 27,
        "S": 28,
        "T": 29,
        "U": 30,
        "V": 31,
        "W": 32,
        "X": 33,
        "Y": 34,
        "Z": 35,
    }

    WEIGHTS = [7, 3, 1]

    RU_MRZ_MAP = {
        "A": "А",
        "B": "Б",
        "V": "В",
        "G": "Г",
        "D": "Д",
        "E": "Е",
        "2": "Ж",
        "Z": "З",
        "I": "И",
        "Q": "Й",
        "K": "К",
        "L": "Л",
        "M": "М",
        "N": "Н",
        "O": "О",
        "P": "П",
        "R": "Р",
        "S": "С",
        "T": "Т",
        "U": "У",
        "F": "Ф",
        "H": "Х",
        "C": "Ц",
        "3": "Ч",
        "4": "Ш",
        "8": "Щ",
        "9": "Ъ",
        "X": "Ы",
        "7": "Ь",
        "J": "Ю",
        "W": "Я",
    }

    # Uzbekistan-specific MRZ transliteration map
    UZ_MRZ_MAP = {
        "A": "А",
        "B": "Б",
        "V": "В",
        "G": "Г",
        "D": "Д",
        "E": "Е",
        "2": "Ж",
        "Z": "З",
        "I": "И",
        "Q": "Қ",
        "K": "К",
        "L": "Л",
        "M": "М",
        "N": "Н",
        "O": "О",
        "P": "П",
        "R": "Р",
        "S": "С",
        "T": "Т",
        "U": "У",
        "F": "Ф",
        "H": "Ҳ",
        "C": "Ц",
        "3": "Ч",
        "4": "Ш",
        "8": "Ъ",
        "9": "Ў",
        "X": "Х",
        "7": "Ь",
        "J": "Й",
        "W": "Ў",
        "Y": "У",
    }

    def __init__(self):
        self.mrz_pattern_td3 = re.compile(
            r"^[A-Z<]{2}[A-Z0-9<]{9}\d[A-Z0-9<]{14}\d{7}[MF<]\d{7}[A-Z0-9<]{14}\d{7}\d$"
        )
        self.mrz_pattern_td1 = re.compile(
            r"^[A-Z<]{2}[A-Z0-9<]{9}\d{7}[A-Z0-9<]{15}\d$"
        )

    def validate_check_digit(self, data: str, check_digit: str) -> bool:
        """Валидация контрольной цифры."""
        if len(data) == 0:
            return False

        total = 0
        for i, char in enumerate(data):
            value = self.CHECK_DIGITS.get(char.upper(), 0)
            weight = self.WEIGHTS[i % 3]
            total += value * weight

        calculated = total % 10
        expected = int(check_digit) if check_digit.isdigit() else 0

        return calculated == expected

    def validate_composite_check(self, line: str) -> bool:
        """Валидация составной контрольной цифры."""
        if len(line) < 30:
            return False

        composite_data = line[5:10] + line[13:20] + line[21:43]
        check_digit = line[28]

        return self.validate_check_digit(composite_data, check_digit)

    def _reverse_transliterate_ru(self, text: str) -> str:
        """Обратная транслитерация для РФ паспортов (из MRZ в кириллицу)."""
        if not text:
            return text
        result = []
        for char in text.upper():
            if char in self.RU_MRZ_MAP:
                result.append(self.RU_MRZ_MAP[char])
            elif char.isalpha() or char.isdigit():
                # Если символ не в маппинге, оставляем как есть.
                # На практике все буквы должны попасть. Исключение - пробелы от <.
                result.append(char)
            else:
                result.append(char)
        return "".join(result)

    def _reverse_transliterate_uz(self, text: str) -> str:
        """Обратная транслитерация для Узбекистан паспортов (из MRZ в кириллицу)."""
        if not text:
            return text
        result = []
        for char in text.upper():
            if char in self.UZ_MRZ_MAP:
                result.append(self.UZ_MRZ_MAP[char])
            elif char == "Y":
                # Special handling for 'Y' which often represents Cyrillic 'У' in OCR
                result.append("У")
            elif char.isalpha() or char.isdigit():
                # Если символ не в маппинге, оставляем как есть.
                result.append(char)
            else:
                result.append(char)
        return "".join(result)

    def parse_td3(self, line1: str, line2: str) -> Dict:
        """Парсинг TD3 формата (паспорт, 2 строки по 44 символа)."""
        line1 = line1.strip().upper()
        line2 = line2.strip().upper()

        if len(line1) < 44 or len(line2) < 44:
            return {"valid": False, "error": "Invalid line length"}

        result = {
            "valid": True,
            "type": "TD3",
            "document_type": line1[0:2],
            "issuing_country": line1[2:5],
            "surname": line1[5:44].split("<<")[0].replace("<", " ").strip(),
            "given_names": "",
            "passport_number": "",
            "nationality": "",
            "birth_date": "",
            "gender": "",
            "expiry_date": "",
            "personal_number": "",
            "line1": line1,
            "line2": line2,
        }

        if "<<" in line1[5:44]:
            parts = line1[5:44].split("<<", 1)
            result["surname"] = parts[0].replace("<", " ").strip()
            result["given_names"] = (
                parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
            )
        else:
            # Fallback для случаев, когда << превратилось в < или пропало
            mrz_payload = line1[5:44].strip()
            # Если есть одиночный <, пробуем разделить по нему
            if "<" in mrz_payload:
                parts = mrz_payload.split("<", 1)
                result["surname"] = parts[0].strip()
                result["given_names"] = parts[1].replace("<", " ").strip()
            else:
                result["surname"] = mrz_payload.replace("<", " ").strip()

        result["passport_number"] = line2[0:9].replace("<", "")
        result["nationality"] = line2[10:13]

        birth_raw = line2[13:19]
        result["birth_date"] = self._format_date(birth_raw)

        result["gender"] = (
            "M" if line2[20] == "M" else ("F" if line2[20] == "F" else "")
        )

        expiry_raw = line2[21:27]
        result["expiry_date"] = self._format_date(expiry_raw)

        result["personal_number"] = line2[28:42].replace("<", "")

        result["passport_check_valid"] = self.validate_check_digit(line2[0:9], line2[9])
        result["birth_check_valid"] = self.validate_check_digit(birth_raw, line2[19])
        result["expiry_check_valid"] = self.validate_check_digit(expiry_raw, line2[26])
        result["composite_check_valid"] = self.validate_check_digit(
            line2[0:10] + line2[13:20] + line2[21:43], line2[28]
        )

        result["all_checks_valid"] = all(
            [
                result["passport_check_valid"],
                result["birth_check_valid"],
                result["expiry_check_valid"],
                result["composite_check_valid"],
            ]
        )

        # Check if this might be an Uzbek passport that was misidentified as RUS
        # Often OCR mistakes "UZB" for "RUS" or similar issues occur
        original_country = result["issuing_country"]
        if (
            result["issuing_country"] == "RUS"
            or result["document_type"] == "PN"
            or "UZB" in result.get("nationality", "")
            or "UZB" in result.get("personal_number", "")
        ):
            # Check if this might actually be UZB based on other fields
            if (
                "UZB" in line1
                or "UZB" in line2
                or "O'ZBEKISTON" in line1
                or "O'ZBEKISTON" in line2
            ):
                result["issuing_country"] = "UZB"

        if result["issuing_country"] == "RUS" or result["document_type"] == "PN":
            # Выполняем автоперевод для российских паспортов
            result["surname"] = self._reverse_transliterate_ru(result["surname"])
            result["given_names"] = self._reverse_transliterate_ru(
                result["given_names"]
            )
        elif result["issuing_country"] == "UZB":
            # Выполняем автоперевод для узбекских паспортов
            result["surname"] = self._reverse_transliterate_uz(result["surname"])
            result["given_names"] = self._reverse_transliterate_uz(
                result["given_names"]
            )

        return result

    def parse_td1(self, line1: str, line2: str, line3: str) -> Dict:
        """Парсинг TD1 формата (ID-карта, 3 строки по 30 символов)."""
        line1 = line1.strip().upper()
        line2 = line2.strip().upper()
        line3 = line3.strip().upper()

        if len(line1) < 30 or len(line2) < 30 or len(line3) < 30:
            return {"valid": False, "error": "Invalid line length"}

        result = {
            "valid": True,
            "type": "TD1",
            "document_type": line1[0:2],
            "issuing_country": line1[2:5],
            "passport_number": line1[5:14].replace("<", ""),
            "nationality": "",
            "birth_date": "",
            "gender": "",
            "expiry_date": "",
            "surname": "",
            "given_names": "",
            "personal_number": "",
            "line1": line1,
            "line2": line2,
            "line3": line3,
        }

        result["passport_check_valid"] = self.validate_check_digit(
            line1[5:14], line1[14]
        )

        # Персональный номер из line1 (позиции 15-29 для TD1)
        personal_from_line1 = line1[15:30].replace("<", "")

        birth_raw = line2[0:6]
        result["birth_date"] = self._format_date(birth_raw)
        result["birth_check_valid"] = self.validate_check_digit(birth_raw, line2[6])

        result["gender"] = "M" if line2[7] == "M" else ("F" if line2[7] == "F" else "")

        expiry_raw = line2[8:14]
        result["expiry_date"] = self._format_date(expiry_raw)
        result["expiry_check_valid"] = self.validate_check_digit(expiry_raw, line2[14])

        result["nationality"] = line2[15:18]
        if result["nationality"] in {"XXX", "<<<", ""}:
            fallback_nationality = line2[18:21]
            if re.match(r"^[A-Z]{3}$", fallback_nationality):
                result["nationality"] = fallback_nationality

        # Персональный номер (ПИНФЛ) — позиции 15-29 в line1 для узбекских ID
        result["personal_number"] = (
            personal_from_line1
            if personal_from_line1
            else line2[18:29].replace("<", "")
        )

        if "<<" in line3:
            parts = line3.split("<<", 1)
            result["surname"] = parts[0].replace("<", " ").strip()
            result["given_names"] = (
                parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
            )

        composite_data = line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29]
        result["composite_check_valid"] = self.validate_check_digit(
            composite_data, line2[29]
        )

        # Check if this might be an Uzbek document that was misidentified as RUS
        original_country = result["issuing_country"]
        if (
            result["issuing_country"] == "RUS"
            or "UZB" in result.get("nationality", "")
            or "UZB" in result.get("personal_number", "")
        ):
            # Check if this might actually be UZB based on other fields
            if (
                "UZB" in line1
                or "UZB" in line2
                or "UZB" in line3
                or "O'ZBEKISTON" in line1
                or "O'ZBEKISTON" in line2
            ):
                result["issuing_country"] = "UZB"

        if result["issuing_country"] == "RUS":
            # Выполняем автоперевод для российских паспортов
            result["surname"] = self._reverse_transliterate_ru(result["surname"])
            result["given_names"] = self._reverse_transliterate_ru(
                result["given_names"]
            )
        elif result["issuing_country"] == "UZB":
            # Выполняем автоперевод для узбекских паспортов
            result["surname"] = self._reverse_transliterate_uz(result["surname"])
            result["given_names"] = self._reverse_transliterate_uz(
                result["given_names"]
            )

        result["all_checks_valid"] = all(
            [
                result["passport_check_valid"],
                result["birth_check_valid"],
                result["expiry_check_valid"],
                result["composite_check_valid"],
            ]
        )

        return result

    def _format_date(self, date_str: str) -> str:
        """Форматирование даты из YYMMDD в YYYY-MM-DD. Проверка валидности."""
        if len(date_str) != 6 or not date_str.isdigit():
            return date_str

        year = int(date_str[0:2])
        month = date_str[2:4]
        day = date_str[4:6]

        full_year = 2000 + year if year < 50 else 1900 + year

        from datetime import datetime

        try:
            datetime(full_year, int(month), int(day))
        except ValueError:
            return ""

        return f"{full_year}-{month}-{day}"

    def detect_and_parse(self, lines: list) -> Dict:
        """Автоопределение формата и парсинг MRZ."""
        cleaned = [l.strip().upper() for l in lines if l.strip()]

        if not cleaned:
            return {"valid": False, "error": "No MRZ lines found"}

        if len(cleaned) >= 2 and len(cleaned[0]) >= 44:
            return self.parse_td3(cleaned[0], cleaned[1])
        elif len(cleaned) >= 3 and len(cleaned[0]) >= 28:
            return self.parse_td1(cleaned[0], cleaned[1], cleaned[2])
        elif len(cleaned) == 2:
            if len(cleaned[0]) >= 44:
                return self.parse_td3(cleaned[0], cleaned[1])
            return self.parse_td1(cleaned[0], cleaned[1], "")

        return {"valid": False, "error": "Cannot determine MRZ format"}

    def _clean_mrz_line(self, line: str) -> str:
        """Очистка строки от мусора, нормализация разделителей."""
        # Cyrillic → Latin
        line = (
            line.replace("М", "M")
            .replace("О", "O")
            .replace("С", "C")
            .replace("А", "A")
            .replace("В", "B")
            .replace("Е", "E")
            .replace("Н", "H")
            .replace("К", "K")
            .replace("Р", "P")
            .replace("Т", "T")
            .replace("Х", "X")
            .replace("У", "U")  # Fixed: Cyrillic У should be U, not Y
        )

        raw = re.sub(r"[^A-Z0-9< ]", "", line.upper())

        # Fix common OCR errors
        # Y often should be U in Cyrillic contexts
        raw = re.sub(r"(?<=[A-Z])Y(?=[A-Z])", "U", raw)  # Y between letters might be U
        # Also handle standalone Y that should be U
        raw = re.sub(r"(?<=[A-Z])Y(?=<)", "U", raw)

        # 4 → < (заполнитель, часто путается с <)
        # 6 НЕ заменяем — это часть даты рождения в line2
        cleaned_digits = re.sub(r"4", "<", raw)

        spaceless = cleaned_digits.replace(" ", "")

        # Обрезаем до правильной длины MRZ
        if 28 <= len(spaceless) <= 32:
            # TD1 = 30 символов
            return spaceless[:30]
        elif 42 <= len(spaceless) <= 46:
            # TD3 = 44 символа
            return spaceless[:44]
        elif len(spaceless) > 46:
            # Если длиннее 46, это скорее всего TD3 с мусором в конце
            return spaceless[:44]

        if raw.count(" ") > 5:
            return spaceless[:30] if len(spaceless) >= 28 else spaceless

        return (
            raw.replace(" ", "<")[:44]
            if len(raw.replace(" ", "<")) >= 42
            else (
                raw.replace(" ", "<")[:30]
                if len(raw.replace(" ", "<")) >= 28
                else raw.replace(" ", "<")
            )
        )

        raw = re.sub(r"[^A-Z0-9< ]", "", line.upper())

        # Fix common OCR errors
        # Y often should be U in Cyrillic contexts
        raw = re.sub(r"(?<=[A-Z])Y(?=[A-Z])", "U", raw)  # Y between letters might be U
        # Also handle standalone Y that should be U
        raw = re.sub(r"(?<=[A-Z])Y(?=<)", "U", raw)

        # Fix common Cyrillic transliteration errors in names:
        # X often represents И (common OCR error)
        raw = re.sub(r"(?<=[A-Z])X(?=[A-Z])", "I", raw)  # X between letters might be I

        # 4 → < (заполнитель, часто путается с <)
        # 6 НЕ заменяем — это часть даты рождения в line2
        cleaned_digits = re.sub(r"4", "<", raw)

        spaceless = cleaned_digits.replace(" ", "")

        # Обрезаем до правильной длины MRZ
        if 28 <= len(spaceless) <= 32:
            # TD1 = 30 символов
            return spaceless[:30]
        elif 42 <= len(spaceless) <= 46:
            # TD3 = 44 символа
            return spaceless[:44]
        elif len(spaceless) > 46:
            # Если длиннее 46, это скорее всего TD3 с мусором в конце
            return spaceless[:44]

        if raw.count(" ") > 5:
            return spaceless[:30] if len(spaceless) >= 28 else spaceless

        return (
            raw.replace(" ", "<")[:44]
            if len(raw.replace(" ", "<")) >= 42
            else (
                raw.replace(" ", "<")[:30]
                if len(raw.replace(" ", "<")) >= 28
                else raw.replace(" ", "<")
            )
        )


    def extract_mrz_from_text(self, full_text: str) -> Tuple[list, Optional[Dict]]:
        """Извлечение MRZ строк из полного OCR текста.

        MRZ строки определяются по:
        1. Длина 28-44 символа
        2. Содержат только [A-Z0-9<]
        3. Содержат << (двойной разделитель) или начинаются с I/P (ID/Passport)
        """
        lines = full_text.split("\n")
        mrz_lines = []

        # Паттерн: строка из MRZ символов длиной 28+
        mrz_pattern = re.compile(r"^[A-Z0-9<]{28,}$")

        for line in lines:
            cleaned = self._clean_mrz_line(line)

            if len(cleaned) < 28:
                continue

            if mrz_pattern.match(cleaned):
                # Отсеиваем строки без единого < — это почти всегда не MRZ
                if "<" not in cleaned:
                    continue
                mrz_lines.append(cleaned)

        # Если нашли 3 строки по ~30 символов → TD1 (ID карта)
        if len(mrz_lines) >= 3:
            # Берём последние 3 строки (MRZ обычно внизу)
            td1_lines = mrz_lines[-3:]
            if all(28 <= len(l) <= 32 for l in td1_lines):
                parsed = self.parse_td1(td1_lines[0], td1_lines[1], td1_lines[2])
                if parsed.get("valid"):
                    return td1_lines, parsed

            # OCR иногда даёт мусорные строки выше MRZ, поэтому ищем лучшее окно из 3 строк.
            for index in range(len(mrz_lines) - 2):
                candidate = mrz_lines[index : index + 3]
                if not all(28 <= len(line) <= 32 for line in candidate):
                    continue
                parsed = self.parse_td1(candidate[0], candidate[1], candidate[2])
                if parsed.get("valid") or parsed.get("line3", "").count("<<") > 0:
                    return candidate, parsed

        # Если 2 строки по ~44 символов → TD3 (паспорт)
        if len(mrz_lines) >= 2:
            td3_candidates = [l for l in mrz_lines if len(l) >= 42]
            if len(td3_candidates) >= 2:
                parsed = self.parse_td3(td3_candidates[-2], td3_candidates[-1])
                if parsed.get("valid"):
                    return [td3_candidates[-2], td3_candidates[-1]], parsed

        # Fallback: пробуем любые 2+ строки
        if len(mrz_lines) >= 2:
            parsed = self.detect_and_parse(mrz_lines)
            if parsed.get("valid"):
                return mrz_lines, parsed
            else:
                # Если 2+ строки, но они невалидны (например, плохая длина),
                # всё равно извлечём всё что сможем частичным парсингом.
                partial = self._parse_partial_mrz(mrz_lines)
                return mrz_lines, partial

        if len(mrz_lines) == 1:
            partial = self._parse_partial_mrz(mrz_lines)
            return mrz_lines, partial

        return mrz_lines, None

    def _parse_partial_mrz(self, mrz_lines: list) -> Dict:
        """Частичный парсинг, когда не все MRZ-строки найдены."""
        result = {
            "valid": False,
            "surname": "",
            "given_names": "",
            "partial": True,
        }

        for line in mrz_lines:
            # В строках с << (имена) чистим 0→O, 4/6→<
            if "<<" not in line and "<<" not in line.replace("0", "O"):
                continue

            cleaned = re.sub(r"0", "O", line)
            cleaned = re.sub(r"[46]", "<", cleaned)

            # Удаляем префикс документа типа "P<UZB" (от 4 до 6 символов P<XXX или IDXXX)
            if re.match(r"^[P|I|V|A][<A-Z0-9]{1,4}[A-Z]{3}", cleaned):
                cleaned = cleaned[5:]

            parts = cleaned.split("<<", 1)
            surname_part = parts[0].replace("<", " ").strip()
            given_part = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""

            if surname_part and len(surname_part) >= 2:
                result["surname"] = surname_part
            if given_part and len(given_part) >= 2:
                result["given_names"] = given_part

            if result["surname"] or result["given_names"]:
                return result

        return result


mrz_parser = MRZParser()
