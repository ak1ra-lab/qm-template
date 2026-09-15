from pathlib import Path

import pytest

from qm_template.errors import QmTemplateError
from qm_template.images import find_images


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_find_images_requires_a_directory(tmp_path: Path) -> None:
    with pytest.raises(QmTemplateError):
        find_images(tmp_path / "missing", None)


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


def test_find_images_rejects_an_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(QmTemplateError):
        find_images(tmp_path, None)


def test_find_images_rejects_invalid_pattern(tmp_path: Path) -> None:
    touch(tmp_path / "a.qcow2")
    with pytest.raises(QmTemplateError):
        find_images(tmp_path, "[")
