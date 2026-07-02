"""
Face detection, frame quality validation, and embedding extraction.

Embedding backend: InsightFace buffalo_l (ArcFace, 512-d, L2-normalized).
Detection:         InsightFace built-in detector (same model as fecid app).
"""
import base64
import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger('apps.face_auth')

SHARPNESS_THRESHOLD = 80.0
MIN_FACE_RATIO      = 0.10
MIN_BRIGHTNESS      = 40.0
MAX_BRIGHTNESS      = 230.0

# ── InsightFace singleton ─────────────────────────────────────────────────────

_INSIGHT_MODEL = None


def _get_model():
    global _INSIGHT_MODEL
    if _INSIGHT_MODEL is None:
        from insightface.app import FaceAnalysis
        _INSIGHT_MODEL = FaceAnalysis(
            name='buffalo_l',
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
        )
        _INSIGHT_MODEL.prepare(ctx_id=0, det_size=(320, 320))
    return _INSIGHT_MODEL


# ── Helpers ───────────────────────────────────────────────────────────────────

def decode_frame(b64_frame: str) -> Optional[np.ndarray]:
    """Decode a base64 JPEG/PNG data-URI or raw base64 string to BGR ndarray."""
    try:
        if ',' in b64_frame:
            b64_frame = b64_frame.split(',', 1)[1]
        raw = base64.b64decode(b64_frame)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as exc:
        logger.debug("Frame dekodlashda xatolik: %s", exc)
        return None


def laplacian_variance(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def face_brightness(image: np.ndarray, bbox: tuple) -> float:
    x1, y1, x2, y2 = bbox
    roi  = image[y1:y2, x1:x2]
    if roi.size == 0:
        return 128.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


# ── Quality validation ────────────────────────────────────────────────────────

def validate_frame_quality(image: np.ndarray) -> tuple:
    """
    Check frame quality before enrollment or verification.
    Returns (is_valid: bool, reason_in_uzbek: str).
    """
    if image is None or image.size == 0:
        return False, "Kadr bo'sh"

    sharpness = laplacian_variance(image)
    if sharpness < SHARPNESS_THRESHOLD:
        return False, "Tasvir xiralashgan. Kamerani barqaror ushlab turing."

    model = _get_model()
    faces = model.get(image)

    if len(faces) == 0:
        return False, "Yuz aniqlanmadi. Kameraga to'g'ri qarang."

    if len(faces) > 1:
        return False, "Bir nechta yuz aniqlandi. Faqat siz kadr ichida bo'ling."

    face  = faces[0]
    x1, y1, x2, y2 = face.bbox.astype(int)
    img_w = image.shape[1]
    face_w = x2 - x1

    if face_w / img_w < MIN_FACE_RATIO:
        return False, "Yuz juda kichik. Kameraga yaqinroq turing."

    brightness = face_brightness(image, (x1, y1, x2, y2))
    if brightness < MIN_BRIGHTNESS:
        return False, "Yoritish yetarli emas. Yorqinroq joyga o'ting."
    if brightness > MAX_BRIGHTNESS:
        return False, "Yoritish haddan ziyod. Nurdan uzoqroq turing."

    return True, ""


# ── Embedding extraction ──────────────────────────────────────────────────────

def extract_embedding(image: np.ndarray) -> Optional[list]:
    """
    Extract L2-normalized 512-d ArcFace embedding via InsightFace buffalo_l.
    Returns a list of floats, or None on failure.
    """
    if image is None:
        return None

    try:
        model = _get_model()
        faces = model.get(image)
        if not faces:
            return None
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        emb  = face.embedding.astype(np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.tolist()
    except Exception as exc:
        logger.error("InsightFace embedding xatosi: %s", exc)
        return None


def select_best_frame(frames: list) -> Optional[np.ndarray]:
    """Return the sharpest frame from a list."""
    best, best_score = None, -1.0
    for f in frames:
        if f is None:
            continue
        score = laplacian_variance(f)
        if score > best_score:
            best_score = score
            best       = f
    return best
