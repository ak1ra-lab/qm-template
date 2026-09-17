import io
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from qm_template.config import CloudInitSettings, CreateSettings
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.pve import (
    MIN_VM_ID,
    VmSpec,
    build_qm_create,
    check_storage,
    choose_image,
    default_vm_name,
    detect_firmware,
    mask_secrets,
    next_vm_id,
    prompt,
    run_qm,
    used_vm_ids,
    vm_config_path,
)
from qm_template.shell import MASK, flatten


def make_spec(**overrides) -> VmSpec:
    values: dict = {
        "vm_id": 9000,
        "name": "debian-template",
        "image": Path("/images/x.qcow2"),
        "firmware": "bios",
        "create": CreateSettings(),
        "cloudinit": CloudInitSettings(),
        "sshkeys": ("ssh-ed25519 AAAA",),
    }
    values.update(overrides)
    return VmSpec(**values)


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
    spec = make_spec(
        create=CreateSettings(
            storage="local-zfs",
            cores=4,
            memory=4096,
            cpu="x86-64-v2-AES",
            bridge="vmbr1",
        ),
        cloudinit=CloudInitSettings(user="admin", password="secret"),
    )
    command = build_qm_create(spec, "/images/x.qcow2", Path("/keys.pub"))
    assert ["qm", "create", "9000"] == command[0]
    assert flatten(command).count("qm") == 1
    assert ["--template", "1"] in command
    argv = flatten(command)
    assert ["--cpu", "cputype=x86-64-v2-AES"] == argv[argv.index("--cpu") :][:2]
    assert "local-zfs:0,import-from=/images/x.qcow2" in argv
    assert "local-zfs:cloudinit" in argv
    assert ["--ciuser", "admin"] == argv[argv.index("--ciuser") :][:2]
    assert ["--cipassword", "secret"] == argv[argv.index("--cipassword") :][:2]
    assert ["--sshkeys", "/keys.pub"] == argv[argv.index("--sshkeys") :][:2]
    assert "--bios" not in argv
    assert "--efidisk0" not in argv


def test_build_qm_create_omits_empty_credentials():
    spec = make_spec(
        cloudinit=CloudInitSettings(user="admin"),
        sshkeys=(),
    )
    argv = flatten(build_qm_create(spec, "/images/x.qcow2", Path("/keys.pub")))
    assert "--cipassword" not in argv
    assert "--sshkeys" not in argv


def test_mask_secrets_hides_the_password():
    command = [["qm", "create", "9000"], ["--cipassword", "secret"], ["--name", "vm"]]
    masked = mask_secrets(command)
    assert masked == [
        ["qm", "create", "9000"],
        ["--cipassword", MASK],
        ["--name", "vm"],
    ]
    assert "secret" not in flatten(masked)


def test_detect_firmware_reads_the_image_name():
    assert detect_firmware(Path("debian-13-genericcloud-amd64.qcow2")) == "bios"
    assert (
        detect_firmware(Path("Fedora-Cloud-Base-UEFI-UKI-44-1.7.x86_64.qcow2"))
        == "uefi"
    )
    assert (
        detect_firmware(Path("generic_alpine-3.24.1-aarch64-uefi-cloudinit-r0.qcow2"))
        == "uefi"
    )


def test_build_qm_create_omits_metadata_by_default():
    command = build_qm_create(make_spec(), "/images/x.qcow2", Path("/keys.pub"))
    argv = flatten(command)
    for flag in ("--tags", "--pool", "--onboot", "--description"):
        assert flag not in argv


def test_build_qm_create_adds_metadata():
    spec = make_spec(
        create=CreateSettings(
            tags=("template", "cloud"),
            pool="templates",
            onboot=True,
            description="Debian 13 cloud template",
        )
    )
    command = build_qm_create(spec, "/images/x.qcow2", Path("/keys.pub"))
    argv = flatten(command)
    assert ["--tags", "template;cloud"] == argv[argv.index("--tags") :][:2]
    assert ["--pool", "templates"] == argv[argv.index("--pool") :][:2]
    assert ["--onboot", "1"] == argv[argv.index("--onboot") :][:2]
    assert ["--description", "Debian 13 cloud template"] == argv[
        argv.index("--description") :
    ][:2]


def test_build_qm_create_uefi_adds_ovmf_and_efidisk():
    spec = make_spec(
        name="fedora-uki",
        image=Path("/images/f.qcow2"),
        firmware="uefi",
        create=CreateSettings(storage="local-zfs"),
    )
    command = build_qm_create(spec, "/images/f.qcow2", Path("/keys.pub"))
    argv = flatten(command)
    assert ["--bios", "ovmf"] == argv[argv.index("--bios") :][:2]
    assert ["--efidisk0", "local-zfs:1,pre-enrolled-keys=0"] == argv[
        argv.index("--efidisk0") :
    ][:2]


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
        "qm_template.pve.run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="VMID NAME STATUS\n100 a running\n9000 tmpl stopped\n\n",
        ),
    )
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", Path("/nonexistent"))
    assert used_vm_ids() == {100, 9000}


def test_used_vm_ids_merges_the_config_directory(monkeypatch, tmp_path):
    (tmp_path / "100.conf").write_text("")
    (tmp_path / "9000.conf").write_text("")
    (tmp_path / "notes.txt").write_text("")
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", tmp_path)
    assert used_vm_ids() == {100, 9000}


def test_used_vm_ids_ignores_an_execution_failure(monkeypatch, tmp_path):
    (tmp_path / "100.conf").write_text("")

    def fail(*_args, **_kwargs):
        raise QmTemplateError("could not run qm: no such file")

    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr("qm_template.pve.run", fail)
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", tmp_path)
    assert used_vm_ids() == {100}


def test_used_vm_ids_without_qm(monkeypatch, tmp_path):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: None)
    monkeypatch.setattr("qm_template.pve.PVE_VM_DIR", tmp_path)
    assert used_vm_ids() == set()


def test_check_storage_accepts_known_storage(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/pvesm")
    monkeypatch.setattr(
        "qm_template.pve.run",
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
        "qm_template.pve.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    check_storage("local-lvm")


def test_check_storage_is_skipped_when_pvesm_cannot_run(monkeypatch):
    def fail(*_args, **_kwargs):
        raise QmTemplateError("could not run pvesm: no such file")

    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/pvesm")
    monkeypatch.setattr("qm_template.pve.run", fail)
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
        "qm_template.pve.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2),
    )
    with pytest.raises(QmTemplateError, match="qm create failed with exit status 2"):
        run_qm([["qm", "create", "9000"]])


def test_run_qm_reports_an_execution_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise QmTemplateError("could not run /usr/bin/qm: no such file")

    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr("qm_template.pve.run", fail)
    with pytest.raises(QmTemplateError, match="could not run"):
        run_qm([["qm", "create", "9000"]])


def test_run_qm_succeeds(monkeypatch):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.pve.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    run_qm([["qm", "create", "9000"]])


def test_run_qm_masks_the_password_in_debug_logs(monkeypatch, caplog):
    monkeypatch.setattr("qm_template.pve.shutil.which", lambda _name: "/usr/bin/qm")
    monkeypatch.setattr(
        "qm_template.shell.subprocess.run",
        lambda argv, **_kwargs: SimpleNamespace(returncode=0),
    )
    with caplog.at_level(logging.DEBUG, logger="qm-template"):
        run_qm([["qm", "create", "9000"], ["--cipassword", "secret"]])
    assert "secret" not in caplog.text
    assert MASK in caplog.text
