import importlib
import importlib.metadata
import runpy
import sys

import pytest

import qm_template


def test_version_falls_back_when_package_is_not_installed(monkeypatch):
    def raise_not_found(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", raise_not_found)
    reloaded = importlib.reload(qm_template)
    try:
        assert reloaded.__version__ == "0.0.0"
    finally:
        monkeypatch.undo()
        importlib.reload(qm_template)
    assert qm_template.__version__ != "0.0.0"


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize("module", ["qm_template.__main__", "qm_template.cli"])
def test_main_module_prints_version(monkeypatch, module, capsys):
    monkeypatch.setattr(sys, "argv", ["qm-template", "--version"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(module, run_name="__main__")
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("qm-template ")
