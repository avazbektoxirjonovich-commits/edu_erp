"""
Passive anti-spoofing for Face ID login verification.

Priority order:
  1. DeepFace built-in Fasnet (MiniFASNetV2 + MiniFASNetV1SE ensemble)
       → DeepFace.extract_faces(..., anti_spoofing=True)
  2. LBP-texture + Fourier-spectrum analysis (OpenCV only, no extra deps)
     — ONLY when FACE_LIVENESS_FAIL_OPEN=True; logged as degraded mode

GATE RULE (enforced in check_passive_liveness):
  A frame passes passive liveness if and only if BOTH:
    (1) DeepFace classifies it as real  → is_real == True
    (2) antispoof_score >= FACE_SPOOF_THRESHOLD  (default 0.7)
  A score alone is not sufficient — Fasnet occasionally scores a spoof above
  the threshold while still setting is_real=False. Both conditions are required.

Settings:
  FACE_PASSIVE_LIVENESS_ENABLED  (default False)
  FACE_SPOOF_THRESHOLD           (default 0.7)
  FACE_LIVENESS_FAIL_OPEN        (default False)
    False → if DeepFace unavailable, FAIL the check (safe default)
    True  → if DeepFace unavailable, fall back to LBP/Fourier (explicit degraded mode)
"""
import logging

import cv2
import numpy as np

logger = logging.getLogger('apps.face_auth')


# ── DeepFace Fasnet (primary) ─────────────────────────────────────────────────

def _deepface_antispoof_result(frame: np.ndarray) -> tuple:
    """
    Run DeepFace's built-in Fasnet on a BGR frame.
    Returns (is_real: bool | None, score: float):
      is_real=None  means model is unavailable or raised an exception
      is_real=True  face classified as live
      is_real=False face classified as spoof
      score: antispoof_score from Fasnet (0.0–1.0), or -1.0 if unavailable
    """
    try:
        from deepface import DeepFace  # type: ignore
        results = DeepFace.extract_faces(
            img_path=frame,
            anti_spoofing=True,
            enforce_detection=False,
            detector_backend='opencv',
        )
        if not results:
            logger.debug("DeepFace anti-spoofing: yuz topilmadi — spoof deb hisoblanadi")
            return False, 0.0

        best    = max(results, key=lambda r: r.get('antispoof_score', 0.0))
        is_real = bool(best.get('is_real', False))
        score   = float(best.get('antispoof_score', 0.0))
        logger.debug("DeepFace Fasnet: is_real=%s score=%.3f", is_real, score)
        return is_real, score

    except ImportError:
        logger.error("DeepFace o'rnatilmagan — passiv liveness MAVJUD EMAS")
        return None, -1.0
    except Exception as exc:
        logger.error("DeepFace anti-spoofing xatosi: %s", exc)
        return None, -1.0


def _deepface_antispoof_score(frame: np.ndarray) -> float:
    """Backward-compatible wrapper — returns just the score (or -1.0 if unavailable)."""
    _, score = _deepface_antispoof_result(frame)
    return score


# ── LBP + Fourier fallback (degraded mode, FAIL_OPEN=True only) ──────────────

def _lbp_entropy(gray: np.ndarray) -> float:
    """Shannon entropy of local binary pattern histogram."""
    h, w    = gray.shape
    lbp_img = np.zeros_like(gray, dtype=np.uint8)
    for dy, dx in [(-1,-1),(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1)]:
        y1 = max(0, -dy); y2 = min(h, h-dy)
        x1 = max(0, -dx); x2 = min(w, w-dx)
        sy1 = max(0, dy); sy2 = min(h, h+dy)
        sx1 = max(0, dx); sx2 = min(w, w+dx)
        lbp_img[sy1:sy2, sx1:sx2] += (
            gray[sy1:sy2, sx1:sx2] >= gray[y1:y2, x1:x2]
        ).astype(np.uint8)
    hist, _ = np.histogram(lbp_img.ravel(), bins=256, range=(0, 256))
    hist    = hist[hist > 0].astype(np.float64)
    hist   /= hist.sum()
    return float(-np.sum(hist * np.log2(hist)))


