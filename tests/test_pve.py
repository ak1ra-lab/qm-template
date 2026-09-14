from pathlib import Path

import pytest

from qm_template.config import CreateSettings
from qm_template.errors import QmTemplateError
from qm_template.pve import (
    build_qm_create,
    default_vm_name,
    find_images,
    sshkeys_file,
)
from qm_template.shell import flatten


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
    assert ["qm", "create", "9000"] == command[0]
    assert flatten(command).count("qm") == 1
    assert ["--template", "1"] in command
    argv = flatten(command)
    assert "local-zfs:0,import-from=/images/x.qcow2" in argv
    assert "local-zfs:cloudinit" in argv
    assert "--ciuser" in argv
    assert "--sshkeys" in argv


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


def test_sshkeys_merges_and_dedupes_inline_and_files(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text(
        "ssh-ed25519 CCCC\n# comment\n\nssh-ed25519 AAAA alt-comment\n"
        "ssh-rsa not@base64@\n"
    )
    settings = CreateSettings(
        sshkeys=("ssh-ed25519 AAAA", "ssh-ed25519 BBBB"),
        sshkeys_files=(str(keys), str(tmp_path / "missing.pub")),
    )
    with sshkeys_file(settings) as path:
        assert (
            path.read_text() == "ssh-ed25519 AAAA\nssh-ed25519 BBBB\nssh-ed25519 CCCC\n"
        )
    assert not path.exists()


def test_sshkeys_without_inline_uses_file(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text("ssh-ed25519 CCCC\n")
    settings = CreateSettings(sshkeys=(), sshkeys_files=(str(keys),))
    with sshkeys_file(settings) as path:
        assert path.read_text() == "ssh-ed25519 CCCC\n"
    assert not path.exists()


def test_sshkeys_unreadable_file_is_skipped(tmp_path):
    settings = CreateSettings(sshkeys_files=(str(tmp_path / "missing.pub"),))
    with pytest.raises(QmTemplateError):
        with sshkeys_file(settings):
            pass


def test_sshkeys_invalid_file_line_is_skipped(tmp_path):
    keys = tmp_path / "id_ed25519.pub"
    keys.write_text("ssh-ed25519 CCCC\ngarbage line\n")
    settings = CreateSettings(sshkeys_files=(str(keys),))
    with sshkeys_file(settings) as path:
        assert path.read_text() == "ssh-ed25519 CCCC\n"


def test_sshkeys_require_a_source():
    settings = CreateSettings(sshkeys=(), sshkeys_files=())
    with pytest.raises(QmTemplateError):
        with sshkeys_file(settings):
            pass


def test_find_images_reports_missing_directory(tmp_path):
    with pytest.raises(QmTemplateError):
        find_images(tmp_path / "missing", None)
