import argparse

import pytest

from qm_template.commands import (
    _complete_distro_names,
    _complete_distro_option,
    _download_verified,
)
from qm_template.distros import RemoteImage
from qm_template.errors import QmTemplateError


def test_complete_distro_names():
    assert _complete_distro_names("ub") == ["ubuntu"]
    assert "debian" in _complete_distro_names("")


def test_complete_distro_option_uses_parsed_distro():
    complete = _complete_distro_option("release")
    namespace = argparse.Namespace(distro="debian")
    assert "bookworm-backports" in complete("bookworm", parsed_args=namespace)
    assert complete("x", parsed_args=argparse.Namespace()) == []
    assert complete("x", parsed_args=argparse.Namespace(distro="rocky")) == []


def remote_image() -> RemoteImage:
    return RemoteImage(
        distro="debian",
        release="trixie",
        filename="debian-13-genericcloud-amd64.qcow2",
        url="https://example.com/debian.qcow2",
        checksum_url="https://example.com/SHA256SUMS",
        algorithm="sha256",
    )


def test_download_verified_retries_after_checksum_mismatch(monkeypatch, tmp_path):
    part = tmp_path / "image.qcow2.part"
    calls: list[int] = []

    def fake_download(image, destination, downloader):
        calls.append(1)
        part.write_bytes(b"data")
        return part

    results = iter([False, True])
    monkeypatch.setattr("qm_template.commands.download_image", fake_download)
    monkeypatch.setattr(
        "qm_template.commands.verify_checksum", lambda *_args: next(results)
    )
    assert (
        _download_verified(remote_image(), tmp_path / "image.qcow2", None, "abc")
        == part
    )
    assert len(calls) == 2


def test_download_verified_gives_up_after_two_attempts(monkeypatch, tmp_path):
    part = tmp_path / "image.qcow2.part"
    calls: list[int] = []

    def fake_download(image, destination, downloader):
        calls.append(1)
        part.write_bytes(b"data")
        return part

    monkeypatch.setattr("qm_template.commands.download_image", fake_download)
    monkeypatch.setattr("qm_template.commands.verify_checksum", lambda *_args: False)
    with pytest.raises(QmTemplateError):
        _download_verified(remote_image(), tmp_path / "image.qcow2", None, "abc")
    assert len(calls) == 2
    assert not part.exists()
