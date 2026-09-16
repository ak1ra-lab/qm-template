import subprocess
from types import SimpleNamespace

import pytest

from qm_template.errors import QmTemplateError
from qm_template.shell import flatten, pretty, run


def test_flatten_joins_groups_in_order():
    groups = [["qm", "create", "9000"], ["--name", "vm"], ["--template", "1"]]
    assert flatten(groups) == [
        "qm",
        "create",
        "9000",
        "--name",
        "vm",
        "--template",
        "1",
    ]


def test_pretty_renders_one_group_per_line():
    groups = [["qm", "create", "9000"], ["--name", "my vm"], ["--template", "1"]]
    assert (
        pretty(groups) == "qm create 9000 \\\n    --name 'my vm' \\\n    --template 1"
    )


def test_pretty_keeps_a_single_group_on_one_line():
    assert pretty([["qm", "create", "9000"]]) == "qm create 9000"


def test_run_returns_the_completed_process(monkeypatch):
    monkeypatch.setattr(
        "qm_template.shell.subprocess.run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 0),
    )
    assert run(["qm", "list"]).returncode == 0


def test_run_forwards_capture(monkeypatch):
    captured: dict[str, bool] = {}

    def fake_run(argv, **_kwargs):
        captured.update(_kwargs)
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("qm_template.shell.subprocess.run", fake_run)
    run(["qm", "list"], capture=True)
    assert captured["capture_output"] is True


def test_run_reports_a_missing_executable(monkeypatch):
    def fake_run(_argv, **_kwargs):
        raise OSError("no such file")

    monkeypatch.setattr("qm_template.shell.subprocess.run", fake_run)
    with pytest.raises(QmTemplateError, match="could not run ghost"):
        run(["ghost"])
