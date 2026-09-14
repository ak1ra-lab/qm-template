import hashlib

import pytest

from qm_template.checksum import (
    fetch_checksum,
    parse_checksum,
    save_checksum,
    verify_checksum,
)
from qm_template.errors import QmTemplateError

DIGEST = "a" * 128


def test_fetch_checksum_uses_http_helper(monkeypatch):
    monkeypatch.setattr(
        "qm_template.checksum.http_get_text",
        lambda url: f"{DIGEST}  image.qcow2\n",
    )
    assert fetch_checksum("https://example.com/SHA512SUMS", "image.qcow2") == DIGEST


def test_parse_gnu_format():
    text = f"{DIGEST} *ubuntu-24.04-server-cloudimg-amd64.img\n"
    assert parse_checksum(text, "ubuntu-24.04-server-cloudimg-amd64.img") == DIGEST


def test_parse_bsd_format():
    text = f"SHA256 (Rocky-9-GenericCloud-Base-9.8.x86_64.qcow2) = {'b' * 64}\n"
    assert (
        parse_checksum(text, "Rocky-9-GenericCloud-Base-9.8.x86_64.qcow2") == "b" * 64
    )


def test_parse_clearsigned_fedora_format():
    text = (
        "-----BEGIN PGP SIGNED MESSAGE-----\n"
        "Hash: SHA256\n"
        "\n"
        f"# Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2: 1 bytes\n"
        f"SHA256 (Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2) = {'c' * 64}\n"
        "-----BEGIN PGP SIGNATURE-----\n"
        "\n"
        "iQIzBAEBCgAdFiEE\n"
        "-----END PGP SIGNATURE-----\n"
    )
    filename = "Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2"
    assert parse_checksum(text, filename) == "c" * 64


def test_parse_selects_matching_filename():
    text = (
        f"{'1' * 64}  AlmaLinux-9-GenericCloud-9.8-a.x86_64.qcow2\n"
        f"{'2' * 64}  AlmaLinux-9-GenericCloud-9.8-b.x86_64.qcow2\n"
    )
    assert (
        parse_checksum(text, "AlmaLinux-9-GenericCloud-9.8-b.x86_64.qcow2") == "2" * 64
    )


def test_parse_single_bare_digest():
    assert parse_checksum(f"{'d' * 128}\n", "anything.qcow2") == "d" * 128


def test_parse_missing_filename_raises():
    text = f"{'1' * 64}  a.qcow2\n{'2' * 64}  b.qcow2\n"
    with pytest.raises(QmTemplateError):
        parse_checksum(text, "c.qcow2")


def test_verify_checksum(tmp_path):
    path = tmp_path / "image.qcow2"
    path.write_bytes(b"cloud image")
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    assert verify_checksum(path, digest, "sha256")
    assert not verify_checksum(path, "0" * 64, "sha256")


def test_save_checksum_writes_sha256sum_compatible_file(tmp_path):
    image = tmp_path / "image.qcow2"
    image.write_bytes(b"cloud image")
    digest = hashlib.file_digest(image.open("rb"), "sha256").hexdigest()
    target = save_checksum(image, digest.upper(), "sha256")
    assert target == tmp_path / "image.qcow2.sha256"
    assert target.read_text() == f"{digest}  image.qcow2\n"


def test_save_checksum_rejects_unknown_algorithm(tmp_path):
    with pytest.raises(QmTemplateError):
        save_checksum(tmp_path / "image.qcow2", "a" * 64, "md5")
