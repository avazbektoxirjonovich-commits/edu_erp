"""iOS Web Clip profili: /ios-app.mobileconfig."""
import plistlib

import pytest
from django.test import Client

from apps.common import webclip

URL = '/ios-app.mobileconfig'


@pytest.fixture(autouse=True)
def clear_cache():
    webclip._CACHE.clear()
    yield
    webclip._CACHE.clear()


def profile(host='testserver'):
    resp = Client().get(URL, HTTP_HOST=host)
    assert resp.status_code == 200
    return resp, plistlib.loads(resp.content)


def test_served_as_apple_profile():
    resp, _ = profile()
    assert resp['Content-Type'] == 'application/x-apple-aspen-config'
    assert webclip.FILENAME in resp['Content-Disposition']


def test_webclip_payload_points_to_this_server():
    _, plist = profile()
    assert plist['PayloadType'] == 'Configuration'
    assert len(plist['PayloadContent']) == 1
    clip = plist['PayloadContent'][0]
    assert clip['PayloadType'] == 'com.apple.webClip.managed'
    assert clip['URL'] == 'http://testserver/'
    # To'liq ekran + o'chirilishi mumkin: telefonda oddiy ilova kabi ko'rinadi
    assert (clip['FullScreen'], clip['IsRemovable']) == (True, True)


def test_icon_is_the_erp_logo():
    _, plist = profile()
    assert plist['PayloadContent'][0]['Icon'] == webclip.ICON_PATH.read_bytes()


def test_icon_missing_does_not_break_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(webclip, 'ICON_PATH', tmp_path / 'yoq.png')
    _, plist = profile()
    assert 'Icon' not in plist['PayloadContent'][0]
    assert plist['PayloadContent'][0]['URL'] == 'http://testserver/'


def test_uuid_stable_per_host():
    """Qayta o'rnatganda iOS eskisining ustiga yozadi — UUID o'zgarmasligi shart."""
    _, first = profile()
    webclip._CACHE.clear()          # server qayta ishga tushgandek
    _, again = profile()
    assert first['PayloadUUID'] == again['PayloadUUID']
    assert first['PayloadContent'][0]['PayloadUUID'] == again['PayloadContent'][0]['PayloadUUID']
    _, other = profile(host='erp.example.com')
    assert other['PayloadUUID'] != first['PayloadUUID']
    assert other['PayloadIdentifier'] == first['PayloadIdentifier'] == webclip.PROFILE_ID


def test_https_scheme_is_kept(settings):
    settings.SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    resp = Client().get(URL, HTTP_X_FORWARDED_PROTO='https')
    assert plistlib.loads(resp.content)['PayloadContent'][0]['URL'].startswith('https://')
