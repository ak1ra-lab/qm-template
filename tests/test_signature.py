from types import SimpleNamespace

import pytest

from qm_template.errors import QmTemplateError
from qm_template.signature import (
    Signature,
    valid_fingerprint,
    verify,
    verify_checksum,
    verify_image,
)

PRIMARY = "1B9A16984A4E8CB448712D2AE0B78BF4326C6F8F"
SUBKEY = "656E4C5AC1CC3B86E539D97E343635A6859A9174"
VALID = f"[GNUPG:] VALIDSIG {SUBKEY} 2026-09-16 1 0 4 0 1 8 01 {PRIMARY}"


def signature(**overrides) -> Signature:
    values = {
        "url": "https://example.com/SHA256SUMS.gpg",
        "key_url": "https://example.com/key.asc",
        "fingerprint": PRIMARY,
    }
    values.update(overrides)
    return Signature(**values)


def test_valid_fingerprint_returns_the_primary_key():
    assert valid_fingerprint(VALID) == PRIMARY


def test_valid_fingerprint_ignores_status_without_validsig():
    assert valid_fingerprint("[GNUPG:] GOODSIG abc uid\n[GNUPG:] NODATA 1") is None


def test_verify_requires_gpg(monkeypatch):
    monkeypatch.setattr("qm_template.signature.shutil.which", lambda _name: None)
    with pytest.raises(QmTemplateError, match="gpg"):
        verify(signature(), None, b"signature")


def test_verify_accepts_a_pinned_primary_key(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(
            returncode=0, stdout=f"[GNUPG:] GOODSIG abc uid\n{VALID}", stderr=""
        )

    monkeypatch.setattr(
        "qm_template.signature.shutil.which", lambda _name: "/usr/bin/gpg"
    )
    monkeypatch.setattr(
        "qm_template.signature.http_get_bytes", lambda _url: b"armored text"
    )
    monkeypatch.setattr("qm_template.signature.run", fake_run)
    verify(signature(), None, b"signature")
    assert any("--verify" in call for call in calls)


def test_verify_rejects_an_unexpected_key(monkeypatch):
    monkeypatch.setattr(
        "qm_template.signature.shutil.which", lambda _name: "/usr/bin/gpg"
    )
    monkeypatch.setattr(
        "qm_template.signature.http_get_bytes", lambda _url: b"armored text"
    )
    monkeypatch.setattr(
        "qm_template.signature.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=f"{VALID}\n", stderr=""
        ),
    )
    with pytest.raises(QmTemplateError, match="expected"):
        verify(signature(fingerprint="A" * 40), None, b"signature")


def test_verify_rejects_a_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        "qm_template.signature.shutil.which", lambda _name: "/usr/bin/gpg"
    )
    monkeypatch.setattr(
        "qm_template.signature.http_get_bytes", lambda _url: b"armored text"
    )

    def fake_run(argv, **_kwargs):
        if "--import" in argv:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="gpg: BAD signature")

    monkeypatch.setattr("qm_template.signature.run", fake_run)
    with pytest.raises(QmTemplateError, match="could not verify"):
        verify(signature(), None, b"signature")


def test_verify_checksum_stages_detached_data(monkeypatch):
    recorded: dict[str, object] = {}

    def fake_verify(sig, data, signature_text):
        recorded["data"] = data.read_text()
        recorded["signature"] = sig
        recorded["text"] = signature_text

    monkeypatch.setattr("qm_template.signature.verify", fake_verify)
    monkeypatch.setattr(
        "qm_template.signature.http_get_bytes", lambda _url: b"signature text"
    )
    verify_checksum("checksum text", signature())
    assert recorded["data"] == "checksum text"
    assert recorded["text"] == b"signature text"


def test_verify_checksum_handles_a_clearsigned_file(monkeypatch):
    recorded: dict[str, object] = {}

    def fake_verify(sig, data, signature_text):
        recorded["data"] = data
        recorded["text"] = signature_text

    monkeypatch.setattr("qm_template.signature.verify", fake_verify)
    verify_checksum("signed checksum", signature(kind="clearsigned"))
    assert recorded["data"] is None
    assert recorded["text"] == b"signed checksum"


def test_verify_image_verifies_the_file(monkeypatch, tmp_path):
    recorded: dict[str, object] = {}
    image = tmp_path / "image.qcow2"
    image.write_bytes(b"image")

    def fake_verify(sig, data, signature_text):
        recorded["data"] = data

    monkeypatch.setattr("qm_template.signature.verify", fake_verify)
    monkeypatch.setattr(
        "qm_template.signature.http_get_bytes", lambda _url: b"signature text"
    )
    verify_image(image, signature(target="image"))
    assert recorded["data"] == image
