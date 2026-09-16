import base64
import binascii
import hashlib
import os
import re
import tomllib
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
    TomlConfigSettingsSource,
)

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


def packaged_config_text() -> str:
    config = resources.files("qm_template") / "config.default.toml"
    return config.read_text(encoding="utf-8")


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


def _check_ssh_key(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("entries must be strings")
    stripped = value.strip()
    if not stripped.startswith(SSH_KEY_TYPE_PREFIXES) or not ssh_key_fingerprint(
        stripped
    ):
        raise ValueError(f"{value!r} does not look like an SSH public key")
    return stripped


class PathsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images_dir: Path = Field(default_factory=default_images_dir)

    @field_validator("images_dir", mode="before")
    @classmethod
    def _expand(cls, value: Any) -> Any:
        if isinstance(value, str):
            return Path(os.path.expandvars(value)).expanduser()
        return value


class DownloadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred: tuple[str, ...] = ("axel", "aria2c", "wget", "curl")
    connections: int = Field(8, ge=1)
    quiet: bool = False
    default_distro: str = "debian"
    verify_signature: bool = True

    @field_validator("default_distro")
    @classmethod
    def _known_distro(cls, value: str) -> str:
        if value not in DISTROS:
            raise ValueError(
                f"unknown distro {value!r} (run `{PROGRAM} distros` for a list)"
            )
        return value


class PrepareSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred: tuple[str, ...] = ("genisoimage", "xorriso", "mkisofs")


class DistroOverride(BaseModel):
    model_config = ConfigDict(extra="allow")


Firmware = Literal["auto", "bios", "uefi"]
FIRMWARE_VALUES: tuple[Firmware, ...] = get_args(Firmware)


class CreateSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage: str = "local-lvm"
    cores: int = Field(1, ge=1)
    memory: int = Field(1024, ge=1)
    cpu: str = "host"
    bridge: str = "vmbr0"
    firmware: Firmware = "auto"
    tags: tuple[str, ...] = ()
    pool: str | None = None
    onboot: bool = False
    description: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _split_tags(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(tag.strip() for tag in re.split(r"[,;]", value) if tag.strip())
        if isinstance(value, (list, tuple)):
            return tuple(str(tag).strip() for tag in value if str(tag).strip())
        return value


class VmidSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = Field(9000, ge=100)
    step: int = Field(1, ge=1)


class CloudInitSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: str = "debian"
    password: str = "debian"
    shell: str = "/bin/bash"
    sshkeys: tuple[str, ...] = ()
    sshkeys_files: tuple[str, ...] = ()

    @field_validator("sshkeys", mode="before")
    @classmethod
    def _ssh_keys(cls, value: Any) -> Any:
        if isinstance(value, str):
            raise ValueError("must be a list of strings")
        if isinstance(value, (list, tuple)):
            return tuple(_check_ssh_key(entry) for entry in value)
        return value

    @field_validator("sshkeys_files", mode="before")
    @classmethod
    def _string_files(cls, value: Any) -> Any:
        if isinstance(value, str):
            raise ValueError("must be a list of strings")
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value


PVE_HOST_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class PveHostSettings(BaseModel):
    """Connection to a remote Proxmox VE host plus optional per-host overrides."""

    model_config = ConfigDict(extra="forbid")

    host: str
    node: str | None = None
    user: str
    token_name: str
    token_secret: SecretStr
    verify_ssl: bool = True
    port: int = Field(8006, ge=1, le=65535)
    timeout: float = Field(30, gt=0)
    task_timeout: int = Field(3600, gt=0)
    import_storage: str | None = None
    create: CreateSettings | None = None
    vmid: VmidSettings | None = None
    cloudinit: CloudInitSettings | None = None

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        for scheme in ("https://", "http://"):
            if normalized.startswith(scheme):
                normalized = normalized[len(scheme) :].rstrip("/")
        if not normalized:
            raise ValueError("must not be empty")
        return normalized

    @field_validator("user", "token_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        env_prefix="QM_TEMPLATE_",
        env_nested_delimiter="__",
    )

    paths: PathsSettings = Field(default_factory=PathsSettings)
    download: DownloadSettings = Field(default_factory=DownloadSettings)
    prepare: PrepareSettings = Field(default_factory=PrepareSettings)
    distro: dict[str, DistroOverride] = Field(default_factory=dict)
    create: CreateSettings = Field(default_factory=CreateSettings)
    vmid: VmidSettings = Field(default_factory=VmidSettings)
    cloudinit: CloudInitSettings = Field(default_factory=CloudInitSettings)
    pve: dict[str, PveHostSettings] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_pve_hosts(self) -> "Settings":
        for name in self.pve:
            if not PVE_HOST_NAME_RE.fullmatch(name):
                raise ValueError(
                    f"invalid PVE host name {name!r} "
                    "(use letters, digits, underscores or dashes)"
                )
        return self

    @model_validator(mode="after")
    def _check_distro_overrides(self) -> "Settings":
        for name in list(self.distro):
            distro = DISTROS.get(name)
            if distro is None:
                raise ValueError(
                    f"unknown distro {name!r} (run `{PROGRAM} distros` for a list)"
                )
            normalized: dict[str, str] = {}
            for param, value in self.distro[name].model_dump(exclude_none=True).items():
                option = distro.options.get(param)
                if option is None:
                    supported = ", ".join(sorted(distro.options))
                    raise ValueError(
                        f"unknown parameter {param!r} for distro {name!r} "
                        f"(supported: {supported})"
                    )
                if not option.accepts(str(value)):
                    raise ValueError(
                        f"invalid {param} {value!r} for distro {name!r} "
                        f"({option.expectation()})"
                    )
                normalized[param] = str(value)
            self.distro[name] = DistroOverride.model_validate(normalized)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        toml_file = settings_cls.model_config.get("toml_file")
        if toml_file is not None:
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_file))
        sources.extend([dotenv_settings, file_secret_settings])
        return tuple(sources)

    def distro_overrides(self, name: str) -> dict[str, str]:
        """Return the configured overrides for a distro, without unset options."""
        override = self.distro.get(name)
        if override is None:
            return {}
        return {
            key: value
            for key, value in override.model_dump().items()
            if value is not None
        }

    def pve_host(self, name: str) -> PveHostSettings:
        """Return the configured remote Proxmox VE host by name."""
        host = self.pve.get(name)
        if host is None:
            configured = ", ".join(sorted(self.pve)) or "none configured"
            raise QmTemplateError(
                f"unknown PVE host {name!r} in [pve.*] (configured: {configured})"
            )
        return host

    @property
    def images_dir(self) -> Path:
        return self.paths.images_dir


