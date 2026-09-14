from pathlib import Path

import pytest

from qm_template.config import CreateSettings
from qm_template.errors import QmTemplateError
from qm_template.pve import build_qm_create, default_vm_name, find_images


def test_default_vm_name_derives_from_image():
    assert (
        default_vm_name(Path("debian-13-genericcloud-amd64-20260831-2587.qcow2"))
        == "debian-13-genericcloud-amd64-20260831-2587"
    )


def test_default_vm_name_truncates_to_63_characters():
    name = default_vm_name(Path("a" * 80 + ".qcow2"))
    assert len(name) == 63


def test_build_qm_create_is_single_complete_command():
    settings = CreateSettings(
        storage="local-zfs",
        cores=4,
        memory=4096,
        bridge="vmbr1",
        ciuser="admin",
        cipassword="secret",
    )
    command = build_qm_create(
        9000, "debian-template", Path("/images/x.qcow2"), Path("/keys.pub"), settings
    )
    assert command[:3] == ["qm", "create", "9000"]
    assert command.count("qm") == 1
    assert "local-zfs:0,import-from=/images/x.qcow2" in command
    assert "local-zfs:cloudinit" in command
    assert command[command.index("--template") + 1] == "1"
    assert "--ciuser" in command
    assert "--sshkeys" in command


def test_find_images_filters_and_sorts(tmp_path):
    (tmp_path / "b.qcow2").write_bytes(b"")
    (tmp_path / "a.img").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("")
    assert [p.name for p in find_images(tmp_path, None)] == ["a.img", "b.qcow2"]
    assert [p.name for p in find_images(tmp_path, "qcow2")] == ["b.qcow2"]


def test_find_images_includes_nested_build_directories(tmp_path):
    nested = tmp_path / "debian" / "trixie" / "20260413-2447"
    nested.mkdir(parents=True)
    (nested / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    assert [p.name for p in find_images(tmp_path, None)] == [
        "debian-13-genericcloud-amd64.qcow2"
    ]
    assert find_images(tmp_path, "trixie")[0].relative_to(tmp_path) == Path(
        "debian/trixie/20260413-2447/debian-13-genericcloud-amd64.qcow2"
    )


def test_find_images_reports_missing_directory(tmp_path):
    with pytest.raises(QmTemplateError):
        find_images(tmp_path / "missing", None)
