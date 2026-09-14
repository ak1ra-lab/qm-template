import base64
import binascii
import hashlib
import os
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
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


def _packaged_config_text() -> str:
    config = resources.files("qm_template") / "config.default.toml"
    return config.read_text(encoding="utf-8")


def write_default_config(path: Path) -> bool:
    """Write the packaged default configuration unless a file already exists."""
    if path.exists():
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_packaged_config_text(), encoding="utf-8")
    except OSError as exc:
        log.debug("Could not write default configuration to %s: %s", path, exc)
        return False
    log.info("Wrote default configuration to %s", path)
    return True


@dataclass(frozen=True)
class DownloadSettings:
    preferred: tuple[str, ...] = ("axel", "aria2c", "wget", "curl")
    connections: int = 8
    quiet: bool = False
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
    sshkeys_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class Settings:
    images_dir: Path = field(default_factory=default_images_dir)
    download: DownloadSettings = field(default_factory=DownloadSettings)
    create: CreateSettings = field(default_factory=CreateSettings)


_DOWNLOAD_DEFAULTS = DownloadSettings()
_CREATE_DEFAULTS = CreateSettings()
_DOWNLOAD_KEYS = frozenset(DownloadSettings.__dataclass_fields__) - {"defaults"}
_CREATE_KEYS = frozenset(CreateSettings.__dataclass_fields__)


def _table(data: Mapping[str, Any], key: str, source: Path) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise QmTemplateError(f"[{key}] must be a table in {source}")
    return value


def _reject_unknown(
    table: Mapping[str, Any],
    allowed: set[str] | frozenset[str],
    section: str | None,
    source: Path,
) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        names = ", ".join(repr(key) for key in unknown)
        where = f"in [{section}]" if section else "at the top level"
        raise QmTemplateError(f"unknown keys {names} {where} of {source}")


def _str(table: Mapping[str, Any], key: str, default: str, source: Path) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise QmTemplateError(f"{key!r} must be a string in {source}")
    return value


def _int(table: Mapping[str, Any], key: str, default: int, source: Path) -> int:
    value = table.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise QmTemplateError(f"{key!r} must be an integer in {source}")
    return value


def _bool(table: Mapping[str, Any], key: str, default: bool, source: Path) -> bool:
    value = table.get(key, default)
    if not isinstance(value, bool):
        raise QmTemplateError(f"{key!r} must be a boolean in {source}")
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


SSH_KEY_TYPE_PREFIXES = ("ssh-", "ecdsa-sha2-", "sk-")


def ssh_key_fingerprint(line: str) -> str | None:
    fields = line.split()
    if len(fields) < 2:
        return None
    try:
        blob = base64.b64decode(fields[1], validate=True)
    except binascii.Error:
        return None
    digest = hashlib.sha256(blob).digest()
    return base64.b64encode(digest).rstrip(b"=").decode("ascii")


def _ssh_keys(table: Mapping[str, Any], key: str, source: Path) -> tuple[str, ...]:
    keys: list[str] = []
    for value in _string_list(table, key, _CREATE_DEFAULTS.sshkeys, source):
        stripped = value.strip()
        if not stripped.startswith(SSH_KEY_TYPE_PREFIXES) or not ssh_key_fingerprint(
            stripped
        ):
            raise QmTemplateError(
                f"{key!r} entry {value!r} does not look like an SSH public key "
                f"in {source}"
            )
        keys.append(stripped)
    return tuple(keys)


def _parse_download(table: Mapping[str, Any], source: Path) -> DownloadSettings:
    _reject_unknown(table, _DOWNLOAD_KEYS | set(DISTROS), "download", source)
    defaults: dict[str, dict[str, str]] = {}
    for key, value in table.items():
        if key in _DOWNLOAD_KEYS:
            continue
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
    connections = _int(table, "connections", _DOWNLOAD_DEFAULTS.connections, source)
    if connections < 1:
        raise QmTemplateError(f"'connections' must be a positive integer in {source}")
    return DownloadSettings(
        preferred=_string_list(
            table, "preferred", _DOWNLOAD_DEFAULTS.preferred, source
        ),
        connections=connections,
        quiet=_bool(table, "quiet", _DOWNLOAD_DEFAULTS.quiet, source),
        default_distro=_str(
            table, "default_distro", _DOWNLOAD_DEFAULTS.default_distro, source
        ),
        defaults=defaults,
    )


def _parse_create(table: Mapping[str, Any], source: Path) -> CreateSettings:
    _reject_unknown(table, _CREATE_KEYS, "create", source)
    return CreateSettings(
        storage=_str(table, "storage", _CREATE_DEFAULTS.storage, source),
        cores=_int(table, "cores", _CREATE_DEFAULTS.cores, source),
        memory=_int(table, "memory", _CREATE_DEFAULTS.memory, source),
        bridge=_str(table, "bridge", _CREATE_DEFAULTS.bridge, source),
        ciuser=_str(table, "ciuser", _CREATE_DEFAULTS.ciuser, source),
        cipassword=_str(table, "cipassword", _CREATE_DEFAULTS.cipassword, source),
        sshkeys=_ssh_keys(table, "sshkeys", source),
        sshkeys_files=_string_list(
            table, "sshkeys_files", _CREATE_DEFAULTS.sshkeys_files, source
        ),
    )


def parse_settings(data: Mapping[str, Any], source: Path) -> Settings:
    _reject_unknown(data, {"paths", "download", "create"}, None, source)
    paths = _table(data, "paths", source)
    _reject_unknown(paths, {"images_dir"}, "paths", source)
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