_MOVED_KEYS = {
    ("create", "start_id"): "[vmid].start",
    ("create", "step"): "[vmid].step",
}


def _moved_to(location: tuple[Any, ...]) -> str | None:
    if location in _MOVED_KEYS:
        return _MOVED_KEYS[location]
    if len(location) == 2 and location[0] == "download":
        return f"[distro.{location[1]}]"
    return None


def _error_message(error: Mapping[str, Any], *, source: Path | None) -> str:
    where = f" in {source}" if source else ""
    location = tuple(error["loc"])
    path = ".".join(str(part) for part in location)
    if error["type"] == "extra_forbidden":
        moved = _moved_to(location)
        hint = f" (moved to {moved})" if moved else ""
        if not path:
            return f"unknown key{where}{hint}"
        return f"unknown key {path!r}{where}{hint}"
    message = str(error["msg"])
    for prefix in ("Value error, ", "Assertion failed, "):
        if message.startswith(prefix):
            message = message[len(prefix) :]
    if not path:
        return f"{message}{where}" if where else message
    return f"invalid {path!r}{where}: {message}"


def format_settings_error(
    exc: ValidationError | SettingsError | tomllib.TOMLDecodeError,
    *,
    source: Path | None,
) -> str:
    if isinstance(exc, (SettingsError, tomllib.TOMLDecodeError)):
        return f"invalid TOML in {source}: {exc}"
    errors = exc.errors()
    return "; ".join(_error_message(error, source=source) for error in errors)


def parse_settings(data: dict[str, Any], source: Path) -> Settings:
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise QmTemplateError(format_settings_error(exc, source=source)) from exc


def load_settings(path: Path, *, explicit: bool) -> Settings:
    if not path.is_file():
        if explicit:
            raise QmTemplateError(f"configuration file not found: {path}")
        log.debug("No configuration file at %s, using built-in defaults", path)
        return Settings()
    log.debug("Loading configuration from: %s", path)
    toml_settings_cls: type[Settings] = type(
        "TomlSettings",
        (Settings,),
        {"model_config": Settings.model_config | {"toml_file": path}},
    )
    try:
        return toml_settings_cls()
    except (ValidationError, SettingsError, tomllib.TOMLDecodeError) as exc:
        raise QmTemplateError(format_settings_error(exc, source=path)) from exc
