from pathlib import Path
from types import SimpleNamespace

import pytest

from qm_template.distros import RemoteImage
from qm_template.download import (
    Aria2c,
    Axel,
    Curl,
    Wget,
    download_image,
    part_path,
    select_downloader,
)
from qm_template.errors import QmTemplateError
from qm_template.shell import flatten

URL = "https://example.com/image.qcow2"


def test_downloader_commands_include_url_and_destination(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    for downloader in (Aria2c(8), Axel(8), Wget(8), Curl(8)):
        argv = flatten(downloader.build_command(URL, destination))
        joined = " ".join(argv)
        assert argv[0] == downloader.name
        assert URL in argv
        assert str(destination) in joined or destination.name in joined


def test_resumable_downloaders_include_continue(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    for downloader in (Aria2c(8), Wget(8), Curl(8)):
        argv = flatten(downloader.build_command(URL, destination))
        assert any("continue" in arg for arg in argv)


def test_connection_options_are_forwarded(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    aria2c = " ".join(flatten(Aria2c(8).build_command(URL, destination)))
    assert "--max-connection-per-server=8" in aria2c
    assert "--split=8" in aria2c
    axel = " ".join(flatten(Axel(8).build_command(URL, destination)))
    assert "--num-connections=8" in axel


def test_part_path_appends_part_suffix(tmp_path):
    assert part_path(tmp_path / "image.qcow2") == tmp_path / "image.qcow2.part"


def test_select_downloader_rejects_empty_preference():
    with pytest.raises(QmTemplateError):
        select_downloader([], 8)


def test_select_downloader_configures_connections(monkeypatch):
    class FakeWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return True

    monkeypatch.setattr("qm_template.download.DOWNLOADERS", {"wget": FakeWget})
    selected = select_downloader(["nope", "wget"], 8)
    assert isinstance(selected, FakeWget)
    assert selected.connections == 8
    assert selected.quiet is False


def test_select_downloader_prefers_the_first_available(monkeypatch):
    class FakeAxel(Axel):
        @classmethod
        def available(cls) -> bool:
            return True

    class FakeWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return True

    monkeypatch.setattr(
        "qm_template.download.DOWNLOADERS", {"axel": FakeAxel, "wget": FakeWget}
    )
    selected = select_downloader(["axel", "wget"])
    assert isinstance(selected, FakeAxel)


def test_select_downloader_forwards_quiet(monkeypatch):
    class FakeWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return True

    monkeypatch.setattr("qm_template.download.DOWNLOADERS", {"wget": FakeWget})
    selected = select_downloader(["wget"], quiet=True)
    assert selected.quiet is True


def test_select_downloader_skips_missing_binaries(monkeypatch):
    class MissingWget(Wget):
        @classmethod
        def available(cls) -> bool:
            return False

    monkeypatch.setattr("qm_template.download.DOWNLOADERS", {"wget": MissingWget})
    with pytest.raises(QmTemplateError):
        select_downloader(["wget"])


def test_quiet_downloaders_suppress_progress(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    aria2c = " ".join(flatten(Aria2c(8, quiet=True).build_command(URL, destination)))
    assert "--quiet=true" in aria2c
    axel = " ".join(flatten(Axel(8, quiet=True).build_command(URL, destination)))
    assert "--quiet" in axel
    wget = " ".join(flatten(Wget(8, quiet=True).build_command(URL, destination)))
    assert "--show-progress" not in wget
    curl = " ".join(flatten(Curl(8, quiet=True).build_command(URL, destination)))
    assert "--silent" in curl
    assert "--progress-bar" not in curl


def test_loud_downloaders_show_progress(tmp_path):
    destination = tmp_path / "image.qcow2.part"
    aria2c = " ".join(flatten(Aria2c(8).build_command(URL, destination)))
    assert "--console-log-level=warn" not in aria2c
    assert "--summary-interval=0" not in aria2c
    wget = " ".join(flatten(Wget(8).build_command(URL, destination)))
    assert "--show-progress" in wget
    curl = " ".join(flatten(Curl(8).build_command(URL, destination)))
    assert "--progress-bar" in curl


def remote_image() -> RemoteImage:
    return RemoteImage(
        distro="debian",
        release="trixie",
        filename="debian-13-genericcloud-amd64.qcow2",
        url=URL,
        checksum_url="https://example.com/SHA256SUMS",
        algorithm="sha256",
    )


class FakeDownloader:
    def __init__(self, name: str) -> None:
        self.name = name

    def build_command(self, url: str, destination: Path):
        return [[self.name, str(destination)], [url]]


def test_download_image_resumes_an_existing_part_file(monkeypatch, tmp_path):
    destination = tmp_path / "image.qcow2"
    part = part_path(destination)
    part.write_bytes(b"partial")
    calls: list[str] = []

    def fake_run(argv):
        calls.append(argv[0])
        Path(argv[1]).write_bytes(b"partial data")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("qm_template.download.subprocess.run", fake_run)
    result = download_image(remote_image(), destination, FakeDownloader("only"))
    assert result.read_bytes() == b"partial data"
    assert calls == ["only"]


def test_download_image_retries_from_scratch(monkeypatch, tmp_path):
    calls: list[str] = []
    destination = tmp_path / "image.qcow2"

    def fake_run(argv):
        calls.append(argv[0])
        if len(calls) == 1:
            Path(argv[1]).write_bytes(b"partial")
            return SimpleNamespace(returncode=1)
        Path(argv[1]).write_bytes(b"data")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("qm_template.download.subprocess.run", fake_run)
    part = download_image(remote_image(), destination, FakeDownloader("only"))
    assert part.read_bytes() == b"data"
    assert calls == ["only", "only"]


def test_download_image_raises_when_the_downloader_fails(monkeypatch, tmp_path):
    destination = tmp_path / "image.qcow2"

    def fake_run(argv):
        Path(argv[1]).write_bytes(b"partial")
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr("qm_template.download.subprocess.run", fake_run)
    with pytest.raises(QmTemplateError):
        download_image(remote_image(), destination, FakeDownloader("only"))
    assert part_path(destination).is_file()


def test_download_image_handles_missing_executable(monkeypatch, tmp_path):
    destination = tmp_path / "image.qcow2"

    def fake_run(_argv):
        raise OSError("no such file")

    monkeypatch.setattr("qm_template.download.subprocess.run", fake_run)
    with pytest.raises(QmTemplateError):
        download_image(remote_image(), destination, FakeDownloader("ghost"))


def test_download_image_rejects_empty_output(monkeypatch, tmp_path):
    destination = tmp_path / "image.qcow2"

    def fake_run(argv):
        Path(argv[1]).write_bytes(b"")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("qm_template.download.subprocess.run", fake_run)
    with pytest.raises(QmTemplateError):
        download_image(remote_image(), destination, FakeDownloader("only"))
