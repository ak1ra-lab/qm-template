import pytest

from qm_template.distros import DISTROS
from qm_template.distros.archlinux import ArchLinux
from qm_template.distros.debian import Debian
from qm_template.distros.ubuntu import Ubuntu
from qm_template.errors import QmTemplateError


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


def test_archlinux_resolves_direct_url():
    distro = ArchLinux()
    image = distro.resolve(distro.merge({}, {}))
    assert image.filename == "Arch-Linux-x86_64-cloudimg.qcow2"
    assert image.url == (
        "https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
    )
    assert image.checksum_url == image.url + ".SHA256"


def test_ubuntu_rejects_unknown_variant():
    distro = Ubuntu()
    with pytest.raises(QmTemplateError):
        distro.resolve(distro.merge({}, {"variant": "desktop"}))
