import pytest

from qm_template.download import Aria2c, Curl, Wget, select_downloaders
from qm_template.errors import QmTemplateError

URL = "https://example.com/image.qcow2"


def test_downloader_commands_include_resume_and_destination(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    for downloader in (Aria2c(), Wget(), Curl()):
        command = downloader.build_command(URL, destination)
        joined = " ".join(command)
        assert command[0] == downloader.name
        assert URL in command
        assert any("continue" in arg for arg in command)
        assert str(destination) in joined or destination.name in joined


def test_select_downloaders_rejects_empty_preference():
    with pytest.raises(QmTemplateError):
        select_downloaders([])


def test_select_downloaders_skips_unknown_names(monkeypatch):
    class FakeWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return True

    fake = FakeWget()
    monkeypatch.setattr("qm_template.download.DOWNLOADERS", {"wget": fake})
    assert select_downloaders(["nope", "wget"]) == [fake]
