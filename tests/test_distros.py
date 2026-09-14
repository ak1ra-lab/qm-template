from pathlib import Path

import pytest

from qm_template.distros import DISTROS
from qm_template.distros.archlinux import ArchLinux
from qm_template.distros.base import RemoteImage
from qm_template.distros.debian import Debian
from qm_template.distros.opensuse import OpenSUSE
from qm_template.distros.ubuntu import Ubuntu
from qm_template.errors import QmTemplateError


def remote_image(**overrides):
    values = {
        "distro": "ubuntu",
        "release": "noble",
        "filename": "noble-server-cloudimg-amd64.img",
        "url": "https://example.com/noble-server-cloudimg-amd64.img",
        "checksum_url": "https://example.com/SHA256SUMS",
        "algorithm": "sha256",
    }
    values.update(overrides)
    return RemoteImage(**values)


def test_local_path_includes_tag():
    image = remote_image(tag="20260911")
    assert image.local_path == Path(
        "ubuntu/noble/20260911/noble-server-cloudimg-amd64.img"
    )


def test_local_path_omits_missing_tag():
    assert remote_image().local_path == Path(
        "ubuntu/noble/noble-server-cloudimg-amd64.img"
    )


def test_local_path_rejects_traversal():
    image = remote_image(release="../../etc")
    with pytest.raises(QmTemplateError):
        image.local_path


def test_registry_contains_expected_distros():
    assert set(DISTROS) == {
        "debian",
        "ubuntu",
        "rocky",
        "almalinux",
        "fedora",
        "centos",
        "alpine",
        "opensuse",
        "archlinux",
    }


def test_debian_version_mapping():
    debian = Debian()
    assert debian.version("trixie") == "13"
    assert debian.version("bookworm-backports") == "12-backports"
    with pytest.raises(QmTemplateError):
        debian.version("etch")


def test_debian_pins_newest_build(monkeypatch):
    listing = ["20250806-2196", "20260413-2447", "latest"]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Debian()
    image = distro.resolve(distro.merge({}, {}))
    assert image.tag == "20260413-2447"
    assert image.local_path == Path(
        "debian/trixie/20260413-2447/debian-13-genericcloud-amd64-20260413-2447.qcow2"
    )


def test_merge_applies_overrides():
    params = DISTROS["rocky"].merge({"release": "10"}, {"variant": "GenericCloud-LVM"})
    assert params == {
        "release": "10",
        "variant": "GenericCloud-LVM",
        "arch": "x86_64",
    }


def test_merge_rejects_unknown_parameter():
    with pytest.raises(QmTemplateError):
        DISTROS["debian"].merge({"typo": "x"}, {})


def test_ubuntu_server_pins_newest_dated_build(monkeypatch):
    listing = ["20260705", "20260911", "current"]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Ubuntu()
    image = distro.resolve(distro.merge({}, {}))
    assert image.tag == "20260911"
    assert image.url == (
        "https://cloud-images.ubuntu.com/resolute/20260911/"
        "resolute-server-cloudimg-amd64.img"
    )
    assert image.checksum_url == (
        "https://cloud-images.ubuntu.com/resolute/20260911/SHA256SUMS"
    )
    assert image.local_path == Path(
        "ubuntu/resolute/20260911/resolute-server-cloudimg-amd64.img"
    )


def test_ubuntu_minimal_keeps_floating_filename(monkeypatch):
    listing = ["ubuntu-26.04-minimal-cloudimg-amd64.img"]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Ubuntu()
    image = distro.resolve(distro.merge({}, {"variant": "minimal"}))
    assert image.tag is None
    assert image.local_path == Path(
        "ubuntu/resolute/ubuntu-26.04-minimal-cloudimg-amd64.img"
    )


def test_archlinux_pins_newest_build(monkeypatch):
    listing = ["latest", "v20260615.545059", "v20260901.583572"]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = ArchLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.tag is None
    assert image.release == "v20260901.583572"
    assert image.url == (
        "https://geo.mirror.pkgbuild.com/images/v20260901.583572/"
        "Arch-Linux-x86_64-cloudimg.qcow2"
    )
    assert image.checksum_url == image.url + ".SHA256"
    assert image.local_path == Path(
        "archlinux/v20260901.583572/Arch-Linux-x86_64-cloudimg.qcow2"
    )


def test_archlinux_accepts_explicit_build(monkeypatch):
    def unexpected_listing(url: str) -> list[str]:
        raise AssertionError(f"unexpected listing of {url}")

    monkeypatch.setattr("qm_template.distros.base.list_directory", unexpected_listing)
    distro = ArchLinux()
    image = distro.resolve(distro.merge({}, {"release": "v20260901.583572"}))
    assert image.local_path == Path(
        "archlinux/v20260901.583572/Arch-Linux-x86_64-cloudimg.qcow2"
    )


def test_opensuse_tumbleweed_prefers_snapshot(monkeypatch):
    listing = [
        "openSUSE-Tumbleweed-Minimal-VM.x86_64-Cloud.qcow2",
        "openSUSE-Tumbleweed-Minimal-VM.x86_64-1.0.0-Cloud-Snapshot20260801.qcow2",
        "openSUSE-Tumbleweed-Minimal-VM.x86_64-1.0.0-Cloud-Snapshot20260911.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = OpenSUSE()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == (
        "openSUSE-Tumbleweed-Minimal-VM.x86_64-1.0.0-Cloud-Snapshot20260911.qcow2"
    )
    assert image.local_path == Path("opensuse/tumbleweed") / image.filename


def test_ubuntu_rejects_unknown_variant():
    distro = Ubuntu()
    with pytest.raises(QmTemplateError):
        distro.resolve(distro.merge({}, {"variant": "desktop"}))
