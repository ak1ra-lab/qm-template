from pathlib import Path

import pytest

from qm_template.distros import DISTROS
from qm_template.distros.alpine import Alpine
from qm_template.distros.archlinux import ArchLinux
from qm_template.distros.base import RemoteImage
from qm_template.distros.debian import Debian
from qm_template.distros.opensuse import OpenSUSE
from qm_template.distros.redhat import (
    AlmaLinux,
    CentOSStream,
    Fedora,
    RockyLinux,
)
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
    params = DISTROS["rocky"].merge({"release": "9"}, {"variant": "GenericCloud-LVM"})
    assert params["release"] == "9"
    assert params["variant"] == "GenericCloud-LVM"
    assert params["arch"] == "x86_64"
    assert params["base_url"] == "https://dl.rockylinux.org/pub/rocky"


def test_base_url_override_changes_image_and_checksum_urls(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: ["20260413-2447"]
    )
    distro = Debian()
    image = distro.resolve(
        distro.merge({"base_url": "https://mirror.example/debian"}, {})
    )
    assert image.url == (
        "https://mirror.example/debian/trixie/20260413-2447/"
        "debian-13-genericcloud-amd64-20260413-2447.qcow2"
    )
    assert image.checksum_url == (
        "https://mirror.example/debian/trixie/20260413-2447/SHA512SUMS"
    )


def test_redhat_family_defaults_to_release_10():
    for name in ("rocky", "almalinux", "centos"):
        assert DISTROS[name].merge({}, {})["release"] == "10"


