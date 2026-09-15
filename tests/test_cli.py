import hashlib
import io
from pathlib import Path

import pytest

from qm_template.cli import build_parser, main
from qm_template.download import part_path
from qm_template.errors import QmTemplateError


def write_config(tmp_path: Path, images_dir: Path, create: str = "") -> Path:
    config = tmp_path / "config.toml"
    config.write_text(
        f'[paths]\nimages_dir = "{images_dir}"\n[create]\n{create}',
    )
    return config


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("qm-template ")


def test_keyboard_interrupt_returns_130(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("")

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("qm_template.cli.load_settings", interrupt)
    assert main(["distros", "--config", str(config)]) == 130
    assert "Interrupted" in capsys.readouterr().err


def test_distros_command_lists_supported_distros(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("")
    assert main(["distros", "--config", str(config)]) == 0
    output = capsys.readouterr().out
    assert "debian" in output
    assert "ubuntu" in output


def test_first_run_writes_default_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "etc" / "config.toml"
    monkeypatch.setattr("qm_template.config.default_config_path", lambda: target)
    monkeypatch.delenv("QM_TEMPLATE_CONFIG", raising=False)
    assert main(["distros"]) == 0
    assert target.is_file()
    assert "debian" in capsys.readouterr().out


def test_unknown_distro_returns_error(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("")
    assert main(["download", "unknown", "--config", str(config)]) == 1


def test_download_dry_run_prints_first_downloader_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/downloader")
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"],
    )
    config = tmp_path / "config.toml"
    config.write_text("")
    assert main(["download", "alpine", "--dry-run", "--config", str(config)]) == 0
    output = capsys.readouterr().out
    assert output.startswith("axel \\\n")
    assert "    --num-connections=8 \\\n" in output
    assert output.rstrip().endswith(
        "generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"
    )


def test_create_dry_run_prints_pretty_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = tmp_path / "config.toml"
    config.write_text(
        f'[paths]\nimages_dir = "{images}"\n[create]\nsshkeys = ["ssh-ed25519 AAAA"]\n'
    )
    monkeypatch.setattr(
        "qm_template.commands.vm_config_path",
        lambda vm_id: tmp_path / f"{vm_id}.conf",
    )
    monkeypatch.setattr("qm_template.commands.check_storage", lambda _storage: None)
    assert (
        main(["create", "--dry-run", "--vm-id", "9000", "--config", str(config)]) == 0
    )
    output = capsys.readouterr().out
    assert output.startswith("qm create 9000 \\\n")
    assert "    --name debian-13-genericcloud-amd64 \\\n" in output
    assert output.rstrip().endswith("--template 1")


def test_create_picks_next_free_vm_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(
        tmp_path,
        images,
        'sshkeys = ["ssh-ed25519 AAAA"]\nstart_id = 9000\nstep = 5\n',
    )
    monkeypatch.setattr("qm_template.commands.used_vm_ids", lambda: {9000, 9005})
    monkeypatch.setattr("qm_template.commands.check_storage", lambda _storage: None)
    monkeypatch.setattr(
        "qm_template.commands.vm_config_path", lambda vm_id: tmp_path / f"{vm_id}.conf"
    )
    assert main(["create", "--dry-run", "--config", str(config)]) == 0
    assert capsys.readouterr().out.startswith("qm create 9010 \\\n")


def test_create_rejects_an_used_vm_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    existing = tmp_path / "9000.conf"
    existing.write_text("")
    monkeypatch.setattr("qm_template.commands.vm_config_path", lambda vm_id: existing)
    assert main(["create", "--vm-id", "9000", "--config", str(config)]) == 1


def test_create_rejects_invalid_resource_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    assert main(["create", "--cores", "0", "--config", str(config)]) == 1
    assert "cores must be a positive integer" in capsys.readouterr().err
    assert main(["create", "--memory", "0", "--config", str(config)]) == 1
    assert "memory must be a positive integer" in capsys.readouterr().err


def test_create_rejects_invalid_start_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(
        tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\nstart_id = 50\n'
    )
    assert main(["create", "--config", str(config)]) == 1
    assert "start ID must be at least 100" in capsys.readouterr().err
    config = write_config(
        tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\nstep = 0\n'
    )
    assert main(["create", "--config", str(config)]) == 1
    assert "step must be a positive integer" in capsys.readouterr().err


def test_create_reports_a_partially_created_vm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    missing = tmp_path / "missing.conf"
    created = tmp_path / "9000.conf"
    state = {"created": False}

    def fake_config_path(_vm_id: int) -> Path:
        return created if state["created"] else missing

    def fake_run_qm(_command) -> None:
        state["created"] = True
        created.write_text("")
        raise QmTemplateError("qm create failed with exit status 1")

    monkeypatch.setattr("qm_template.commands.vm_config_path", fake_config_path)
    monkeypatch.setattr("qm_template.commands.check_storage", lambda _storage: None)
    monkeypatch.setattr("qm_template.commands.run_qm", fake_run_qm)
    assert main(["create", "--vm-id", "9000", "--config", str(config)]) == 1
    assert "qm destroy 9000" in capsys.readouterr().err


def test_download_dry_run_respects_quiet(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/downloader")
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"],
    )
    config = tmp_path / "config.toml"
    config.write_text("")
    assert (
        main(["download", "alpine", "--quiet", "--dry-run", "--config", str(config)])
        == 0
    )
    assert "    --quiet \\\n" in capsys.readouterr().out


def test_download_skips_an_already_verified_image(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    filename = "generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"
    image = images / "alpine" / "3.24" / filename
    image.parent.mkdir(parents=True)
    image.write_bytes(b"cloud image")
    digest = hashlib.file_digest(image.open("rb"), "sha512").hexdigest()
    config = write_config(tmp_path, images)
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: [filename]
    )
    monkeypatch.setattr(
        "qm_template.commands.fetch_checksum", lambda _url, _name: digest
    )
    monkeypatch.setattr(
        "qm_template.commands.select_downloader", lambda *_args, **_kwargs: None
    )
    assert main(["download", "alpine", "--config", str(config)]) == 0
    captured = capsys.readouterr()
    assert "Already up to date" in captured.err
    assert image.with_name(image.name + ".sha512").read_text().startswith(digest)


def test_download_ignores_tag_for_unsupported_distro(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/downloader")
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory",
        lambda _url: ["generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"],
    )
    config = tmp_path / "config.toml"
    config.write_text("")
    assert (
        main(["download", "alpine", "--tag", "x", "--dry-run", "--config", str(config)])
        == 0
    )
    assert "does not support --tag" in capsys.readouterr().err


def test_download_replaces_a_corrupt_existing_image(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    filename = "generic_alpine-3.24.0-x86_64-bios-cloudinit-r0.qcow2"
    image = images / "alpine" / "3.24" / filename
    image.parent.mkdir(parents=True)
    image.write_bytes(b"corrupt")
    digest = hashlib.sha512(b"good").hexdigest()
    config = write_config(tmp_path, images)
    monkeypatch.setattr(
        "qm_template.distros.base.list_directory", lambda _url: [filename]
    )
    monkeypatch.setattr(
        "qm_template.commands.fetch_checksum", lambda _url, _name: digest
    )
    monkeypatch.setattr(
        "qm_template.commands.select_downloader", lambda *_args, **_kwargs: None
    )

    def fake_verified(_image, destination, _downloader, _expected):
        part = part_path(destination)
        part.write_bytes(b"good")
        return part

    monkeypatch.setattr("qm_template.commands._download_verified", fake_verified)
    assert main(["download", "alpine", "--config", str(config)]) == 0
    captured = capsys.readouterr()
    assert "Checksum mismatch" in captured.err
    assert "Saved" in captured.err
    assert image.read_bytes() == b"good"
    assert image.with_name(image.name + ".sha512").is_file()


def test_create_prompts_when_multiple_images_match(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    (images / "debian-12-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))
    monkeypatch.setattr("qm_template.commands.check_storage", lambda _storage: None)
    monkeypatch.setattr(
        "qm_template.commands.vm_config_path", lambda vm_id: tmp_path / f"{vm_id}.conf"
    )
    assert (
        main(["create", "--dry-run", "--vm-id", "9000", "--config", str(config)]) == 0
    )
    assert "--name debian-13-genericcloud-amd64" in capsys.readouterr().out


def test_create_rejects_vm_id_below_minimum(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    assert main(["create", "--vm-id", "50", "--config", str(config)]) == 1
    assert "VM ID must be at least 100" in capsys.readouterr().err


def test_create_reports_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "debian-13-genericcloud-amd64.qcow2").write_bytes(b"")
    config = write_config(tmp_path, images, 'sshkeys = ["ssh-ed25519 AAAA"]\n')
    monkeypatch.setattr("qm_template.commands.check_storage", lambda _storage: None)
    monkeypatch.setattr(
        "qm_template.commands.vm_config_path", lambda vm_id: tmp_path / f"{vm_id}.conf"
    )
    monkeypatch.setattr("qm_template.commands.run_qm", lambda _command: None)
    assert main(["create", "--vm-id", "9000", "--config", str(config)]) == 0
    assert "created" in capsys.readouterr().err
