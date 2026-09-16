import email.message
import io
import urllib.error

import pytest

from qm_template.errors import QmTemplateError
from qm_template.http import (
    http_get_bytes,
    http_get_text,
    latest_name,
    list_directory,
    natural_key,
)


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes) -> None:
        super().__init__(body)
        self.headers = email.message.Message()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def test_natural_key_orders_versions_numerically():
    names = [
        "Rocky-9-GenericCloud-Base-9.9-20250101.0.x86_64.qcow2",
        "Rocky-9-GenericCloud-Base-9.10-20250101.0.x86_64.qcow2",
    ]
    assert max(names, key=natural_key) == names[1]


def test_latest_name_picks_latest_match():
    names = ["20260101-1", "20260102-2", "README"]
    assert latest_name(names, r"\d{8}-\d+", source="test") == "20260102-2"


def test_latest_name_raises_without_match():
    with pytest.raises(QmTemplateError):
        latest_name(["README"], r"\d+", source="test")


def test_http_get_text_decodes_response(monkeypatch):
    monkeypatch.setattr(
        "qm_template.http.urllib.request.urlopen",
        lambda _request, timeout: FakeResponse(b"hello"),
    )
    assert http_get_text("https://example.com/x") == "hello"


def test_http_get_bytes_returns_raw_bytes(monkeypatch):
    monkeypatch.setattr(
        "qm_template.http.urllib.request.urlopen",
        lambda _request, timeout: FakeResponse(b"\x88\x01raw signature"),
    )
    assert http_get_bytes("https://example.com/x.sig") == b"\x88\x01raw signature"


def test_http_get_text_retries_server_errors(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []

    def fake_urlopen(_request, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(
                "https://example.com/x", 503, "unavailable", None, None
            )
        return FakeResponse(b"ok")

    monkeypatch.setattr("qm_template.http.urllib.request.urlopen", fake_urlopen)
    assert http_get_text("https://example.com/x", sleep=sleeps.append) == "ok"
    assert sleeps == [1.0, 2.0]


def test_http_get_text_retries_url_errors(monkeypatch):
    calls: list[int] = []

    def fake_urlopen(_request, timeout):
        calls.append(1)
        raise urllib.error.URLError("name resolution failed")

    monkeypatch.setattr("qm_template.http.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(QmTemplateError, match="name resolution failed"):
        http_get_text("https://example.com/x", attempts=2, sleep=lambda _delay: None)
    assert len(calls) == 2


def test_http_get_text_retries_timeouts(monkeypatch):
    calls: list[int] = []

    def fake_urlopen(_request, timeout):
        calls.append(1)
        raise TimeoutError("timed out")

    monkeypatch.setattr("qm_template.http.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(QmTemplateError):
        http_get_text("https://example.com/x", attempts=2, sleep=lambda _delay: None)
    assert len(calls) == 2


def test_http_get_text_does_not_retry_client_errors(monkeypatch):
    calls: list[int] = []

    def fake_urlopen(_request, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(
            "https://example.com/x", 404, "not found", None, None
        )

    monkeypatch.setattr("qm_template.http.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(QmTemplateError, match="HTTP 404"):
        http_get_text("https://example.com/x", sleep=lambda _delay: None)
    assert len(calls) == 1


def test_list_directory_extracts_names(monkeypatch):
    monkeypatch.setattr(
        "qm_template.http.http_get_text",
        lambda _url: '<a href="./v1/">v1</a><a href="b%20c">b c</a>',
    )
    assert list_directory("https://example.com/") == ["v1", "b c"]
