import pytest

from qm_template.download import Aria2c, Axel, Curl, Wget, select_downloaders
from qm_template.errors import QmTemplateError

URL = "https://example.com/image.qcow2"


def test_downloader_commands_include_url_and_destination(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    for downloader in (Aria2c(8), Axel(8), Wget(8), Curl(8)):
        command = downloader.build_command(URL, destination)
        joined = " ".join(command)
        assert command[0] == downloader.name
        assert URL in command
        assert str(destination) in joined or destination.name in joined


def test_resumable_downloaders_include_continue(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    for downloader in (Aria2c(8), Wget(8), Curl(8)):
        command = downloader.build_command(URL, destination)
        assert any("continue" in arg for arg in command)


def test_connection_options_are_forwarded(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    aria2c = " ".join(Aria2c(8).build_command(URL, destination))
    assert "--max-connection-per-server=8" in aria2c
    assert "--split=8" in aria2c
    axel = " ".join(Axel(8).build_command(URL, destination))
    assert "--num-connections=8" in axel


def test_select_downloaders_rejects_empty_preference():
    with pytest.raises(QmTemplateError):
        select_downloaders([], 8)


def test_select_downloaders_configures_connections(monkeypatch):
    class FakeWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return True

    monkeypatch.setattr("qm_template.download.DOWNLOADERS", {"wget": FakeWget})
    selected = select_downloaders(["nope", "wget"], 8)
    assert len(selected) == 1
    assert isinstance(selected[0], FakeWget)
    assert selected[0].connections == 8
