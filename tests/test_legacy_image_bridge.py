"""Explicit backwards-compatible image APIs; text scanning remains unified."""
import json
import httpx
import pytest

from testsavant.guard import Guardrail
from testsavant.guard.image_scanners import ImageNSFW


def test_legacy_image_upload_is_explicit_and_separate(tmp_path):
    image = tmp_path / 'sample.png'
    image.write_bytes(b'not-a-real-image-test-fixture')
    seen = []
    def handler(req):
        seen.append(req)
        return httpx.Response(200, json={
            'is_valid': True,
            'scanners': {'ImageNSFW:base': 0.1},
            'validity': {'ImageNSFW:base': True}
        })
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        guard = Guardrail(API_KEY='key', remote_addr='https://example.test', sync_client=transport)
        guard.add_scanner(ImageNSFW(tag='base'))
        result = guard.scan_images([str(image)], prompt='Check image')
    assert result.is_valid is True
    assert result.validity['ImageNSFW:base'] is True
    assert str(seen[0].url).endswith('/guard/image-input')
    assert seen[0].headers.get('Content-Type', '').startswith('multipart/form-data')
    assert b'ImageNSFW:base' in seen[0].content


def test_legacy_image_download_and_safe_filename(tmp_path):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'png-data'))) as transport:
        guard = Guardrail(API_KEY='key', remote_addr='https://example.test', sync_client=transport)
        paths = guard.fetch_image_results(['clean.png'], str(tmp_path))
        assert len(paths) == 1
        assert (tmp_path/'clean.png').read_bytes() == b'png-data'
        with pytest.raises(ValueError, match='basenames'):
            guard.fetch_image_results(['../escape.png'], str(tmp_path))
