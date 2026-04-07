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

SYSTEM_PROMPT = """Extract passport data and return ONLY valid JSON:
{
  "first_name":"","last_name":"","middle_name":"",
  "birth_date":"DD.MM.YYYY","gender":"M/F","nationality":"",
  "passport_number":"","issue_date":"DD.MM.YYYY","expiry_date":"DD.MM.YYYY",
  "issued_by":"","pinfl":"14 digits"
}
Use empty string if unreadable. Return ONLY JSON."""


class VLMExtractor:
    """VLM-экстрактор (Groq / Qwen)."""

    def __init__(self):
        self.provider = settings.VLM_PROVIDER.lower()
        self.timeout = settings.VLM_TIMEOUT

        if self.provider == 'groq':
            self.api_key = settings.GROQ_API_KEY
            self.model = settings.GROQ_MODEL
            self.base_url = settings.GROQ_BASE_URL
            logger.info(f"VLMExtractor initialized: Groq ({self.model})")
        elif self.provider == 'qwen':
            self.api_key = settings.QWEN_API_KEY
            self.model = settings.QWEN_MODEL
            self.base_url = settings.QWEN_BASE_URL
            logger.info(f"VLMExtractor initialized: Qwen ({self.model})")
        elif self.provider == 'ollama':
            self.api_key = settings.OLLAMA_API_KEY
            self.model = settings.OLLAMA_MODEL
            self.base_url = settings.OLLAMA_BASE_URL
            logger.info(f"VLMExtractor initialized: Ollama ({self.model})")
        else:
            logger.error(f"Unknown VLM provider: {self.provider}")

    def extract(self, image_bytes: bytes) -> Dict[str, Any]:
        empty_result = {
            "first_name": "", "last_name": "", "middle_name": "", "birth_date": "",
            "gender": "", "nationality": "", "passport_number": "", "issue_date": "",
            "expiry_date": "", "issued_by": "", "pinfl": ""
        }

        if not settings.VLM_ENABLED:
            return empty_result

        if self.provider in ['groq', 'qwen', 'ollama']:
            return self._extract_openai_compatible(image_bytes, empty_result)
        else:
            logger.error(f"Provider {self.provider} not implemented")
            return empty_result

    def _compress_image(self, image_bytes: bytes, max_size: int = 1600, quality: int = 90) -> bytes:
        """Сжимает изображение для ускорения отправки в VLM."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_size = len(image_bytes)
        # Не сжимаем маленькие изображения
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

    def _extract_openai_compatible(self, image_bytes: bytes, empty_result: Dict[str, Any]) -> Dict[str, Any]:
        # Сжатие изображения для ускорения
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
            "max_tokens": 512
        }

        headers = {"Content-Type": "application/json"}
        # Ollama не требует API ключа
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        max_retries = 1
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=httpx.Timeout(self.timeout + 60, connect=30.0, read=self.timeout)) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    logger.info(f"Response: {content[:200]}...")
                    parsed = self._parse_json_response(content)
                    result = self._normalize_fields(parsed)
                    filled = sum(1 for v in result.values() if v)
                    logger.info(f"Extraction success: {filled}/11 fields")
                    return result
            except Exception as e:
                logger.error(f"VLM error (attempt {attempt+1}): {e}")
                if attempt == max_retries - 1:
                    return empty_result
        return empty_result

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        content = content.strip()
        if content.startswith("```json"): content = content[7:]
        elif content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try: return json.loads(content.replace("'", '"'))
            except: pass
            try:
                import ast
                return ast.literal_eval(content)
            except: pass
            return {}

    def _normalize_fields(self, raw: Dict[str, Any]) -> Dict[str, str]:
        result = {k: "" for k in ["first_name", "last_name", "middle_name", "birth_date", "gender", "nationality", "passport_number", "issue_date", "expiry_date", "issued_by", "pinfl"]}
        
        mapping = {
            "first_name": ["first_name", "given_names", "name"],
            "last_name": ["last_name", "surname"],
            "middle_name": ["middle_name", "patronymic"],
            "birth_date": ["birth_date", "date_of_birth"],
            "gender": ["gender", "sex"],
            "nationality": ["nationality", "citizenship"],
            "passport_number": ["passport_number", "document_number"],
            "issue_date": ["issue_date", "date_of_issue"],
            "expiry_date": ["expiry_date", "date_of_expiry"],
            "issued_by": ["issued_by", "issuing_authority"],
            "pinfl": ["pinfl", "personal_number"]
        }

        for field, keys in mapping.items():
            for k in keys:
                if k in raw and raw[k]:
                    val = str(raw[k]).strip()
                    if val and val.lower() not in ("none", "null", "n/a"):
                        result[field] = val
                        break

        # Normalizations
        g = result["gender"].upper()
        if "M" in g or "ERKAK" in g: result["gender"] = "M"
        elif "F" in g or "AYOL" in g: result["gender"] = "F"

        pinfl = re.sub(r"\D", "", result["pinfl"])
        result["pinfl"] = pinfl[:14] if len(pinfl) >= 14 else ""

        return result


vlm_extractor = VLMExtractor()
