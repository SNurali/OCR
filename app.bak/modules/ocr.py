"""OCR module: EasyOCR (primary) → Tesseract fallback chain."""

import cv2
import numpy as np
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class OCREngine:
    """Multi-engine OCR with fallback strategy."""

    def __init__(self):
        self._easyocr = None
        self._easyocr_available = None
        self._tesseract_config = r"--oem 3 --psm 6 -l eng+rus"

    def _init_easyocr(self):
        if self._easyocr is not None:
            return self._easyocr
        try:
            import easyocr

            logger.info("Initializing EasyOCR (en, ru, uzb)...")
            self._easyocr = easyocr.Reader(["en", "ru"], gpu=False, verbose=False)
            self._easyocr_available = True
            logger.info("EasyOCR initialized successfully")
        except Exception as e:
            logger.warning(f"EasyOCR unavailable: {e}")
            self._easyocr = False
            self._easyocr_available = False
        return self._easyocr if self._easyocr is not False else None

    def run_easyocr(self, image: np.ndarray) -> Tuple[str, float, List[Dict]]:
        """Run EasyOCR and return (text, avg_confidence, word_details)."""
        engine = self._init_easyocr()
        if engine is None:
            return "", 0.0, []

        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = engine.readtext(rgb)

            if not results:
                return "", 0.0, []

            lines = []
            confidences = []
            details = []

            for item in results:
                if len(item) == 3:
                    bbox, text, conf = item
                elif len(item) == 2:
                    text, conf = item
                    bbox = None
                else:
                    continue

                if text.strip():
                    lines.append(text.strip())
                    confidences.append(float(conf))
                    details.append({"text": text.strip(), "confidence": float(conf)})

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            text = "\n".join(lines)
            logger.info(f"EasyOCR: {len(details)} regions, confidence={avg_conf:.3f}")
            return text, avg_conf, details

        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return "", 0.0, []

    def run_easyocr_detailed(self, image: np.ndarray) -> Tuple[str, float, List[Dict]]:
        """Run EasyOCR without paragraph merging for better MRZ detection."""
        engine = self._init_easyocr()
        if engine is None:
            return "", 0.0, []

        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = engine.readtext(rgb, paragraph=False)

            if not results:
                return "", 0.0, []

            lines = []
            confidences = []
            details = []

            for bbox, text, conf in results:
                if text.strip():
                    lines.append(text.strip())
                    confidences.append(conf)
                    details.append({"text": text.strip(), "confidence": conf})

            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            text = "\n".join(lines)
            return text, avg_conf, details

        except Exception as e:
            logger.error(f"EasyOCR detailed failed: {e}")
            return "", 0.0, []

    def run_tesseract(self, image: np.ndarray) -> Tuple[str, float, List[Dict]]:
        """Run Tesseract with multiple PSM modes."""
        import pytesseract

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
        )

        all_texts = []
        all_confs = []

        for psm in [6, 4, 3, 11]:
            try:
                data = pytesseract.image_to_data(
                    binary,
                    config=f"--oem 3 --psm {psm} -l eng+rus",
                    output_type=pytesseract.Output.DICT,
                )
                lines = []
                confs = []
                for i, text in enumerate(data["text"]):
                    text = text.strip()
                    conf = data["conf"][i]
                    if text and conf > 0:
                        lines.append(text)
                        confs.append(conf / 100.0)

                if lines:
                    avg = sum(confs) / len(confs)
                    all_texts.append("\n".join(lines))
                    all_confs.append(avg)
            except Exception:
                continue

        if not all_texts:
            return "", 0.0, []

        best_idx = all_confs.index(max(all_confs))
        text = self._deduplicate_lines(all_texts)
        avg_conf = all_confs[best_idx]

        details = [{"text": t, "confidence": avg_conf} for t in text.split("\n") if t]
        logger.info(f"Tesseract: confidence={avg_conf:.3f}")
        return text, avg_conf, details

    def _deduplicate_lines(self, texts: List[str]) -> str:
        """Merge multiple OCR outputs, removing duplicates."""
        all_lines = []
        seen = set()
        for text in texts:
            for line in text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                key = stripped.lower().replace(" ", "")
                if key and key not in seen:
                    seen.add(key)
                    all_lines.append(stripped)
        return "\n".join(all_lines)

    def ocr_full(self, image: np.ndarray) -> Dict:
        """
        Main OCR pipeline:
        1. EasyOCR (primary, with paragraph=True for readability)
        2. If confidence < 0.65 → Tesseract
        3. Merge best results
        """
        easy_text, easy_conf, easy_details = self.run_easyocr(image)

        if easy_conf >= 0.65 and easy_text.strip():
            logger.info(f"EasyOCR sufficient (conf={easy_conf:.3f}), using as primary")
            return {
                "text": easy_text,
                "confidence": easy_conf,
                "engine": "easyocr",
                "details": easy_details,
            }

        tess_text, tess_conf, tess_details = self.run_tesseract(image)

        if tess_text.strip() and tess_conf > easy_conf:
            logger.info(
                f"Tesseract fallback used (conf={tess_conf:.3f} > {easy_conf:.3f})"
            )
            return {
                "text": tess_text,
                "confidence": tess_conf,
                "engine": "tesseract",
                "details": tess_details,
            }

        if easy_text.strip():
            return {
                "text": easy_text,
                "confidence": easy_conf,
                "engine": "easyocr",
                "details": easy_details,
            }

        if tess_text.strip():
            return {
                "text": tess_text,
                "confidence": tess_conf,
                "engine": "tesseract",
                "details": tess_details,
            }

        logger.warning("All OCR engines failed")
        return {
            "text": "",
            "confidence": 0.0,
            "engine": "none",
            "details": [],
        }

    def ocr_mrz(self, image: np.ndarray) -> Tuple[str, float]:
        """Specialized MRZ OCR using Tesseract with aggressive preprocessing."""
        import pytesseract

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        best_text = ""
        best_score = 0

        regions = [
            gray[int(h * 0.85) :, :],
            gray[int(h * 0.75) :, :],
            gray[int(h * 0.65) :, :],
            gray[int(h * 0.55) :, :],
        ]

        for region in regions:
            variants = []
            scaled = cv2.resize(
                region, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC
            )
            variants.append(scaled)

            _, otsu = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants.append(otsu)
            variants.append(255 - otsu)

            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(
                cv2.resize(region, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
            )
            adaptive = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
            )
            variants.append(adaptive)

            for config in [
                r"--oem 3 --psm 6 -l eng",
                r"--oem 3 --psm 4 -l eng",
                r"--oem 3 --psm 11 -l eng",
            ]:
                for img_variant in variants:
                    try:
                        text = pytesseract.image_to_string(
                            img_variant, config=config
                        ).strip()
                        if not text:
                            continue

                        score = self._score_mrz(text)
                        if score > best_score:
                            best_score = score
                            best_text = text

                        if "<<" in text and any(
                            "<<" in line
                            for line in text.split("\n")
                            if len(line.strip()) >= 20
                        ):
                            return text, 0.95

                    except Exception:
                        continue

        confidence = min(best_score / 100.0, 1.0) if best_score > 0 else 0.0
        return best_text, confidence

    def _score_mrz(self, text: str) -> int:
        """Score MRZ text quality."""
        score = 0
        for line in text.split("\n"):
            cleaned = line.strip().upper().replace(" ", "")
            if "<<" in cleaned and len(cleaned) >= 20:
                score += 1000
            if len(cleaned) >= 28:
                valid = sum(
                    1 for c in cleaned if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
                )
                if valid / max(len(cleaned), 1) > 0.8:
                    score += valid
        return score


ocr_engine = OCREngine()
