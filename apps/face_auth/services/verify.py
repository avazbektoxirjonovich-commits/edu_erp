"""
Face login verification: single-frame identity check via InsightFace.

Flow: decode frame → extract InsightFace embedding → cosine similarity vs stored embedding.
Liveness challenge removed — simple snapshot comparison (same as fecid app).
"""
import logging

import numpy as np

logger = logging.getLogger('apps.face_auth')


def cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _threshold() -> float:
    from django.conf import settings
    return float(getattr(settings, 'FACE_COSINE_THRESHOLD', 0.45))


def verify_login_face(user, frames_b64: list, challenge_action: str = '') -> tuple:
    """
    Verify identity: best frame → InsightFace embedding → cosine similarity.

    Returns:
        (passed: bool, liveness_passed: bool, identity_matched: bool, error_msg: str | None)
    """
    from apps.face_auth.services.embeddings import decode_frame, select_best_frame, extract_embedding
    from apps.face_auth.crypto import decrypt_embedding

    frames = [decode_frame(f) for f in frames_b64]
    frames = [f for f in frames if f is not None]

    if not frames:
        return False, False, False, "Kadr topilmadi"

    try:
        face_profile = user.face_profile
    except Exception:
        return False, False, False, "Yuz profili topilmadi"

    if not face_profile.is_enrolled:
        return False, False, False, "Yuz ro'yxatga olinmagan"

    ref_embedding = decrypt_embedding(face_profile.encrypted_embedding)
    if ref_embedding is None:
        return False, False, False, "Yuz ma'lumotlarini o'qishda xatolik"

    best_frame = select_best_frame(frames)
    if best_frame is None:
        return False, False, False, "Kadr topilmadi"

    live_embedding = extract_embedding(best_frame)
    if live_embedding is None:
        return False, False, False, "Yuz aniqlanmadi. Kameraga to'g'ri qarang."

    sim       = cosine_similarity(live_embedding, ref_embedding)
    threshold = _threshold()

    logger.info("Yuz o'xshashligi: user=%s similarity=%.4f threshold=%.4f", user.pk, sim, threshold)

    if sim < threshold:
        return False, True, False, "Yuz mos kelmadi. Qayta urinib ko'ring."

    return True, True, True, None
