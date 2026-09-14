import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from qm_template.config import CreateSettings
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.pve import (
    MIN_VM_ID,
    build_qm_create,
    check_storage,
    choose_image,
    default_vm_name,
    next_vm_id,
    prompt,
    run_qm,
    sshkeys_file,
    used_vm_ids,
    vm_config_path,
)
from qm_template.shell import flatten


def test_prompt_requires_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    with pytest.raises(QmTemplateError):
        prompt("Enter VM ID: ")
    assert "Enter VM ID: " in capsys.readouterr().err


def test_default_vm_name_derives_from_image():
    assert (
        default_vm_name(Path("debian-13-genericcloud-amd64-20260831-2587.qcow2"))
        == "debian-13-genericcloud-amd64-20260831-2587"
    )


def test_default_vm_name_truncates_to_63_characters():
    name = default_vm_name(Path("a" * 80 + ".qcow2"))
    assert len(name) == 63


def test_vm_config_path():
    assert vm_config_path(9000) == Path("/etc/pve/qemu-server/9000.conf")


def test_build_qm_create_is_single_complete_command():
    settings = CreateSettings(
        storage="local-zfs",
        cores=4,
        memory=4096,
        cpu="x86-64-v2-AES",
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
    assert ["--cpu", "cputype=x86-64-v2-AES"] == argv[argv.index("--cpu") :][:2]
    assert "local-zfs:0,import-from=/images/x.qcow2" in argv
    assert "local-zfs:cloudinit" in argv
    assert "--ciuser" in argv
    assert "--sshkeys" in argv


def test_next_vm_id_skips_used_ids():
    assert next_vm_id({100, 101, 103}, 100) == 102
    assert next_vm_id({100, 101, 102}, 100) == 103


def test_next_vm_id_honours_step():
    assert next_vm_id({100, 102, 104}, 100, 2) == 106
    assert next_vm_id(set(), 9000, 10) == 9000


def test_next_vm_id_rejects_non_positive_step():
    with pytest.raises(QmTemplateError):
        next_vm_id(set(), MIN_VM_ID, 0)


def test_used_vm_ids_parses_qm_list(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="VMID NAME STATUS\n100 a running\n9000 tmpl stopped\n\n",
        ),
    )
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", Path("/nonexistent"))
    assert used_vm_ids() == {100, 9000}


def test_used_vm_ids_falls_back_to_config_directory(monkeypatch, tmp_path):
    (tmp_path / "100.conf").write_text("")
    (tmp_path / "9000.conf").write_text("")
    (tmp_path / "notes.txt").write_text("")
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", tmp_path)
    assert used_vm_ids() == {100, 9000}


def test_used_vm_ids_without_qm(monkeypatch, tmp_path):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: None)
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", tmp_path)
    assert used_vm_ids() == set()


def test_check_storage_accepts_known_storage(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/pvesm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="Name Type Status\nlocal-lvm lvm active\nlocal dir active\n",
        ),
    )
    check_storage("local-lvm")
    check_storage("local")
    with pytest.raises(QmTemplateError):
        check_storage("nope")


def test_check_storage_is_skipped_without_pvesm(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: None)
    check_storage("local-lvm")


def test_check_storage_is_skipped_when_pvesm_fails(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/pvesm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    check_storage("local-lvm")


def test_choose_image_selects_by_index(monkeypatch, tmp_path, capsys):
    images = [tmp_path / "a.qcow2", tmp_path / "b.qcow2"]
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))
    assert choose_image(images, tmp_path) == images[1]
    assert "a.qcow2" in capsys.readouterr().err


def test_choose_image_retries_invalid_selection(monkeypatch, tmp_path, capsys):
    images = [tmp_path / "a.qcow2"]
    monkeypatch.setattr("sys.stdin", io.StringIO("9\nq\n"))
    with pytest.raises(UserCancelled):
        choose_image(images, tmp_path)
    assert "Invalid selection" in capsys.readouterr().err


def test_run_qm_requires_qm(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: None)
    with pytest.raises(QmTemplateError):
        run_qm([["qm", "create", "9000"]])


def test_run_qm_reports_failure(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2),
    )
    with pytest.raises(QmTemplateError):
        run_qm([["qm", "create", "9000"]])


def test_run_qm_succeeds(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    run_qm([["qm", "create", "9000"]])


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


def test_sshkeys_invalid_inline_entry_raises():
    settings = CreateSettings(sshkeys=("not-a-key",))
    with pytest.raises(QmTemplateError):
        with sshkeys_file(settings):
            pass
