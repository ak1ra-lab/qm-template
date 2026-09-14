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
