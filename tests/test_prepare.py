from types import SimpleNamespace

import pytest

from qm_template.errors import QmTemplateError
from qm_template.prepare import (
    DISK_FORMATS,
    convert_command,
    require_tool,
    run_tool,
    seed_iso_command,
)
from qm_template.shell import flatten


def test_convert_command_requests_the_requested_format(tmp_path):
    argv = flatten(
        convert_command(tmp_path / "in.qcow2", tmp_path / "out.vmdk", "vmdk")
    )
    assert argv[0] == "qemu-img"
    assert ["-O", "vmdk"] == argv[argv.index("-O") :][:2]
    assert str(tmp_path / "in.qcow2") in argv
    assert str(tmp_path / "out.vmdk") in argv


def test_disk_formats_map_to_distinct_suffixes():
    assert set(DISK_FORMATS) == {"vdi", "vmdk", "qcow2", "raw", "vhdx"}
    assert len(set(DISK_FORMATS.values())) == len(DISK_FORMATS)


def test_seed_iso_command_labels_cidata(tmp_path):
    sources = [
        tmp_path / "user-data",
        tmp_path / "meta-data",
        tmp_path / "network-config",
    ]
    argv = flatten(seed_iso_command(tmp_path / "seed.iso", sources))
    assert argv[0] == "genisoimage"
    assert ["-volid", "cidata"] == argv[argv.index("-volid") :][:2]
    assert str(tmp_path / "seed.iso") in argv
    for source in sources:
        assert str(source) in argv


def test_require_tool_raises_when_missing(monkeypatch):
    monkeypatch.setattr("qm_template.prepare.shutil.which", lambda _name: None)
    with pytest.raises(QmTemplateError):
        require_tool("qemu-img", package="qemu-utils")


def test_run_tool_reports_failure(monkeypatch):
    monkeypatch.setattr(
        "qm_template.prepare.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=2),
    )
    with pytest.raises(QmTemplateError, match="qemu-img"):
        run_tool([["qemu-img", "convert"]])


def test_run_tool_reports_an_execution_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise QmTemplateError("could not run qemu-img: no such file")

    monkeypatch.setattr("qm_template.prepare.run", fail)
    with pytest.raises(QmTemplateError, match="could not run"):
        run_tool([["qemu-img", "convert"]])


def test_run_tool_succeeds(monkeypatch):
    monkeypatch.setattr(
        "qm_template.prepare.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    run_tool([["qemu-img", "convert"]])
