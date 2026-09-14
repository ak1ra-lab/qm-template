import os
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qm_template import PROGRAM
from qm_template.distros import DISTROS
from qm_template.errors import QmTemplateError
from qm_template.log import log


def default_config_path() -> Path:
    return Path("/etc") / PROGRAM / "config.toml"


def default_images_dir() -> Path:
    return Path("/var/lib") / PROGRAM


def resolve_config_path(cli_value: str | None) -> tuple[Path, bool]:
    if cli_value:
        return Path(cli_value).expanduser(), True
    env_value = os.environ.get("QM_TEMPLATE_CONFIG")
    if env_value:
        return Path(env_value).expanduser(), True
    return default_config_path(), False


@dataclass(frozen=True)
class DownloadSettings:
    preferred: tuple[str, ...] = ("axel", "aria2c", "wget", "curl")
    connections: int = 8
    default_distro: str = "debian"
    defaults: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class CreateSettings:
    storage: str = "local-lvm"
    cores: int = 1
    memory: int = 1024
    bridge: str = "vmbr0"
    ciuser: str = "debian"
    cipassword: str = "debian"
    sshkeys: tuple[str, ...] = ()
    sshkeys_file: str | None = "~/.ssh/id_ed25519.pub"


@dataclass(frozen=True)
class Settings:
    images_dir: Path = field(default_factory=default_images_dir)
    download: DownloadSettings = field(default_factory=DownloadSettings)
    create: CreateSettings = field(default_factory=CreateSettings)


def _table(data: Mapping[str, Any], key: str, source: Path) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise QmTemplateError(f"[{key}] must be a table in {source}")
    return value


def _str(table: Mapping[str, Any], key: str, default: str, source: Path) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise QmTemplateError(f"{key!r} must be a string in {source}")
    return value


def _optional_str(
    table: Mapping[str, Any], key: str, default: str | None, source: Path
) -> str | None:
    value = table.get(key, default)
    if value is not None and not isinstance(value, str):
        raise QmTemplateError(f"{key!r} must be a string in {source}")
    return value


def _int(table: Mapping[str, Any], key: str, default: int, source: Path) -> int:
    value = table.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise QmTemplateError(f"{key!r} must be an integer in {source}")
    return value


def _string_list(
    table: Mapping[str, Any], key: str, default: Sequence[str], source: Path
) -> tuple[str, ...]:
    value = table.get(key, default)
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise QmTemplateError(f"{key!r} must be a list of strings in {source}")
    return tuple(value)


def _parse_download(table: Mapping[str, Any], source: Path) -> DownloadSettings:
    defaults: dict[str, dict[str, str]] = {}
    for key, value in table.items():
        if key in {"preferred", "connections", "default_distro"}:
            continue
        if key not in DISTROS:
            raise QmTemplateError(
                f"unknown distro section [download.{key}] in {source}"
            )
        if not isinstance(value, dict):
            raise QmTemplateError(f"[download.{key}] must be a table in {source}")
        allowed = set(DISTROS[key].defaults) | {"tag"}
        params: dict[str, str] = {}
        for param, raw in value.items():
            if param not in allowed:
                raise QmTemplateError(
                    f"unknown parameter {param!r} in [download.{key}] of {source}"
                )
            if isinstance(raw, bool) or not isinstance(raw, (str, int)):
                raise QmTemplateError(
                    f"[download.{key}].{param} must be a string or integer in {source}"
                )
            params[param] = str(raw)
        defaults[key] = params
    connections = _int(table, "connections", 8, source)
    if connections < 1:
        raise QmTemplateError(f"'connections' must be a positive integer in {source}")
    return DownloadSettings(
        preferred=_string_list(
            table, "preferred", ("axel", "aria2c", "wget", "curl"), source
        ),
        connections=connections,
        default_distro=_str(table, "default_distro", "debian", source),
        defaults=defaults,
    )


def _parse_create(table: Mapping[str, Any], source: Path) -> CreateSettings:
    return CreateSettings(
        storage=_str(table, "storage", "local-lvm", source),
        cores=_int(table, "cores", 1, source),
        memory=_int(table, "memory", 1024, source),
        bridge=_str(table, "bridge", "vmbr0", source),
        ciuser=_str(table, "ciuser", "debian", source),
        cipassword=_str(table, "cipassword", "debian", source),
        sshkeys=_string_list(table, "sshkeys", (), source),
        sshkeys_file=_optional_str(
            table, "sshkeys_file", "~/.ssh/id_ed25519.pub", source
        ),
    )


def parse_settings(data: Mapping[str, Any], source: Path) -> Settings:
    paths = _table(data, "paths", source)
    images_dir_value = _str(paths, "images_dir", str(default_images_dir()), source)
    images_dir = Path(os.path.expandvars(images_dir_value)).expanduser()
    return Settings(
        images_dir=images_dir,
        download=_parse_download(_table(data, "download", source), source),
        create=_parse_create(_table(data, "create", source), source),
    )


def load_settings(path: Path, *, explicit: bool) -> Settings:
    if not path.is_file():
        if explicit:
            raise QmTemplateError(f"configuration file not found: {path}")
        log.debug("No configuration file at %s, using built-in defaults", path)
        return Settings()
    log.debug("Loading configuration from: %s", path)
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise QmTemplateError(f"invalid TOML in {path}: {exc}") from exc
    return parse_settings(data, source=path)