def test_almalinux_pins_newest_dated_build(monkeypatch):
    listing = [
        "AlmaLinux-10-GenericCloud-10.2-20260526.0.x86_64.qcow2",
        "AlmaLinux-10-GenericCloud-10.2-20260817.0.x86_64.qcow2",
        "AlmaLinux-10-GenericCloud-latest.x86_64.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = AlmaLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == "AlmaLinux-10-GenericCloud-10.2-20260817.0.x86_64.qcow2"
    assert image.local_path == Path(
        "almalinux/10/AlmaLinux-10-GenericCloud-10.2-20260817.0.x86_64.qcow2"
    )


def test_merge_rejects_unknown_parameter():
    with pytest.raises(QmTemplateError):
        DISTROS["debian"].merge({"typo": "x"}, {})


def test_merge_rejects_invalid_choice():
    with pytest.raises(QmTemplateError, match="choose from"):
        DISTROS["debian"].merge({"variant": "desktop"}, {})


def test_merge_rejects_unsupported_tag():
    with pytest.raises(QmTemplateError, match="unknown parameter 'tag'"):
        DISTROS["rocky"].merge({"tag": "1"}, {})


def test_option_accepts_suffix_and_free_form_values():
    release = DISTROS["debian"].options["release"]
    assert release.accepts("bookworm")
    assert release.accepts("bookworm-backports")
    assert not release.accepts("etch")
    assert DISTROS["rocky"].options["release"].accepts("11")
    assert "bookworm-backports" in release.completions("bookworm")


def test_declared_options_cover_defaults():
    for distro in DISTROS.values():
        assert set(distro.defaults) <= set(distro.options)


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


def test_archlinux_rejects_basic_variant():
    with pytest.raises(QmTemplateError, match="choose from"):
        DISTROS["archlinux"].merge({}, {"variant": "basic"})


def test_alpine_aarch64_resolves_uefi_images(monkeypatch):
    listing = [
        "generic_alpine-3.24.1-aarch64-uefi-cloudinit-r0.qcow2",
        "generic_alpine-3.24.1-aarch64-uefi-tiny-r0.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Alpine()
    image = distro.resolve(distro.merge({}, {"arch": "aarch64"}))
    assert image.filename == "generic_alpine-3.24.1-aarch64-uefi-cloudinit-r0.qcow2"


def test_alpine_x86_64_resolves_bios_images(monkeypatch):
    listing = [
        "generic_alpine-3.24.1-x86_64-bios-cloudinit-r0.qcow2",
        "generic_alpine-3.24.1-x86_64-uefi-cloudinit-r0.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Alpine()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == "generic_alpine-3.24.1-x86_64-bios-cloudinit-r0.qcow2"


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


def test_rocky_pins_newest_dated_build(monkeypatch):
    listing = [
        "Rocky-10-GenericCloud-Base-10.0-20250601.0.x86_64.qcow2",
        "Rocky-10-GenericCloud-Base-10.1-20260201.0.x86_64.qcow2",
        "Rocky-10-GenericCloud-Base-latest.x86_64.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = RockyLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == "Rocky-10-GenericCloud-Base-10.1-20260201.0.x86_64.qcow2"
    assert image.checksum_url.endswith(f"{image.filename}.CHECKSUM")
    assert image.local_path == Path("rocky/10") / image.filename
    with pytest.raises(QmTemplateError):
        distro.resolve(distro.merge({}, {"variant": "Desktop"}))


def test_fedora_pins_newest_dated_build(monkeypatch):
    listing = [
        "Fedora-Cloud-Base-Generic-44-1.9.x86_64.qcow2",
        "Fedora-Cloud-Base-Generic-44-1.10.x86_64.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = Fedora()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == "Fedora-Cloud-Base-Generic-44-1.10.x86_64.qcow2"
    assert image.checksum_url == (
        "https://download.fedoraproject.org/pub/fedora/linux/releases/44/Cloud/"
        "x86_64/images/Fedora-Cloud-44-1.10-x86_64-CHECKSUM"
    )
    assert image.local_path == Path("fedora/44") / image.filename


def test_fedora_accepts_explicit_tag(monkeypatch):
    def unexpected_listing(url: str) -> list[str]:
        raise AssertionError(f"unexpected listing of {url}")

    monkeypatch.setattr("qm_template.distros.base.list_directory", unexpected_listing)
    distro = Fedora()
    image = distro.resolve(distro.merge({}, {"tag": "1.9"}))
    assert image.filename == "Fedora-Cloud-Base-Generic-44-1.9.x86_64.qcow2"


def test_centos_pins_newest_dated_build(monkeypatch):
    listing = [
        "CentOS-Stream-GenericCloud-x86_64-10-20260101.0.x86_64.qcow2",
        "CentOS-Stream-GenericCloud-x86_64-10-20260901.0.x86_64.qcow2",
    ]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda url: listing)
    distro = CentOSStream()
    image = distro.resolve(distro.merge({}, {}))
    assert (
        image.filename == "CentOS-Stream-GenericCloud-x86_64-10-20260901.0.x86_64.qcow2"
    )
    assert image.checksum_url.endswith(f"{image.filename}.SHA256SUM")
    assert image.local_path == Path("centos/10") / image.filename


def test_opensuse_leap_resolves(monkeypatch):
    filename = "openSUSE-Leap-15.6-Minimal-VM.x86_64-Cloud.qcow2"
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda url: [filename]
    )
    distro = OpenSUSE()
    image = distro.resolve(distro.merge({}, {"release": "15.6"}))
    assert image.filename == filename
    assert image.url.endswith(f"/15.6/appliances/{filename}")
    assert image.checksum_url == f"{image.url}.sha256"
    assert image.local_path == Path("opensuse/15.6") / filename


def test_ubuntu_declares_a_signed_checksum(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: ["20260911"]
    )
    distro = Ubuntu()
    image = distro.resolve(distro.merge({}, {}))
    assert image.signature is not None
    assert image.signature.url.endswith("/SHA256SUMS.gpg")
    assert image.signature.target == "checksum"
    assert image.signature.fingerprint == "D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81"
    assert image.signature.key_url.startswith("https://keyserver.ubuntu.com/")


def test_alpine_signs_the_downloaded_image(monkeypatch):
    filename = "generic_alpine-3.24.1-x86_64-bios-cloudinit-r0.qcow2"
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: [filename]
    )
    distro = Alpine()
    image = distro.resolve(distro.merge({}, {}))
    assert image.signature is not None
    assert image.signature.url == f"{image.url}.asc"
    assert image.signature.target == "image"
    assert image.signature.key_url == "https://alpinelinux.org/keys/tomalok.asc"


def test_fedora_checksum_is_clearsigned(monkeypatch):
    listing = ["Fedora-Cloud-Base-Generic-44-1.10.x86_64.qcow2"]
    monkeypatch.setattr("qm_template.distros.base.list_directory", lambda _url: listing)
    distro = Fedora()
    image = distro.resolve(distro.merge({}, {}))
    assert image.signature is not None
    assert image.signature.url == image.checksum_url
    assert image.signature.kind == "clearsigned"
    assert image.signature.fingerprint == "36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6"


def test_almalinux_signs_the_checksum_file(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["AlmaLinux-10-GenericCloud-10.2-20260817.0.x86_64.qcow2"],
    )
    distro = AlmaLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.signature is not None
    assert image.signature.url == f"{image.checksum_url}.asc"
    assert image.signature.key_url.endswith("RPM-GPG-KEY-AlmaLinux-10")
    assert image.signature.fingerprint == "EE6DB7B98F5BF5EDD9DA0DE5DEE5C11CC2A1E572"


def test_rocky_9_pins_the_release_key(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["Rocky-9-GenericCloud-Base-9.6-20260101.0.x86_64.qcow2"],
    )
    distro = RockyLinux()
    image = distro.resolve(distro.merge({}, {"release": "9"}))
    assert image.signature is not None
    assert image.signature.key_url.endswith("RPM-GPG-KEY-Rocky-9")
    assert image.signature.fingerprint == "21CB256AE16FC54C6E652949702D426D350D275D"


def test_archlinux_signs_the_downloaded_image(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: ["v20260901.583572"]
    )
    distro = ArchLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.signature is not None
    assert image.signature.url == f"{image.url}.sig"
    assert image.signature.target == "image"
    assert image.signature.key_url.startswith("https://keyserver.ubuntu.com/")


def test_debian_and_centos_have_no_upstream_signature(monkeypatch):
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: ["20260413-2447"]
    )
    debian = Debian()
    assert debian.resolve(debian.merge({}, {})).signature is None

    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["CentOS-Stream-GenericCloud-x86_64-10-20260901.0.x86_64.qcow2"],
    )
    centos = CentOSStream()
    assert centos.resolve(centos.merge({}, {})).signature is None
