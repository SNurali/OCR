import cv2
import numpy as np
from typing import Dict
from app.config import settings


class AntiFraudChecker:
    """Anti-fraud модуль для детекции поддельных документов."""

    def check(self, image: np.ndarray) -> Dict:
        results = {
            "blur": self._detect_blur(image),
            "glare": self._detect_glare(image),
            "moire": self._detect_moire(image),
            "copy_detection": self._detect_copy(image),
            "edge_analysis": self._analyze_edges(image),
            "color_consistency": self._check_color_consistency(image),
        }

        weighted_score = (
            results["blur"]["score"] * 0.20
            + results["glare"]["score"] * 0.15
            + results["moire"]["score"] * 0.20
            + results["copy_detection"]["score"] * 0.20
            + results["edge_analysis"]["score"] * 0.15
            + results["color_consistency"]["score"] * 0.10
        )

        results["overall_score"] = round(weighted_score, 3)
        results["blocked"] = weighted_score < 0.35
        results["risk_level"] = self._risk_level(weighted_score)

        return results

    def _detect_blur(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        threshold = settings.ANTI_FRAUD_BLUR_THRESHOLD
        if laplacian_var > threshold * 1.5:
            score = 1.0
        elif laplacian_var > threshold:
            score = 0.7
        elif laplacian_var > threshold * 0.5:
            score = 0.4
        else:
            score = 0.1

        return {
            "score": score,
            "laplacian_variance": round(laplacian_var, 2),
            "threshold": threshold,
            "passed": laplacian_var > threshold * 0.5,
        }

    def _detect_glare(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        threshold = settings.ANTI_FRAUD_GLARE_THRESHOLD
        bright_pixels = np.sum(gray > threshold)
        total_pixels = h * w
        glare_ratio = bright_pixels / total_pixels

        if glare_ratio < 0.02:
            score = 1.0
        elif glare_ratio < 0.05:
            score = 0.7
        elif glare_ratio < 0.10:
            score = 0.4
        else:
            score = 0.1

        return {
            "score": score,
            "glare_ratio": round(glare_ratio, 4),
            "bright_pixel_percentage": round(glare_ratio * 100, 2),
            "passed": glare_ratio < 0.10,
        }

    def _detect_moire(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift)

        h, w = magnitude.shape
        center_h, center_w = h // 2, w // 2

        mask_radius = min(h, w) // 8
        y, x = np.ogrid[:h, :w]
        mask = (x - center_w) ** 2 + (y - center_h) ** 2 > mask_radius**2
        magnitude[mask] = 0

        total_energy = np.sum(magnitude)
        if total_energy == 0:
            return {"score": 0.5, "moire_energy": 0.0, "passed": True}

        high_freq_energy = np.sum(magnitude) / total_energy
        moire_ratio = high_freq_energy

        threshold = settings.ANTI_FRAUD_MOIRE_THRESHOLD
        if moire_ratio < threshold:
            score = 1.0
        elif moire_ratio < threshold * 2:
            score = 0.6
        else:
            score = 0.2

        return {
            "score": score,
            "moire_ratio": round(moire_ratio, 4),
            "passed": moire_ratio < threshold * 2,
        }

    def _detect_copy(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        contrast = np.std(l_channel)

        edge_score = 1.0 if 0.03 < edge_density < 0.4 else 0.3
        contrast_score = 1.0 if contrast > 30 else (0.6 if contrast > 15 else 0.2)

        score = (edge_score + contrast_score) / 2

        return {
            "score": score,
            "edge_density": round(edge_density, 4),
            "contrast": round(contrast, 2),
            "passed": score > 0.4,
        }

    def _analyze_edges(self, image: np.ndarray) -> Dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        edges = cv2.Canny(gray, 50, 150)

        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        document_contours = [c for c in contours if cv2.contourArea(c) > (h * w * 0.1)]

        has_document = len(document_contours) > 0

        straight_lines = 0
        for contour in document_contours:
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            if len(approx) == 4:
                straight_lines += 1

        score = 1.0 if has_document and straight_lines > 0 else 0.5

        return {
            "score": score,
            "document_detected": has_document,
            "straight_edges": straight_lines,
            "total_contours": len(contours),
            "passed": has_document,
        }

    def _check_color_consistency(self, image: np.ndarray) -> Dict:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        h, w = hsv.shape[:2]
        regions = [
            hsv[0 : h // 2, 0 : w // 2],
            hsv[0 : h // 2, w // 2 : w],
            hsv[h // 2 : h, 0 : w // 2],
            hsv[h // 2 : h, w // 2 : w],
        ]

        saturations = [np.mean(r[:, :, 1]) for r in regions]
        values = [np.mean(r[:, :, 2]) for r in regions]

        sat_std = np.std(saturations)
        val_std = np.std(values)

        consistency = 1.0 / (1.0 + sat_std / 20.0 + val_std / 30.0)
        score = min(consistency, 1.0)

        return {
            "score": round(score, 3),
            "saturation_std": round(sat_std, 2),
            "value_std": round(val_std, 2),
            "passed": score > 0.4,
        }

    def _risk_level(self, score: float) -> str:
        if score >= 0.7:
            return "low"
        elif score >= 0.4:
            return "medium"
        else:
            return "high"


anti_fraud_checker = AntiFraudChecker()
