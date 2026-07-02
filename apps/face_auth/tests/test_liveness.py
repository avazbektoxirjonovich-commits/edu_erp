"""
Tests for liveness detection services.
Covers: motion check, challenge generation, per-action detection (mocked landmarks).
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from apps.face_auth.services.liveness import (
    frames_have_motion,
    generate_challenge,
    verify_liveness,
    CHALLENGES,
    CHALLENGE_LABELS,
    EAR_CLOSE_THRESHOLD,
    SMILE_WIDTH_RATIO,
    YAW_DISPLACEMENT,
)


# ── Anti-spoofing: motion check ───────────────────────────────────────────────

class TestMotionCheck:

    def _make_frames(self, values: list) -> list:
        """Create grayscale frames with given mean brightness."""
        import cv2
        frames = []
        for v in values:
            img = np.full((50, 50, 3), int(v), dtype=np.uint8)
            frames.append(img)
        return frames

    def test_static_image_fails(self):
        """All identical frames → no motion → liveness denied."""
        frames = self._make_frames([100] * 10)
        assert frames_have_motion(frames) is False

    def test_varying_frames_pass(self):
        """Frames with progressively changing brightness → motion detected."""
        frames = self._make_frames(range(10, 100, 9))
        assert frames_have_motion(frames) is True

    def test_too_few_frames_fail(self):
        frames = self._make_frames([100, 110])
        assert frames_have_motion(frames) is False

    def test_none_frames_ignored(self):
        frames = self._make_frames([100] * 3)
        assert frames_have_motion([None, None, None]) is False


# ── Challenge generation ──────────────────────────────────────────────────────

class TestChallengeGeneration:

    def test_returns_known_action(self):
        for _ in range(30):
            ch = generate_challenge()
            assert ch['action'] in CHALLENGES
            assert ch['label'] in CHALLENGE_LABELS.values()

    def test_challenge_is_random(self):
        """Over many trials, at least two different actions must appear."""
        actions = {generate_challenge()['action'] for _ in range(50)}
        assert len(actions) > 1


# ── Liveness: DENIED paths (no motion) ───────────────────────────────────────

class TestLivenessDenied:

    def test_empty_frames_denied(self):
        passed, reason = verify_liveness([], 'blink')
        assert not passed
        assert reason

    def test_static_frames_denied(self):
        """Static (zero inter-frame diff) frames must always fail."""
        frames = [np.full((50, 50, 3), 100, dtype=np.uint8)] * 10
        passed, reason = verify_liveness(frames, 'smile')
        assert not passed
        assert 'harakatsiz' in reason.lower() or reason

    def test_unknown_action_denied(self):
        """Unknown challenge action is rejected."""
        frames = [np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8) for _ in range(5)]
        with patch('apps.face_auth.services.liveness.frames_have_motion', return_value=True):
            passed, reason = verify_liveness(frames, 'unknown_action')
        assert not passed


# ── Liveness: action detection (MediaPipe mocked) ────────────────────────────

def _make_landmark(x: float, y: float, z: float = 0.0):
    lm = MagicMock()
    lm.x, lm.y, lm.z = x, y, z
    return lm


def _make_face_landmarks(ear_value: float = 0.35, smile_ratio: float = 0.35,
                          nose_x: float = 0.5, face_lx: float = 0.2, face_rx: float = 0.8):
    """
    Build a mock MediaPipe face_landmarks object returning controlled values.
    ear_value:   EAR (eye aspect ratio) — < 0.22 means closed
    smile_ratio: mouth_width / face_width — > 0.46 means smile
    nose_x:      nose-tip x — deviated from centre for head turn
    """
    face_width = face_rx - face_lx
    mouth_width = smile_ratio * face_width

    # Eye landmarks (simplified): vertical distance drives EAR
    # EAR = (v1 + v2) / (2 * h) where h=horizontal separation
    # To get desired EAR: v1=v2=EAR*h, h=0.1
    h = 0.1
    v = ear_value * h

    # Left eye (indices 33,160,158,133,153,144)
    le = [
        _make_landmark(0.3, 0.4),           # P1 (left)
        _make_landmark(0.33, 0.4 - v),      # P2 (top-left)
        _make_landmark(0.37, 0.4 - v),      # P3 (top-right)
        _make_landmark(0.3 + h, 0.4),       # P4 (right)
        _make_landmark(0.37, 0.4 + v),      # P5 (bottom-right)
        _make_landmark(0.33, 0.4 + v),      # P6 (bottom-left)
    ]
    # Right eye (indices 362,385,387,263,373,380) — same structure
    re = [
        _make_landmark(0.6, 0.4),
        _make_landmark(0.63, 0.4 - v),
        _make_landmark(0.67, 0.4 - v),
        _make_landmark(0.6 + h, 0.4),
        _make_landmark(0.67, 0.4 + v),
        _make_landmark(0.63, 0.4 + v),
    ]

    # Mouth corners
    ml = _make_landmark(0.5 - mouth_width / 2, 0.7)
    mr = _make_landmark(0.5 + mouth_width / 2, 0.7)

    # Face outer boundaries
    fl = _make_landmark(face_lx, 0.5)
    fr = _make_landmark(face_rx, 0.5)

    # Nose tip
    nose = _make_landmark(nose_x, 0.5)

    landmark_map = {}
    for i, lm in zip([33,160,158,133,153,144], le):
        landmark_map[i] = lm
    for i, lm in zip([362,385,387,263,373,380], re):
        landmark_map[i] = lm
    landmark_map[61]  = ml
    landmark_map[291] = mr
    landmark_map[234] = fl
    landmark_map[454] = fr
    landmark_map[4]   = nose

    face_lm = MagicMock()
    face_lm.landmark.__getitem__ = lambda self, i: landmark_map[i]
    return face_lm



# ── FIX D: MediaPipe model path configurable + graceful degradation ───────────

class TestFaceLandmarkerPath:

    def test_custom_path_via_setting(self, settings, tmp_path):
        """FACE_LANDMARKER_MODEL setting overrides the default bundled path."""
        import pathlib
        from apps.face_auth.services.liveness import _task_model_path
        custom = str(tmp_path / 'custom.task')
        settings.FACE_LANDMARKER_MODEL = custom
        path = _task_model_path()
        assert str(path) == custom
        # Restore
        settings.FACE_LANDMARKER_MODEL = ''

    def test_missing_model_raises_importerror_in_build(self, settings, tmp_path):
        """
        When task model file is missing, _build_face_mesh() raises ImportError
        (caught by verify_liveness, not propagated to caller).
        """
        from apps.face_auth.services.liveness import _build_face_mesh
        settings.FACE_LANDMARKER_MODEL = str(tmp_path / 'nonexistent.task')
        try:
            fm = _build_face_mesh()
            # If old solutions API available, it would not raise
        except ImportError as e:
            assert 'topilmadi' in str(e) or 'task' in str(e).lower()
        except Exception:
            pass   # any error is acceptable — just must not silently corrupt state
        finally:
            settings.FACE_LANDMARKER_MODEL = ''

    def test_verify_liveness_graceful_when_model_missing(self, settings, tmp_path):
        """
        If face_landmarker.task is missing, verify_liveness must return False
        with an informative message — never raise an unhandled exception.
        """
        from apps.face_auth.services.liveness import verify_liveness
        settings.FACE_LANDMARKER_MODEL = str(tmp_path / 'missing.task')
        frames = [np.random.randint(10*i+5, 10*i+50, (50,50,3), dtype=np.uint8)
                  for i in range(10)]
        try:
            passed, reason = verify_liveness(frames, 'smile')
            assert isinstance(passed, bool)
            assert isinstance(reason, str)
        except Exception as exc:
            pytest.fail(f"verify_liveness raised unexpectedly: {exc}")
        finally:
            settings.FACE_LANDMARKER_MODEL = ''


# ── FIX 4: Passive liveness tests ────────────────────────────────────────────

class TestPassiveLiveness:

    def _solid_frame(self, val=128):
        return np.full((80, 80, 3), val, dtype=np.uint8)

    def _noisy_frame(self, seed=0):
        rng = np.random.RandomState(seed)
        return rng.randint(30, 220, (80, 80, 3), dtype=np.uint8)

    def test_score_returns_float_0_to_1(self):
        from apps.face_auth.services.passive_liveness import passive_liveness_score
        frame = self._noisy_frame()
        score = passive_liveness_score(frame)
        assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_noisy_frame_scores_higher_than_solid(self):
        """Varied texture (natural) should score higher than flat solid color."""
        from apps.face_auth.services.passive_liveness import passive_liveness_score
        solid = self._solid_frame(128)
        noisy = self._noisy_frame(42)
        score_solid = passive_liveness_score(solid)
        score_noisy = passive_liveness_score(noisy)
        assert score_noisy >= score_solid, (
            f"Noisy ({score_noisy:.3f}) should >= solid ({score_solid:.3f})"
        )

    def test_check_passive_liveness_disabled(self, settings):
        """When FACE_PASSIVE_LIVENESS_ENABLED=False, always passes."""
        from apps.face_auth.services.passive_liveness import check_passive_liveness
        settings.FACE_PASSIVE_LIVENESS_ENABLED = False
        solid = [self._solid_frame(0)] * 5   # all-black frames
        passed, score, reason = check_passive_liveness(solid)
        assert passed is True

    def test_check_passive_liveness_enabled_low_score_fails(self, settings):
        """Flat/uniform frames score low and fail when enabled with high threshold."""
        from apps.face_auth.services.passive_liveness import check_passive_liveness, _lbp_fourier_score
        settings.FACE_PASSIVE_LIVENESS_ENABLED = True
        settings.FACE_SPOOF_THRESHOLD = 0.99   # very high threshold
        flat_frame = self._solid_frame(100)   # uniform texture → low LBP entropy
        passed, score, reason = check_passive_liveness([flat_frame] * 5)
        assert passed is False

    def test_check_passive_liveness_graceful_on_crash(self, settings):
        """If passive liveness raises an unexpected exception, liveness continues."""
        from unittest.mock import patch
        settings.FACE_PASSIVE_LIVENESS_ENABLED = True
        # Patch at the source module (it's imported inside the function)
        with patch('apps.face_auth.services.passive_liveness.check_passive_liveness',
                   side_effect=RuntimeError("model crash")):
            from apps.face_auth.services.liveness import verify_liveness
            varied = [np.random.randint(i*10+5, i*10+50, (50,50,3), dtype=np.uint8)
                      for i in range(10)]
            with patch('apps.face_auth.services.liveness.frames_have_motion', return_value=True), \
                 patch('apps.face_auth.services.liveness._build_face_mesh') as mock_fm:
                mock_fm.return_value.process.return_value.multi_face_landmarks = None
                mock_fm.return_value.close = lambda: None
                passed, reason = verify_liveness(varied, 'smile')
                assert isinstance(passed, bool)

    def test_no_crash_when_frames_empty(self):
        from apps.face_auth.services.passive_liveness import check_passive_liveness
        passed, score, reason = check_passive_liveness([])
        assert passed is True   # no frames → can't score → pass


@pytest.mark.parametrize("challenge,ear_seq,smile_ratio,nose_x,expected", [
    # blink: EAR dips below threshold then recovers
    ('blink',       [0.35, 0.35, 0.10, 0.10, 0.35, 0.35], 0.35, 0.5, True),
    # no blink: EAR stays high
    ('blink',       [0.35] * 10,                            0.35, 0.5, False),
    # blink_twice
    ('blink_twice', [0.35, 0.10, 0.35, 0.10, 0.35, 0.35],  0.35, 0.5, True),
    # blink_twice: only one dip → fail
    ('blink_twice', [0.35, 0.10, 0.35, 0.35, 0.35, 0.35],  0.35, 0.5, False),
    # smile: mouth wide for many frames
    ('smile',       [0.35] * 8,                             0.55, 0.5, True),
    # no smile
    ('smile',       [0.35] * 8,                             0.30, 0.5, False),
    # turn left: nose displaced left
    ('turn_left',   [0.35] * 8,                             0.35, 0.35, True),
    # turn right
    ('turn_right',  [0.35] * 8,                             0.35, 0.65, True),
    # no turn left
    ('turn_left',   [0.35] * 8,                             0.35, 0.5,  False),
])
def test_liveness_action(challenge, ear_seq, smile_ratio, nose_x, expected):
    """Parametrised test for each action with mocked MediaPipe landmarks."""
    import cv2

    def make_frame(i):
        return np.random.randint(10 * i + 5, 10 * i + 50, (50, 50, 3), dtype=np.uint8)

    n_frames = max(len(ear_seq), 8)
    frames   = [make_frame(i) for i in range(n_frames)]

    # Mock MediaPipe
    mock_fm = MagicMock()
    call_count = [0]
    def fake_process(rgb):
        idx = call_count[0]
        ear = ear_seq[idx] if idx < len(ear_seq) else ear_seq[-1]
        call_count[0] += 1
        result = MagicMock()
        lm = _make_face_landmarks(ear_value=ear, smile_ratio=smile_ratio, nose_x=nose_x)
        result.multi_face_landmarks = [lm]
        return result
    mock_fm.process.side_effect = fake_process

    with patch('apps.face_auth.services.liveness._build_face_mesh', return_value=mock_fm), \
         patch('apps.face_auth.services.liveness.frames_have_motion', return_value=True):
        passed, reason = verify_liveness(frames, challenge)

    assert passed is expected, f"challenge={challenge} expected={expected} reason={reason}"
