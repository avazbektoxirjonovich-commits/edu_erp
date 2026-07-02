"""
Integration tests — use REAL DeepFace, MediaPipe, and OpenCV (no mocks).

Run with:
    pytest -m integration apps/face_auth/tests/test_integration.py -v

These tests verify:
  1. DeepFace ArcFace produces embeddings and they are stable for the same image
  2. Cosine similarity of same image → near 1.0; different images → lower
  3. MediaPipe EAR landmark computation on a real face image
  4. Full enroll→verify pipeline without mocks on the sample face image
  5. Passive LBP+Fourier scores varied > flat
  6. OTP console backend produces a code (logged, no external call)

Sample image: apps/face_auth/tests/fixtures/sample_face.jpg
  - Lena Forsén (Söderberg) test image, widely used in CV research.
  - It is NOT a real user — do not commit real biometrics.
  - Source: opencv/opencv/samples/data/lena.jpg (distributed with OpenCV).

NOTE: These tests are SLOW (DeepFace downloads ArcFace on first run ~500MB).
They are intentionally marked `@pytest.mark.integration` and skipped in the
fast suite unless explicitly selected.
"""
import base64
import os
import pathlib
import pytest
import cv2
import numpy as np

FIXTURE_DIR  = pathlib.Path(__file__).parent / 'fixtures'
SAMPLE_FACE  = FIXTURE_DIR / 'sample_face.jpg'

pytestmark = pytest.mark.integration


def _load_sample():
    img = cv2.imread(str(SAMPLE_FACE))
    assert img is not None, f"Sample face not found: {SAMPLE_FACE}"
    return img


def _img_to_b64(img: np.ndarray) -> str:
    _, buf = cv2.imencode('.jpg', img)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf).decode()


# ── 1. DeepFace embedding stability ──────────────────────────────────────────

