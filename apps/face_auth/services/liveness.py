"""
Liveness detection via MediaPipe Face Mesh.

Random challenge generation + server-side frame action verification.
Supported actions: blink, blink_twice, smile, turn_left, turn_right.

Anti-spoofing: inter-frame motion check ensures frames are not from a
static image or pre-recorded video replay.
"""
import logging
import pathlib
import random
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger('apps.face_auth')

# ── Challenge catalogue ───────────────────────────────────────────────────────

CHALLENGES: list[str] = ['blink', 'blink_twice', 'smile', 'turn_left', 'turn_right']

CHALLENGE_LABELS: dict[str, str] = {
    'blink':       "Ko'zingizni bir marta yuming",
    'blink_twice': "Ko'zingizni ikki marta yuming",
    'smile':       "Jilmaying",
    'turn_left':   "Boshingizni chapga burting",
    'turn_right':  "Boshingizni o'ngga burting",
}


def generate_challenge() -> dict:
    """Pick a random liveness action. Returns {'action': str, 'label': str}."""
    action = random.choice(CHALLENGES)
    return {'action': action, 'label': CHALLENGE_LABELS[action]}


# ── MediaPipe landmark indices (Face Mesh 468-point model) ────────────────────
# Left eye:  P1=33, P2=160, P3=158, P4=133, P5=153, P6=144
# Right eye: P1=362, P2=385, P3=387, P4=263, P5=373, P6=380

