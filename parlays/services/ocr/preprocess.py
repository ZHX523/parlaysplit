"""OpenCV preprocessing for mobile bet slip screenshots."""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def load_rgb(image_bytes: bytes) -> np.ndarray:
    pil = Image.open(BytesIO(image_bytes))
    pil = pil.convert("RGB")
    return np.array(pil)


def preprocess_for_ocr(image_bytes: bytes) -> np.ndarray:
    """
    Grayscale pipeline: contrast, denoise, sharpen, adaptive threshold.
    Returns single-channel uint8 image for Tesseract.
    """
    rgb = load_rgb(image_bytes)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    gray = cv2.fastNlMeansDenoising(gray, h=8, templateWindowSize=7, searchWindowSize=21)

    pil = Image.fromarray(gray)
    pil = pil.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(pil)
    pil = enhancer.enhance(1.35)
    gray = np.array(pil)

    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        8,
    )

    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(thresh, -1, kernel)
    return sharpened


def preprocess_color_preserve(image_bytes: bytes) -> np.ndarray:
    """Lighter preprocessing that keeps color (useful for blue FanDuel headers)."""
    rgb = load_rgb(image_bytes)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a, b))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