def _fourier_high_freq_ratio(gray: np.ndarray) -> float:
    """Ratio of high-frequency energy — periodic screen/print artifacts show up here."""
    f      = np.fft.fft2(gray.astype(np.float32))
    mag    = np.abs(np.fft.fftshift(f))
    h, w   = mag.shape
    cy, cx = h // 2, w // 2
    r_in   = min(h, w) // 6
    r_out  = min(h, w) // 2
    Y, X   = np.ogrid[:h, :w]
    dist   = np.sqrt((Y - cy) ** 2 + (X - cx) ** 2)
    high_e = float(np.sum(mag[(dist > r_in) & (dist <= r_out)]))
    tot_e  = float(np.sum(mag[dist <= r_in])) + high_e
    return high_e / tot_e if tot_e > 0 else 0.0


def _lbp_fourier_score(frame: np.ndarray) -> float:
    """Combined LBP + Fourier texture score (0.0–1.0). Degraded fallback only."""
    try:
        resized   = cv2.resize(frame, (64, 64))
        gray      = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        ent_score = min(1.0, max(0.0, (_lbp_entropy(gray) - 3.0) / 4.0))
        hf_score  = min(1.0, max(0.0, (_fourier_high_freq_ratio(gray) - 0.10) / 0.40))
        return 0.6 * ent_score + 0.4 * hf_score
    except Exception as exc:
        logger.warning("LBP/Fourier xatosi: %s", exc)
        return 0.0   # fail closed in fallback too


# ── Public API ────────────────────────────────────────────────────────────────

def passive_liveness_score(frame: np.ndarray) -> float:
    """
    Return a passive liveness score for a single BGR frame (backward-compat).
    Tries DeepFace first; falls back to LBP/Fourier if unavailable.
    Used directly only in integration tests / calibration — not the gate.
    The gate is check_passive_liveness() which enforces is_real AND score.
    """
    is_real, score = _deepface_antispoof_result(frame)
    if is_real is not None:
        return score
    return _lbp_fourier_score(frame)


def check_passive_liveness(frames: list) -> tuple:
    """
    Run passive liveness on up to 3 sampled frames.
    Returns (passed: bool, score: float, reason_uzbek: str).

    Gate rule: BOTH conditions must hold for every sampled frame's mean:
      (1) is_real == True  (DeepFace Fasnet classification)
      (2) mean antispoof_score >= FACE_SPOOF_THRESHOLD

    When DeepFace is unavailable:
      FACE_LIVENESS_FAIL_OPEN=False (default) → FAIL, steer to OTP
      FACE_LIVENESS_FAIL_OPEN=True            → degrade to LBP/Fourier (logged)
    """
    from django.conf import settings
    enabled   = getattr(settings, 'FACE_PASSIVE_LIVENESS_ENABLED', False)
    threshold = float(getattr(settings, 'FACE_SPOOF_THRESHOLD', 0.7))
    fail_open = getattr(settings, 'FACE_LIVENESS_FAIL_OPEN', False)

    if not enabled:
        return True, 1.0, ""

    valid = [f for f in frames if f is not None]
    if not valid:
        return True, 1.0, ""

    step    = max(1, len(valid) // 3)
    sampled = valid[::step][:3]

    scores   = []
    all_real = True

    for frame in sampled:
        is_real, score = _deepface_antispoof_result(frame)

        if is_real is None:
            # DeepFace unavailable
            if fail_open:
                logger.warning(
                    "DeepFace mavjud emas, FACE_LIVENESS_FAIL_OPEN=True — "
                    "LBP/Fourier degraded mode ishlatilmoqda"
                )
                score    = _lbp_fourier_score(frame)
                is_real  = (score >= threshold)
            else:
                logger.error(
                    "XAVFSIZLIK: Passiv liveness modeli MAVJUD EMAS. "
                    "FACE_LIVENESS_FAIL_OPEN=False — fail-closed. "
                    "Foydalanuvchi OTP zaxiraga yo'naltiriladi."
                )
                return (
                    False, -1.0,
                    "Yuz tekshiruvi vaqtincha mavjud emas. Zaxira kod orqali kiring.",
                )

        if not is_real:
            all_real = False
        scores.append(score)

    mean = float(np.mean(scores)) if scores else 0.0

    logger.info(
        "Passiv liveness ballar: %s → o'rtacha=%.3f all_real=%s chegara=%.2f",
        [f"{s:.3f}" for s in scores], mean, all_real, threshold,
    )

    # Gate: BOTH is_real==True for every frame AND mean score >= threshold
    if not all_real:
        return False, mean, f"Passiv jonlilik: yuz soxta deb topildi (is_real=False)"
    if mean < threshold:
        return False, mean, f"Passiv jonlilik: ball yetarli emas (bal={mean:.2f}, chegara={threshold:.2f})"

    return True, mean, ""