LEFT_EYE_IDX  = [33,  160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

MOUTH_CORNER_L = 61
MOUTH_CORNER_R = 291
FACE_OUTER_L   = 234   # outer-left cheek boundary
FACE_OUTER_R   = 454   # outer-right cheek boundary
NOSE_TIP       = 4

EAR_CLOSE_THRESHOLD = 0.22   # EAR below this → eye closed
SMILE_WIDTH_RATIO   = 0.46   # mouth_w / face_w above this → smile
YAW_DISPLACEMENT    = 0.10   # nose-x deviation from face-center → head turned
MIN_SMILE_FRAMES    = 4      # sustained smile frames required
MIN_TURN_FRAMES     = 4      # sustained turn frames required


# ── Internal helpers ──────────────────────────────────────────────────────────

def _euclidean(p1, p2) -> float:
    return float(((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2) ** 0.5)


def _ear(lm, indices: list) -> float:
    """Eye Aspect Ratio from 6 MediaPipe landmark points."""
    p  = [lm.landmark[i] for i in indices]
    v1 = _euclidean(p[1], p[5])
    v2 = _euclidean(p[2], p[4])
    h  = _euclidean(p[0], p[3])
    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0


def _get_landmarks(frame: np.ndarray, face_mesh):
    """Run MediaPipe on a BGR frame; return the first face landmark set or None."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    res = face_mesh.process(rgb)
    if res.multi_face_landmarks:
        return res.multi_face_landmarks[0]
    return None


def _task_model_path() -> pathlib.Path:
    """
    Return the face_landmarker.task model path.
    Configurable via FACE_LANDMARKER_MODEL env var or Django setting;
    falls back to the bundled path in models_weights/.
    """
    import os
    from django.conf import settings as djsettings
    custom = (
        os.environ.get('FACE_LANDMARKER_MODEL', '')
        or getattr(djsettings, 'FACE_LANDMARKER_MODEL', '')
    )
    if custom:
        return pathlib.Path(custom)
    return pathlib.Path(__file__).resolve().parent.parent / 'models_weights' / 'face_landmarker.task'


class _LandmarkResult:
    """Thin wrapper that mirrors the old mp.solutions.face_mesh result interface."""
    def __init__(self, landmarks_list):
        self.multi_face_landmarks = landmarks_list


class _FaceMeshCompat:
    """
    Adapter for mediapipe 0.10+ tasks API that exposes the same interface as the
    old mp.solutions.face_mesh.FaceMesh — so all callers need no changes.
    """
    def __init__(self, landmarker):
        self._landmarker = landmarker

    def process(self, rgb_frame: np.ndarray):
        import mediapipe as mp
        mp_img  = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result  = self._landmarker.detect(mp_img)
        if not result.face_landmarks:
            return _LandmarkResult(None)
        # Wrap each landmark set in an object with a .landmark attribute
        wrapped = []
        for face_lm_list in result.face_landmarks:
            wrapped.append(_LandmarkWrapper(face_lm_list))
        return _LandmarkResult(wrapped)

    def close(self):
        try:
            self._landmarker.close()
        except Exception:
            pass


class _LandmarkWrapper:
    """Wraps a list of NormalizedLandmark objects to support dict-style access lm.landmark[i]."""
    def __init__(self, lm_list):
        self._list = lm_list

    @property
    def landmark(self):
        return self._list   # already indexable


def _build_face_mesh():
    """
    Build a face mesh processor.
    Supports mediapipe 0.10+ (tasks API with FaceLandmarker) and older 0.9.x
    (solutions API). Falls back gracefully.
    """
    import mediapipe as mp

    # Try new tasks API (mediapipe >= 0.10)
    try:
        from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
        from mediapipe.tasks.python import BaseOptions

        task_path = _task_model_path()
        if not task_path.exists():
            logger.warning(
                "FaceLandmarker model topilmadi: %s. "
                "FACE_LANDMARKER_MODEL env o'zgaruvchisi bilan sozlang yoki "
                "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
                "face_landmarker/float16/1/face_landmarker.task dan yuklab oling. "
                "MediaPipe-ga bog'liq tekshiruvlar o'tkazib yuboriladi.",
                task_path,
            )
            raise FileNotFoundError(str(task_path))

        opts = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(task_path)),
            num_faces=1,
        )
        landmarker = FaceLandmarker.create_from_options(opts)
        return _FaceMeshCompat(landmarker)
    except FileNotFoundError:
        pass   # fall through to solutions
    except Exception as exc:
        logger.warning("FaceLandmarker tasks API ishlamadi (%s), solutions sinab ko'rilmoqda", exc)

    # Try old solutions API (mediapipe < 0.10)
    try:
        return mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
        )
    except AttributeError:
        raise ImportError("mediapipe solutions API topilmadi va tasks model ham mavjud emas")


# ── Anti-spoofing: motion check ───────────────────────────────────────────────

def frames_have_motion(frames: list) -> bool:
    """
    Return True if consecutive frames differ enough to indicate live video.
    A static photograph produces zero inter-frame difference.
    """
    if len(frames) < 3:
        return False
    grays = []
    for f in frames:
        if f is not None:
            grays.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
    if len(grays) < 3:
        return False
    diffs = [np.mean(np.abs(grays[i] - grays[i - 1])) for i in range(1, len(grays))]
    return float(np.mean(diffs)) > 0.5


# ── Per-action detectors ──────────────────────────────────────────────────────

def _detect_blink(frames: list, face_mesh, required: int = 1) -> bool:
    """Count EAR dips below threshold; require at least `required` complete blinks."""
    ears: list = []
    for f in frames:
        lm = _get_landmarks(f, face_mesh)
        if lm:
            avg = (_ear(lm, LEFT_EYE_IDX) + _ear(lm, RIGHT_EYE_IDX)) / 2.0
            ears.append(avg)
        else:
            ears.append(None)

    dip_count, in_dip = 0, False
    for e in ears:
        if e is None:
            continue
        if e < EAR_CLOSE_THRESHOLD and not in_dip:
            in_dip = True
        elif e >= EAR_CLOSE_THRESHOLD and in_dip:
            dip_count += 1
            in_dip     = False
    if in_dip:
        dip_count += 1
    return dip_count >= required


def _detect_smile(frames: list, face_mesh) -> bool:
    """Check that mouth width / face width ratio exceeds threshold in enough frames."""
    wide_count = 0
    for f in frames:
        lm = _get_landmarks(f, face_mesh)
        if lm:
            ml = lm.landmark[MOUTH_CORNER_L]
            mr = lm.landmark[MOUTH_CORNER_R]
            fl = lm.landmark[FACE_OUTER_L]
            fr = lm.landmark[FACE_OUTER_R]
            mouth_w = _euclidean(ml, mr)
            face_w  = _euclidean(fl, fr)
            if face_w > 0 and mouth_w / face_w > SMILE_WIDTH_RATIO:
                wide_count += 1
    return wide_count >= MIN_SMILE_FRAMES


def _detect_head_turn(frames: list, face_mesh, direction: str) -> bool:
    """Check that the nose-tip is displaced from face-centre in the given direction."""
    hit_count = 0
    for f in frames:
        lm = _get_landmarks(f, face_mesh)
        if lm:
            nose   = lm.landmark[NOSE_TIP]
            fl     = lm.landmark[FACE_OUTER_L]
            fr     = lm.landmark[FACE_OUTER_R]
            centre = (fl.x + fr.x) / 2.0
            disp   = nose.x - centre
            if direction == 'turn_left'  and disp < -YAW_DISPLACEMENT:
                hit_count += 1
            elif direction == 'turn_right' and disp >  YAW_DISPLACEMENT:
                hit_count += 1
    return hit_count >= MIN_TURN_FRAMES


# ── Public API ────────────────────────────────────────────────────────────────

_OTP_REDIRECT_MSG = (
    "Yuz tekshiruvi vaqtincha mavjud emas. "
    "Zaxira kod orqali kiring."
)


def _fail_open() -> bool:
    """Return FACE_LIVENESS_FAIL_OPEN setting (default False = fail-CLOSED)."""
    from django.conf import settings
    return bool(getattr(settings, 'FACE_LIVENESS_FAIL_OPEN', False))


def verify_liveness(frames: list, challenge_action: str) -> tuple:
    """
    Verify liveness with three independent layers:
      1. Motion check   — inter-frame pixel diff (anti static-image replay)
      2. Passive model  — DeepFace Fasnet (is_real AND score >= threshold)
      3. Active challenge — MediaPipe landmark action detection

    Returns (passed: bool, uzbek_reason: str).

    Fail-CLOSED behaviour (FACE_LIVENESS_FAIL_OPEN=False, the safe default):
      If any required component (passive model or MediaPipe model file) is
      unavailable, verification FAILS and the user is steered to OTP.
      An ERROR is logged so operators notice the outage.

    Fail-OPEN behaviour (FACE_LIVENESS_FAIL_OPEN=True, explicit degraded mode):
      Missing models are skipped with a WARNING; only available layers run.
      Use only in controlled environments where the camera feed is trusted.
    """
    if not frames:
        return False, "Kadrlar topilmadi"

    # ── Layer 1: motion (always required; no degradation) ────────────────────
    if not frames_have_motion(frames):
        return False, "Tirik odam aniqlanmadi (harakatsiz tasvir)"

    # ── Layer 2: passive liveness (DeepFace Fasnet gate) ─────────────────────
    # check_passive_liveness() itself respects FACE_LIVENESS_FAIL_OPEN:
    #   - FAIL_OPEN=False + model unavailable  → returns (False, -1.0, OTP msg)
    #   - FAIL_OPEN=True  + model unavailable  → degrades to LBP/Fourier
    # Here we additionally catch unexpected exceptions in the layer itself.
    try:
        from apps.face_auth.services.passive_liveness import check_passive_liveness
        pl_passed, pl_score, pl_reason = check_passive_liveness(frames)
        if not pl_passed:
            return False, pl_reason
    except Exception as exc:
        if _fail_open():
            logger.warning(
                "Passiv jonlilik tekshiruvida kutilmagan xatolik "
                "(FACE_LIVENESS_FAIL_OPEN=True — o'tkazib yuborildi): %s", exc,
            )
        else:
            logger.error(
                "XAVFSIZLIK: Passiv jonlilik moduli ishlamadi "
                "(FACE_LIVENESS_FAIL_OPEN=False — fail-closed): %s", exc,
            )
            return False, _OTP_REDIRECT_MSG

    # ── Layer 3: active challenge (MediaPipe) ─────────────────────────────────
    try:
        face_mesh = _build_face_mesh()
        try:
            if challenge_action == 'blink':
                passed = _detect_blink(frames, face_mesh, required=1)
            elif challenge_action == 'blink_twice':
                passed = _detect_blink(frames, face_mesh, required=2)
            elif challenge_action == 'smile':
                passed = _detect_smile(frames, face_mesh)
            elif challenge_action == 'turn_left':
                passed = _detect_head_turn(frames, face_mesh, 'turn_left')
            elif challenge_action == 'turn_right':
                passed = _detect_head_turn(frames, face_mesh, 'turn_right')
            else:
                return False, "Noma'lum vazifa"
        finally:
            face_mesh.close()

        if passed:
            return True, ""
        return False, f"Vazifa bajarilmadi: {CHALLENGE_LABELS.get(challenge_action, challenge_action)}"

    except ImportError as exc:
        # MediaPipe model file missing
        if _fail_open():
            logger.warning(
                "MediaPipe modeli mavjud emas (FACE_LIVENESS_FAIL_OPEN=True — "
                "faqat harakat tekshiruvi qilinmoqda): %s", exc,
            )
            return True, ""
        else:
            logger.error(
                "XAVFSIZLIK: MediaPipe modeli MAVJUD EMAS — fail-closed "
                "(FACE_LIVENESS_FAIL_OPEN=False). Foydalanuvchi OTP'ga yo'naltiriladi. "
                "Xato: %s", exc,
            )
            return False, _OTP_REDIRECT_MSG

    except Exception as exc:
        logger.error("Jonlilik tekshiruvida xatolik: %s", exc)
        return False, "Tekshiruvda ichki xatolik yuz berdi"
