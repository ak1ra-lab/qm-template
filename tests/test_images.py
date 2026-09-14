from pathlib import Path

import pytest

from qm_template.errors import QmTemplateError
from qm_template.images import (
    checksum_sidecar,
    find_images,
    human_size,
    orphaned_sidecars,
    superseded_images,
)


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_find_images_requires_a_directory(tmp_path: Path) -> None:
    with pytest.raises(QmTemplateError):
        find_images(tmp_path / "missing", None)
    assert find_images(tmp_path / "missing", None, required=False) == []


def test_find_images_filters_and_sorts(tmp_path: Path) -> None:
    touch(tmp_path / "b.qcow2")
    touch(tmp_path / "a.img")
    touch(tmp_path / "notes.txt")
    assert [path.name for path in find_images(tmp_path, None)] == ["a.img", "b.qcow2"]
    assert [path.name for path in find_images(tmp_path, "qcow2")] == ["b.qcow2"]


def test_find_images_includes_nested_build_directories(tmp_path: Path) -> None:
    nested = tmp_path / "debian" / "trixie" / "20260413-2447"
    touch(nested / "debian-13-genericcloud-amd64.qcow2")
    assert [path.name for path in find_images(tmp_path, None)] == [
        "debian-13-genericcloud-amd64.qcow2"
    ]
    assert find_images(tmp_path, "trixie")[0].relative_to(tmp_path) == Path(
        "debian/trixie/20260413-2447/debian-13-genericcloud-amd64.qcow2"
    )


def test_find_images_empty_directory_is_optional(tmp_path: Path) -> None:
    with pytest.raises(QmTemplateError):
        find_images(tmp_path, None)
    assert find_images(tmp_path, None, required=False) == []


def test_find_images_rejects_invalid_pattern(tmp_path: Path) -> None:
    touch(tmp_path / "a.qcow2")
    with pytest.raises(QmTemplateError):
        find_images(tmp_path, "[")


def test_human_size() -> None:
    assert human_size(0) == "0 B"
    assert human_size(1023) == "1023 B"
    assert human_size(1024) == "1.0 KiB"
    assert human_size(1536) == "1.5 KiB"
    assert human_size(1024**3) == "1.0 GiB"
    assert human_size(1024**4) == "1.0 TiB"
    assert human_size(5 * 1024**5) == "5.0 PiB"


def test_checksum_sidecar(tmp_path: Path) -> None:
    image = touch(tmp_path / "a.qcow2")
    assert checksum_sidecar(image) is None
    sidecar = touch(tmp_path / "a.qcow2.sha256")
    assert checksum_sidecar(image) == sidecar


def test_orphaned_sidecars(tmp_path: Path) -> None:
    image = touch(tmp_path / "debian" / "trixie" / "a.qcow2")
    touch(image.with_name("a.qcow2.sha256"))
    orphan = touch(tmp_path / "debian" / "trixie" / "gone.qcow2.sha512")
    assert orphaned_sidecars(tmp_path) == [orphan]


def test_superseded_prefers_newest_tag_directory(tmp_path: Path) -> None:
    old = touch(tmp_path / "ubuntu" / "resolute" / "20260705" / "resolute-server.img")
    new = touch(tmp_path / "ubuntu" / "resolute" / "20260911" / "resolute-server.img")
    assert superseded_images([old, new], tmp_path) == [old]


def test_superseded_dated_filenames(tmp_path: Path) -> None:
    old = touch(
        tmp_path
        / "debian"
        / "trixie"
        / "20260831-2587"
        / "debian-13-genericcloud-amd64-20260831-2587.qcow2"
    )
    new = touch(
        tmp_path
        / "debian"
        / "trixie"
        / "20260901-2590"
        / "debian-13-genericcloud-amd64-20260901-2590.qcow2"
    )
    assert superseded_images([old, new], tmp_path) == [old]


def test_superseded_groups_dated_release_directories(tmp_path: Path) -> None:
    old = touch(
        tmp_path / "archlinux" / "v20260615.545059" / "Arch-Linux-x86_64-cloudimg.qcow2"
    )
    new = touch(
        tmp_path / "archlinux" / "v20260901.583572" / "Arch-Linux-x86_64-cloudimg.qcow2"
    )
    assert superseded_images([old, new], tmp_path) == [old]


def test_superseded_keeps_other_variants_arches_and_releases(tmp_path: Path) -> None:
    old = touch(tmp_path / "debian" / "trixie" / "d-genericcloud-amd64-1.qcow2")
    new = touch(tmp_path / "debian" / "trixie" / "d-genericcloud-amd64-2.qcow2")
    variant = touch(tmp_path / "debian" / "trixie" / "d-generic-amd64-2.qcow2")
    arch = touch(tmp_path / "debian" / "trixie" / "d-genericcloud-arm64-2.qcow2")
    release = touch(tmp_path / "debian" / "bookworm" / "d-genericcloud-amd64-1.qcow2")
    assert superseded_images([old, new, variant, arch, release], tmp_path) == [old]


def test_superseded_uses_natural_order(tmp_path: Path) -> None:
    old = touch(
        tmp_path / "almalinux" / "10" / "AlmaLinux-10-GenericCloud-10.9-a.x86_64.qcow2"
    )
    new = touch(
        tmp_path / "almalinux" / "10" / "AlmaLinux-10-GenericCloud-10.10-a.x86_64.qcow2"
    )
    assert superseded_images([old, new], tmp_path) == [old]


def test_superseded_keeps_lone_images(tmp_path: Path) -> None:
    only = touch(tmp_path / "alpine" / "3.24" / "generic_alpine-3.24.0.qcow2")
    assert superseded_images([only], tmp_path) == []
