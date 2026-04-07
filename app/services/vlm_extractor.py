import io
import json
import logging
import base64
import re
from typing import Optional, Dict, Any

import httpx
from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — эксперт по распознаванию паспортов Узбекистана.
Извлеки все данные из изображения паспорта и верни ТОЛЬКО валидный JSON:
{
  "first_name":"","last_name":"","middle_name":"",
  "birth_date":"DD.MM.YYYY","gender":"M/F","nationality":"",
  "passport_number":"","issue_date":"DD.MM.YYYY","expiry_date":"DD.MM.YYYY",
  "issued_by":"","pinfl":"14 цифр"
}
Правила:
- gender: верни "M" для мужского (ERKAK) или "F" для женского (AYOL)
- pinfl: ровно 14 цифр
- birth_date, issue_date, expiry_date: формат DD.MM.YYYY
- Если поле не читается — оставь пустую строку ""
- Верни ТОЛЬКО JSON, без пояснений и markdown"""


class VLMExtractor:
    """Экстрактор данных паспорта через Qwen Vision API."""

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model = settings.QWEN_MODEL
        self.base_url = settings.QWEN_BASE_URL.rstrip("/")
        self.timeout = settings.VLM_TIMEOUT

        if not self.api_key:
            logger.warning("QWEN_API_KEY not set — VLM extraction will fail")
        else:
            logger.info(f"VLMExtractor initialized: Qwen ({self.model}) @ {self.base_url}")

    def extract(self, image_bytes: bytes) -> Dict[str, Any]:
        empty_result = {
            "first_name": "", "last_name": "", "middle_name": "", "birth_date": "",
            "gender": "", "nationality": "", "passport_number": "", "issue_date": "",
            "expiry_date": "", "issued_by": "", "pinfl": ""
        }

        if not self.api_key:
            logger.error("QWEN_API_KEY is not configured")
            return empty_result

        return self._extract_qwen(image_bytes, empty_result)

    def _compress_image(self, image_bytes: bytes, max_size: int = 1600, quality: int = 90) -> bytes:
        """Сжимает изображение для ускорения отправки в Qwen API."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_size = len(image_bytes)

        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()
            logger.info(f"Image compressed: {original_size/1024:.0f}KB -> {len(compressed)/1024:.0f}KB ({img.size[0]}x{img.size[1]})")
            return compressed

        logger.info(f"Image kept original: {original_size/1024:.0f}KB ({img.size[0]}x{img.size[1]})")
        return image_bytes

    def _extract_qwen(self, image_bytes: bytes, empty_result: Dict[str, Any]) -> Dict[str, Any]:
        # Сжатие изображения
        image_bytes = self._compress_image(image_bytes)
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{image_b64}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SYSTEM_PROMPT},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1024
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending request to Qwen API (attempt {attempt+1}/{max_retries})")
                with httpx.Client(
                    timeout=httpx.Timeout(self.timeout + 60, connect=30.0, read=self.timeout)
                ) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"Qwen response: {content[:300]}")

                    parsed = self._parse_json_response(content)
                    result = self._normalize_fields(parsed)
                    filled = sum(1 for v in result.values() if v)
                    logger.info(f"Extraction success: {filled}/11 fields filled")
                    return result

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error (attempt {attempt+1}): {e.response.status_code} - {e.response.text}")
            except Exception as e:
                logger.error(f"Qwen API error (attempt {attempt+1}): {type(e).__name__}: {e}")

            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # exponential backoff

        return empty_result

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Парсит JSON из ответа модели, убирая markdown и прочий шум."""
        content = content.strip()

        # Убираем markdown code fences
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Попытка распарсить как JSON
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Попытка с заменой кавычек
        try:
            return json.loads(content.replace("'", '"'))
        except json.JSONDecodeError:
            pass

        # Попытка через ast.literal_eval
        try:
            import ast
            return ast.literal_eval(content)
        except Exception:
            pass

        logger.error(f"Failed to parse JSON from: {content[:200]}")
        return {}

    def _normalize_fields(self, raw: Dict[str, Any]) -> Dict[str, str]:
        """Нормализует поля: маппинг альтернативных ключей, очистка значений."""
        result = {
            "first_name": "", "last_name": "", "middle_name": "", "birth_date": "",
            "gender": "", "nationality": "", "passport_number": "", "issue_date": "",
            "expiry_date": "", "issued_by": "", "pinfl": ""
        }

        mapping = {
            "first_name": ["first_name", "given_name", "given_names", "name"],
            "last_name": ["last_name", "surname", "family_name"],
            "middle_name": ["middle_name", "patronymic", "father_name"],
            "birth_date": ["birth_date", "date_of_birth", "dob"],
            "gender": ["gender", "sex"],
            "nationality": ["nationality", "citizenship", "country"],
            "passport_number": ["passport_number", "document_number", "passport_no"],
            "issue_date": ["issue_date", "date_of_issue", "date_issued"],
            "expiry_date": ["expiry_date", "date_of_expiry", "expiration_date"],
            "issued_by": ["issued_by", "issuing_authority", "authority"],
            "pinfl": ["pinfl", "personal_number", "id_number", "jshshir"]
        }

        for field, keys in mapping.items():
            for k in keys:
                if k in raw and raw[k]:
                    val = str(raw[k]).strip()
                    if val and val.lower() not in ("none", "null", "n/a", "unknown"):
                        result[field] = val
                        break

        # Нормализация пола
        g = result["gender"].upper()
        if any(x in g for x in ["M", "ERKAK", "MUZ"]):
            result["gender"] = "M"
        elif any(x in g for x in ["F", "AYOL", "ZN", "Ж"]):
            result["gender"] = "F"

        # Очистка PINFL — только 14 цифр
        pinfl = re.sub(r"\D", "", result["pinfl"])
        result["pinfl"] = pinfl[:14] if len(pinfl) >= 14 else ""

        # Очистка дат — приводим к DD.MM.YYYY
        for date_field in ["birth_date", "issue_date", "expiry_date"]:
            result[date_field] = self._normalize_date(result[date_field])

        return result

    def _normalize_date(self, date_str: str) -> str:
        """Приводит дату к формату DD.MM.YYYY."""
        if not date_str:
            return ""

        # Уже в нужном формате
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", date_str):
            return date_str

        # Формат YYYY-MM-DD или YYYY/MM/DD
        m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", date_str)
        if m:
            return f"{m.group(3).zfill(2)}.{m.group(2).zfill(2)}.{m.group(1)}"

        # Формат DD/MM/YYYY
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
        if m:
            return f"{m.group(1).zfill(2)}.{m.group(2).zfill(2)}.{m.group(3)}"

        # Формат MM/DD/YYYY (US) — если день > 12, значит это месяц
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
        if m and int(m.group(1)) > 12:
            return f"{m.group(2).zfill(2)}.{m.group(1).zfill(2)}.{m.group(3)}"

        return date_str  # Вернём как есть, если не распознали


vlm_extractor = VLMExtractor()