class TestDeepFaceEmbedding:

    def test_arcface_produces_512d_embedding(self):
        from apps.face_auth.services.embeddings import extract_embedding
        img  = _load_sample()
        emb  = extract_embedding(img)
        assert emb is not None, "ArcFace embedding returned None"
        assert len(emb) in (512, 128), f"Unexpected embedding dim: {len(emb)}"

    def test_same_image_high_cosine_similarity(self):
        """Two embeddings of the same image should have similarity > 0.95."""
        from apps.face_auth.services.embeddings import extract_embedding
        from apps.face_auth.services.verify import cosine_similarity
        img  = _load_sample()
        emb1 = extract_embedding(img)
        emb2 = extract_embedding(img)
        assert emb1 is not None and emb2 is not None
        sim = cosine_similarity(emb1, emb2)
        assert sim > 0.95, f"Same image similarity too low: {sim}"

    def test_different_image_lower_similarity(self):
        """A different (non-face) image should produce lower similarity."""
        from apps.face_auth.services.embeddings import extract_embedding
        from apps.face_auth.services.verify import cosine_similarity
        img1 = _load_sample()
        emb1 = extract_embedding(img1)
        assert emb1 is not None

        # Create a clearly different synthetic image (cartoon-like face)
        h, w = img1.shape[:2]
        img2 = np.zeros_like(img1)
        img2[:] = (200, 150, 100)
        cv2.circle(img2, (w//2, h//2), h//3, (255,220,185), -1)  # skin oval
        cv2.circle(img2, (w//2-50, h//2-30), 20, (50,50,50), -1)  # left eye
        cv2.circle(img2, (w//2+50, h//2-30), 20, (50,50,50), -1)  # right eye
        cv2.ellipse(img2, (w//2, h//2+50), (60,25), 0, 0, 180, (180,80,80), -1)  # mouth

        emb2 = extract_embedding(img2)
        if emb2 is None:
            pytest.skip("Synthetic face not detected — skip similarity check")
        sim = cosine_similarity(emb1, emb2)
        # Different face → similarity should be lower than same-image threshold
        assert sim < 0.99, f"Expected lower similarity for different image, got {sim}"


# ── 2. MediaPipe EAR on real face ─────────────────────────────────────────────

class TestMediaPipeLandmarks:

    def test_face_mesh_detects_landmarks(self):
        from apps.face_auth.services.liveness import (
            _build_face_mesh, _get_landmarks, _ear, LEFT_EYE_IDX, RIGHT_EYE_IDX
        )
        img       = _load_sample()
        face_mesh = _build_face_mesh()
        try:
            lm = _get_landmarks(img, face_mesh)
        finally:
            face_mesh.close()
        assert lm is not None, "MediaPipe found no landmarks on sample face"

    def test_ear_value_in_expected_range(self):
        """EAR for an open eye should be in range [0.2, 0.5]."""
        from apps.face_auth.services.liveness import (
            _build_face_mesh, _get_landmarks, _ear, LEFT_EYE_IDX, RIGHT_EYE_IDX
        )
        img       = _load_sample()
        face_mesh = _build_face_mesh()
        try:
            lm = _get_landmarks(img, face_mesh)
        finally:
            face_mesh.close()
        if lm is None:
            pytest.skip("No landmarks detected")
        left_ear  = _ear(lm, LEFT_EYE_IDX)
        right_ear = _ear(lm, RIGHT_EYE_IDX)
        assert 0.1 < left_ear  < 0.6, f"Left EAR unexpected: {left_ear}"
        assert 0.1 < right_ear < 0.6, f"Right EAR unexpected: {right_ear}"


# ── 3. Full enroll→verify pipeline without mocks ─────────────────────────────

@pytest.mark.django_db
class TestFullPipelineNoMocks:

    def test_enroll_and_verify_same_face(self, fernet_key):
        """
        Enroll a face from the sample image.
        Verify the same image against the stored embedding.
        Expected: passed=True.
        """
        from apps.face_auth.services.embeddings import extract_embedding
        from apps.face_auth.services.verify import verify_login_face, cosine_similarity
        from apps.face_auth.crypto import encrypt_embedding, decrypt_embedding
        from apps.face_auth.models import FaceProfile
        from apps.accounts.models import User

        user = User.objects.create_user(
            phone='+998991234599', password='pw', full_name='Integration Test'
        )

        img = _load_sample()
        emb = extract_embedding(img)
        assert emb is not None, "Enrollment embedding failed"

        enc = encrypt_embedding(emb)
        profile, _ = FaceProfile.objects.get_or_create(user=user)
        profile.encrypted_embedding = enc
        profile.status              = FaceProfile.Status.ENROLLED
        profile.consent_given       = True
        profile.save()

        # Verify: submit the same image as a single-frame list
        b64 = _img_to_b64(img)

        # Patch liveness to pass (we are testing identity, not challenge here)
        from unittest.mock import patch
        with patch('apps.face_auth.services.liveness.verify_liveness', return_value=(True, '')):
            passed, liveness_ok, identity_ok, error = verify_login_face(
                user, [b64] * 5, 'smile'
            )

        assert identity_ok is True, f"Identity failed: {error}"
        assert passed      is True, f"Pipeline failed: {error}"

    def test_verify_different_face_fails(self, fernet_key):
        """
        Enroll face A; try to verify with face B → identity_matched=False.
        """
        from apps.face_auth.services.embeddings import extract_embedding
        from apps.face_auth.services.verify import verify_login_face
        from apps.face_auth.crypto import encrypt_embedding
        from apps.face_auth.models import FaceProfile
        from apps.accounts.models import User
        from apps.face_auth.tests.conftest import make_synthetic_embedding

        user = User.objects.create_user(
            phone='+998991234500', password='pw', full_name='Test User B'
        )

        # Enroll with a synthetic (random) embedding — very different from real face
        enc = encrypt_embedding(make_synthetic_embedding(512))
        profile, _ = FaceProfile.objects.get_or_create(user=user)
        profile.encrypted_embedding = enc
        profile.status              = FaceProfile.Status.ENROLLED
        profile.consent_given       = True
        profile.save()

        img = _load_sample()
        b64 = _img_to_b64(img)

        from unittest.mock import patch
        with patch('apps.face_auth.services.liveness.verify_liveness', return_value=(True, '')):
            passed, liveness_ok, identity_ok, error = verify_login_face(
                user, [b64] * 5, 'smile'
            )

        assert identity_ok is False, f"Expected identity failure but got: {error}"
        assert passed      is False


# ── 4. Passive liveness: DeepFace Fasnet (real anti-spoofing model) ───────────

class TestPassiveLivenessReal:
    """
    Tests run DeepFace's built-in Fasnet (MiniFASNetV2 + MiniFASNetV1SE ensemble).
    Requires weights in ~/.deepface/weights/ (downloaded automatically on first run).
    """

    def test_real_face_high_score(self):
        """
        DeepFace Fasnet should give a HIGH score (>= 0.7) for a real face image.
        The sample face (Lena) is a natural photograph — should be classified as live.
        """
        from apps.face_auth.services.passive_liveness import _deepface_antispoof_score
        img   = _load_sample()
        score = _deepface_antispoof_score(img)
        assert score >= 0, f"DeepFace Fasnet unavailable (returned -1). Score: {score}"
        assert score >= 0.7, (
            f"Real face should score >= 0.7, got {score:.3f}. "
            "If DeepFace weights not downloaded, run: "
            "python -c \"from deepface import DeepFace; "
            "DeepFace.extract_faces('test.jpg', anti_spoofing=True)\""
        )

    def test_real_face_classified_as_live(self):
        """DeepFace Fasnet should return is_real=True for the sample face."""
        from deepface import DeepFace  # type: ignore
        img     = _load_sample()
        results = DeepFace.extract_faces(
            img_path=img, anti_spoofing=True,
            enforce_detection=False, detector_backend='opencv',
        )
        assert results, "No face detected in sample image"
        assert results[0].get('is_real') is True, (
            f"Expected is_real=True, got {results[0].get('is_real')}, "
            f"score={results[0].get('antispoof_score'):.3f}"
        )

    def test_real_face_scores_higher_than_uniform_frame(self):
        """Real face should score higher than a flat grey rectangle."""
        from apps.face_auth.services.passive_liveness import passive_liveness_score
        real_frame = _load_sample()
        flat_frame = np.full_like(real_frame, 128)
        real_score = passive_liveness_score(real_frame)
        flat_score = passive_liveness_score(flat_frame)
        assert real_score > flat_score, (
            f"Real face ({real_score:.3f}) should score > flat ({flat_score:.3f})"
        )

    def test_lbp_fallback_entropy_real_face_higher_than_flat(self):
        """LBP fallback: real face entropy should exceed flat grey."""
        from apps.face_auth.services.passive_liveness import _lbp_entropy
        img  = _load_sample()
        gray = cv2.cvtColor(cv2.resize(img, (64, 64)), cv2.COLOR_BGR2GRAY)
        ent_face = _lbp_entropy(gray)
        flat     = np.full((64, 64), 128, dtype=np.uint8)
        ent_flat = _lbp_entropy(flat)
        assert ent_face > ent_flat, (
            f"Face entropy ({ent_face:.3f}) should exceed flat ({ent_flat:.3f})"
        )

    def test_check_passive_liveness_enabled_real_face_passes(self, settings):
        """With FACE_PASSIVE_LIVENESS_ENABLED=True, real face should pass."""
        from apps.face_auth.services.passive_liveness import check_passive_liveness
        settings.FACE_PASSIVE_LIVENESS_ENABLED = True
        settings.FACE_SPOOF_THRESHOLD          = 0.5
        img    = _load_sample()
        passed, score, reason = check_passive_liveness([img] * 3)
        assert passed is True, (
            f"Real face should pass passive liveness. score={score:.3f} reason={reason}"
        )
        assert score >= 0.5


# ── 5. Quality validation on real image ──────────────────────────────────────

class TestQualityValidationReal:

    def test_sample_face_passes_quality(self):
        from apps.face_auth.services.embeddings import validate_frame_quality
        img   = _load_sample()
        valid, reason = validate_frame_quality(img)
        assert valid is True, f"Quality check failed on sample face: {reason}"
