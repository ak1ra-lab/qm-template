from pathlib import Path

import pytest

from qm_template.cli import build_parser, main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("qm-template ")


def test_distros_command_lists_supported_distros(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("")
    assert main(["distros", "--config", str(config)]) == 0
    output = capsys.readouterr().out
    assert "debian" in output
    assert "ubuntu" in output


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
