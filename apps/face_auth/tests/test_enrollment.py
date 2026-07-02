"""
Tests for face enrollment endpoint.
All DeepFace / OpenCV calls are mocked — no real camera or model needed.
"""
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
import numpy as np

from apps.face_auth.models import FaceProfile
from .conftest import make_black_frame_b64, make_synthetic_embedding


@pytest.mark.django_db
class TestFaceEnroll:

    ENROLL_URL = '/api/v1/face-auth/enroll/'

    def _post(self, client, user, frame_b64, consent=True):
        client.force_authenticate(user=user)
        return client.post(
            self.ENROLL_URL,
            {'frame': frame_b64, 'consent': consent},
            format='json',
        )

    # ── Success path ──────────────────────────────────────────────────────────

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_enroll_success(self, mock_decode, mock_quality, mock_embed,
                            api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = make_synthetic_embedding()

        resp = self._post(api_client, admin_user, make_black_frame_b64())

        assert resp.status_code == 200
        assert resp.json()['status'] == 'enrolled'

        profile = FaceProfile.objects.get(user=admin_user)
        assert profile.is_enrolled
        assert profile.consent_given
        assert profile.encrypted_embedding is not None

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_reenroll_overwrites_old_embedding(self, mock_decode, mock_quality, mock_embed,
                                               api_client, admin_user, fernet_key):
        """Re-enrollment replaces the previous embedding."""
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = make_synthetic_embedding()

        self._post(api_client, admin_user, make_black_frame_b64())
        old_enc = admin_user.face_profile.encrypted_embedding

        new_emb = make_synthetic_embedding(512)
        new_emb[0] = 0.9999
        mock_embed.return_value = new_emb

        self._post(api_client, admin_user, make_black_frame_b64())
        admin_user.face_profile.refresh_from_db()
        assert admin_user.face_profile.encrypted_embedding != old_enc

    # ── DENIED paths ──────────────────────────────────────────────────────────

    def test_enroll_requires_consent(self, api_client, admin_user, fernet_key):
        resp = self._post(api_client, admin_user, make_black_frame_b64(), consent=False)
        assert resp.status_code == 400
        assert 'rozil' in resp.json()['detail'].lower()

    @patch('apps.face_auth.api.views.decode_frame')
    def test_enroll_bad_frame(self, mock_decode, api_client, admin_user, fernet_key):
        mock_decode.return_value = None
        resp = self._post(api_client, admin_user, 'not-valid-base64')
        assert resp.status_code == 400

    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_enroll_quality_fail_no_face(self, mock_decode, mock_quality,
                                         api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (False, 'Yuz aniqlanmadi. Kameraga to\'g\'ri qarash.')

        resp = self._post(api_client, admin_user, make_black_frame_b64())
        assert resp.status_code == 400
        assert 'Yuz aniqlanmadi' in resp.json()['detail']

    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_enroll_quality_fail_blurry(self, mock_decode, mock_quality,
                                        api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (False, 'Tasvir xiralashgan. Kamerani barqaror ushlab turing.')

        resp = self._post(api_client, admin_user, make_black_frame_b64())
        assert resp.status_code == 400
        assert 'xiralashgan' in resp.json()['detail']

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_enroll_embedding_fail(self, mock_decode, mock_quality, mock_embed,
                                   api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = None

        resp = self._post(api_client, admin_user, make_black_frame_b64())
        assert resp.status_code == 400

    def test_enroll_requires_auth(self, api_client, fernet_key):
        resp = api_client.post(self.ENROLL_URL, {}, format='json')
        assert resp.status_code == 401


@pytest.mark.django_db
class TestFaceStatus:

    STATUS_URL = '/api/v1/face-auth/status/'

    def test_status_not_enrolled(self, api_client, admin_user, fernet_key):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.get(self.STATUS_URL)
        assert resp.status_code == 200
        assert resp.json()['enrolled'] is False

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_status_enrolled(self, mock_decode, mock_quality, mock_embed,
                              api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = make_synthetic_embedding()

        api_client.force_authenticate(user=admin_user)
        api_client.post(
            '/api/v1/face-auth/enroll/',
            {'frame': make_black_frame_b64(), 'consent': True},
            format='json',
        )
        resp = api_client.get(self.STATUS_URL)
        assert resp.json()['enrolled'] is True
        assert resp.json()['label'] == 'Yoqilgan'


@pytest.mark.django_db
class TestFaceDelete:

    DELETE_URL = '/api/v1/face-auth/enroll/delete/'

    @patch('apps.face_auth.api.views.extract_embedding')
    @patch('apps.face_auth.api.views.validate_frame_quality')
    @patch('apps.face_auth.api.views.decode_frame')
    def test_delete_enrollment(self, mock_decode, mock_quality, mock_embed,
                               api_client, admin_user, fernet_key):
        mock_decode.return_value  = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_quality.return_value = (True, '')
        mock_embed.return_value   = make_synthetic_embedding()

        api_client.force_authenticate(user=admin_user)
        api_client.post('/api/v1/face-auth/enroll/',
                        {'frame': make_black_frame_b64(), 'consent': True}, format='json')

        resp = api_client.delete(self.DELETE_URL)
        assert resp.status_code == 200

        admin_user.face_profile.refresh_from_db()
        assert not admin_user.face_profile.is_enrolled
