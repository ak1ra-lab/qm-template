import argparse
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from qm_template import PROGRAM
from qm_template.api import ApiPveTarget
from qm_template.checksum import (
    fetch_checksum,
    read_checksum,
    save_checksum,
    verify_checksum,
)
from qm_template.cloudinit import (
    meta_data,
    network_config,
    require_ssh_keys,
    user_data,
)
from qm_template.config import (
    FIRMWARE_VALUES,
    CloudInitSettings,
    CreateSettings,
    Settings,
    VmidSettings,
    load_settings,
    packaged_config_text,
    resolve_config_path,
)
from qm_template.distros import DISTROS, RemoteImage
from qm_template.download import (
    Downloader,
    download_image,
    extract_image,
    part_path,
    select_downloader,
)
from qm_template.errors import QmTemplateError
from qm_template.images import find_images
from qm_template.log import log
from qm_template.prepare import (
    DEFAULT_FORMAT,
    DISK_FORMATS,
    QEMU_IMG,
    convert_command,
    require_tool,
    run_tool,
    select_iso_builder,
)
from qm_template.pve import (
    MIN_VM_ID,
    LocalPveTarget,
    PveTarget,
    ResolvedFirmware,
    VmSpec,
    choose_image,
    default_vm_name,
    detect_firmware,
)
from qm_template.shell import pretty
from qm_template.signature import verify_image

Model = TypeVar("Model", bound=BaseModel)


def _set_completer(
    action: argparse.Action, completer: Callable[..., list[str]]
) -> None:
    setattr(action, "completer", completer)


def _complete_distro_names(prefix: str = "", **_: Any) -> list[str]:
    return [name for name in DISTROS if name.startswith(prefix)]


def _complete_distro_option(param: str) -> Callable[..., list[str]]:
    def complete(
        prefix: str = "", parsed_args: argparse.Namespace | None = None, **_: Any
    ) -> list[str]:
        name = getattr(parsed_args, "distro", None)
        distro = DISTROS.get(name) if isinstance(name, str) else None
        if distro is None:
            return []
        option = distro.options.get(param)
        return [] if option is None else option.completions(prefix)

    return complete


def _complete_pve_names(
    prefix: str = "", parsed_args: argparse.Namespace | None = None, **_: Any
) -> list[str]:
    path, explicit = resolve_config_path(getattr(parsed_args, "config", None))
    try:
        settings = load_settings(path, explicit=explicit)
    except QmTemplateError:
        return []
    return [name for name in settings.pve if name.startswith(prefix)]


CLI_OPTION_NAMES = tuple(
    sorted(
        {
            name
            for distro in DISTROS.values()
            for name, option in distro.options.items()
            if option.cli
        }
    )
)

DOWNLOAD_OPTION_HELP = {
    "release": "distro release or codename",
    "variant": "image variant",
    "arch": "image architecture",
    "tag": "specific image tag/version",
}


def _download_option_help(name: str) -> str:
    if name in DOWNLOAD_OPTION_HELP:
        return DOWNLOAD_OPTION_HELP[name]
    notes = {
        option.note
        for distro in DISTROS.values()
        if (option := distro.options.get(name)) and option.note
    }
    if len(notes) == 1:
        return notes.pop()
    return f"distro-specific parameter (see `{PROGRAM} distros <distro>`)"


def add_download_arguments(parser: argparse.ArgumentParser) -> None:
    distro_argument = parser.add_argument(
        "distro",
        nargs="?",
        help="distro name (default from configuration)",
    )
    _set_completer(distro_argument, _complete_distro_names)
    for name in CLI_OPTION_NAMES:
        action = parser.add_argument(
            f"--{name.replace('_', '-')}",
            help=_download_option_help(name),
        )
        _set_completer(action, _complete_distro_option(name))
    parser.add_argument(
        "-q",
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="hide downloader progress output",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print the download command and exit",
    )


def _download_verified(
    image: RemoteImage,
    destination: Path,
    downloader: Downloader,
    expected: str,
) -> Path:
    for attempt in range(1, 3):
        if attempt > 1:
            log.warning("Checksum mismatch, downloading again from scratch")
        part = download_image(image, destination, downloader)
        log.info("Verifying checksum")
        if verify_checksum(part, expected, image.algorithm):
            return part
        part.unlink(missing_ok=True)
    raise QmTemplateError("downloaded image failed checksum verification")


def _extract(archive: Path, image: RemoteImage) -> Path:
    target, digest = extract_image(archive, image)
    save_checksum(target, digest, "sha256")
    archive.unlink(missing_ok=True)
    return target


def run_download(args: argparse.Namespace, settings: Settings) -> None:
    name = args.distro or settings.download.default_distro
    distro = DISTROS.get(name)
    if distro is None:
        raise QmTemplateError(
            f"unknown distro {name!r} (run `{PROGRAM} distros` for a list)"
        )
    if args.tag and not distro.options.get("tag"):
        raise QmTemplateError(
            f"{distro.name} does not support --tag "
            f"(run `{PROGRAM} distros {distro.name}` for the supported options)"
        )
    overrides = {
        name: value
        for name in CLI_OPTION_NAMES
        if (value := getattr(args, name, None)) is not None
    }
    params = distro.merge(settings.distro_overrides(distro.name), overrides)
    image = distro.resolve(params)
    log.info("Image: %s", image.local_path)
    log.debug("URL: %s", image.url)
    log.debug("Checksum: %s (%s)", image.checksum_url, image.algorithm)
    destination = settings.images_dir / image.local_path
    quiet = settings.download.quiet if args.quiet is None else args.quiet
    downloader = select_downloader(
        settings.download.preferred, settings.download.connections, quiet=quiet
    )
    if args.dry_run:
        print(pretty(downloader.build_command(image.url, part_path(destination))))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if image.compression is not None:
        extracted = destination.with_name(image.extracted_name)
        digest = read_checksum(extracted, "sha256")
        if digest is not None and verify_checksum(extracted, digest, "sha256"):
            log.info("Already up to date: %s", extracted)
            return
    expected = fetch_checksum(
        image.checksum_url,
        image.filename,
        signature=image.signature,
        verify=settings.download.verify_signature,
    )
    if destination.is_file():
        if verify_checksum(destination, expected, image.algorithm):
            if image.compression is None:
                save_checksum(destination, expected, image.algorithm)
                log.info("Already up to date: %s", destination)
            else:
                _extract(destination, image)
            return
        log.warning("Checksum mismatch for %s, removing it", destination)
        destination.unlink()
    part = _download_verified(image, destination, downloader, expected)
    if (
        settings.download.verify_signature
        and image.signature is not None
        and image.signature.target == "image"
    ):
        verify_image(part, image.signature)
    part.replace(destination)
    if image.compression is None:
        save_checksum(destination, expected, image.algorithm)
        log.info("Saved %s", destination)
    else:
        _extract(destination, image)


def add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pattern", nargs="?", help="regex to filter local images")
    parser.add_argument(
        "--vm-id", type=int, help="VM ID (next free ID is chosen when omitted)"
    )
    parser.add_argument(
        "--vm-name", help="VM name (derived from the image when omitted)"
    )
    parser.add_argument("--storage", help="Proxmox storage for VM disks")
    parser.add_argument("--cores", type=int, help="number of CPU cores")
    parser.add_argument("--memory", type=int, help="memory in MiB")
    parser.add_argument("--cpu", help="CPU type passed as cputype (default: host)")
    parser.add_argument("--bridge", help="network bridge")
    parser.add_argument(
        "--tags", help="Proxmox tags, separated by commas or semicolons"
    )
    parser.add_argument("--pool", help="Proxmox resource pool")
    parser.add_argument(
        "--onboot",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="start the VM when the node boots",
    )
    parser.add_argument("--description", help="VM description shown in Proxmox")
    parser.add_argument(
        "--firmware",
        choices=FIRMWARE_VALUES,
        help="VM firmware; auto uses uefi when the image name says UEFI",
    )
    pve_argument = parser.add_argument(
        "--pve",
        metavar="NAME",
        help=(
            "create the template on the remote [pve.<name>] host through its API "
            "(default: run qm on this machine)"
        ),
    )
    _set_completer(pve_argument, _complete_pve_names)
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print the assembled command or API requests and exit",
    )


def _layered(model: type[Model], *sources: BaseModel | dict[str, Any] | None) -> Model:
    """Merge configuration layers, honouring only explicitly set fields."""
    values: dict[str, Any] = {}
    for source in sources:
        if source is None:
            continue
        if isinstance(source, dict):
            values.update(source)
        else:
            values.update(source.model_dump(exclude_unset=True))
    return model.model_validate(values)


def run_create(args: argparse.Namespace, settings: Settings) -> None:
    host = settings.pve_host(args.pve) if args.pve else None
    target: PveTarget = (
        LocalPveTarget()
        if host is None
        else ApiPveTarget(args.pve, host, settings.images_dir)
    )
    if host is not None:
        log.info("Using PVE host %r (%s)", args.pve, host.host)

    cli_overrides = {
        name: value
        for name in CreateSettings.model_fields
        if (value := getattr(args, name, None)) is not None
    }
    create = _layered(
        CreateSettings,
        settings.create,
        None if host is None else host.create,
        cli_overrides,
    )
    vmid = _layered(VmidSettings, settings.vmid, None if host is None else host.vmid)
    cloudinit = _layered(
        CloudInitSettings,
        settings.cloudinit,
        None if host is None else host.cloudinit,
    )
    sshkeys = require_ssh_keys(cloudinit)

    images = find_images(settings.images_dir, args.pattern)
    if len(images) == 1:
        image = images[0]
        log.info("Selected image: %s", image.name)
    else:
        image = choose_image(images, settings.images_dir)

    firmware: ResolvedFirmware = (
        create.firmware if create.firmware != "auto" else detect_firmware(image)
    )
    vm_name = args.vm_name or default_vm_name(image)

    target.validate(create)

    if args.vm_id is not None:
        if args.vm_id < MIN_VM_ID:
            raise QmTemplateError(f"VM ID must be at least {MIN_VM_ID}")
        target.assert_vm_id_free(args.vm_id)
        vm_id = args.vm_id
    else:
        vm_id = target.next_vm_id(vmid.start, vmid.step)
        log.info("Selected free VM ID: %d", vm_id)
    log.info("Creating VM %d (%s)", vm_id, vm_name)
    log.debug(
        "storage=%s cores=%d memory=%d cpu=%s bridge=%s firmware=%s "
        "pool=%s onboot=%s tags=%s",
        create.storage,
        create.cores,
        create.memory,
        create.cpu,
        create.bridge,
        firmware,
        create.pool,
        create.onboot,
        ";".join(create.tags) or "-",
    )

    spec = VmSpec(
        vm_id=vm_id,
        name=vm_name,
        image=image,
        firmware=firmware,
        create=create,
        cloudinit=cloudinit,
        sshkeys=sshkeys,
    )
    source = target.source_for(image)
    if args.dry_run:
        print(target.preview(spec, source))
        return
    target.ensure_source(source, image)
    try:
        target.create_template(spec, source)
    except QmTemplateError:
        target.abort(vm_id)
        raise
    log.info("Template %s (ID %d) created", vm_name, vm_id)


def add_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pattern", nargs="?", help="regex to filter local images")
    parser.add_argument(
        "--vm-name", help="VM name (derived from the image when omitted)"
    )
    parser.add_argument(
        "--format",
        choices=sorted(DISK_FORMATS),
        default=DEFAULT_FORMAT,
        help=f"guest disk format (default: {DEFAULT_FORMAT})",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="reconvert the guest disk even if it already exists",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print the commands and exit",
    )


def run_prepare(args: argparse.Namespace, settings: Settings) -> None:
    images = find_images(settings.images_dir, args.pattern)
    if len(images) == 1:
        image = images[0]
        log.info("Selected image: %s", image.name)
    else:
        image = choose_image(images, settings.images_dir)

    vm_name = args.vm_name or default_vm_name(image)
    cloudinit = settings.cloudinit
    disk = image.with_suffix(DISK_FORMATS[args.format])
    if disk == image:
        raise QmTemplateError(
            f"--format {args.format} would overwrite the source image; "
            "choose a different format"
        )
    seed = image.with_suffix(".iso")
    seed_files = {
        "user-data": user_data(cloudinit, vm_name),
        "meta-data": meta_data(vm_name),
        "network-config": network_config(),
    }
    convert = convert_command(image, disk, args.format)
    convert_needed = args.force or not disk.exists()
    builder = select_iso_builder(settings.prepare.preferred)
    seed_command = builder.build_command(seed, [Path(name) for name in seed_files])
    if args.dry_run:
        if convert_needed:
            print(pretty(convert))
        print(pretty(seed_command))
        return

    if convert_needed:
        require_tool(QEMU_IMG, package="qemu-utils")
        disk.unlink(missing_ok=True)
    seed.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{PROGRAM}-seed-") as staging:
        staged = Path(staging)
        for name, content in seed_files.items():
            (staged / name).write_text(content, encoding="utf-8")
        if convert_needed:
            run_tool(convert)
            log.info("Wrote %s", disk)
        else:
            log.info("Keeping existing %s", disk)
        run_tool(builder.build_command(seed, [staged / name for name in seed_files]))
    log.info("Wrote %s", seed)


def add_distros_arguments(parser: argparse.ArgumentParser) -> None:
    action = parser.add_argument(
        "distro", nargs="?", help="distro to describe (default: all)"
    )
    _set_completer(action, _complete_distro_names)


def add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--full",
        action="store_true",
        help="also print the per-distro default tables",
    )


def _distro_tables() -> str:
    lines = [
        "# Generated per-distro defaults. Every value below is the built-in",
        "# default; remove a table to fall back to it, or edit the values.",
    ]
    for name, distro in DISTROS.items():
        lines.extend(["", f"[distro.{name}]"])
        for key, option in distro.options.items():
            if option.default:
                lines.append(f"{key} = {json.dumps(option.default)}")
    return "\n".join(lines) + "\n"


def run_config(args: argparse.Namespace, settings: Settings) -> None:
    print(packaged_config_text(), end="")
    if args.full:
        print()
        print(_distro_tables(), end="")


def _describe_option(value: str, detail: str) -> str:
    rendered = f"  {value:<24} {detail}".rstrip()
    return rendered


def run_distros(args: argparse.Namespace, settings: Settings) -> None:
    names = [args.distro] if args.distro else list(DISTROS)
    for index, name in enumerate(names):
        distro = DISTROS.get(name)
        if distro is None:
            raise QmTemplateError(
                f"unknown distro {name!r} (run `{PROGRAM} distros` for a list)"
            )
        if index:
            print()
        print(f"{distro.name:<12} {distro.description}")
        overrides = settings.distro_overrides(distro.name)
        for key, option in distro.options.items():
            value = overrides.get(key) or option.default or "-"
            print(_describe_option(f"{key} = {value}", option.describe()))


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace, Settings], None]
    description: str = ""
    aliases: tuple[str, ...] = ()
    load_settings: bool = True


COMMANDS: tuple[Command, ...] = (
    Command(
        name="download",
        help="download a cloud image",
        add_arguments=add_download_arguments,
        run=run_download,
        description="Resolve, download and verify a distro cloud image.",
        aliases=("get",),
    ),
    Command(
        name="create",
        help="create a Proxmox VE VM template",
        add_arguments=add_create_arguments,
        run=run_create,
        description="Create a Proxmox VE VM template from a downloaded cloud image.",
        aliases=("template",),
    ),
    Command(
        name="prepare",
        help="prepare local VM artifacts from a downloaded image",
        add_arguments=add_prepare_arguments,
        run=run_prepare,
        description=(
            "Convert a downloaded image to a hypervisor disk format and build a "
            "NoCloud cloud-init seed ISO that can be attached as a CD-ROM."
        ),
    ),
    Command(
        name="distros",
        help="list supported distros",
        add_arguments=add_distros_arguments,
        run=run_distros,
        description="List supported distros with the values each option accepts.",
    ),
    Command(
        name="config",
        help="print the default configuration",
        add_arguments=add_config_arguments,
        run=run_config,
        description=(
            "Print the default configuration to stdout; redirect it to "
            "/etc/qm-template/config.toml to use it as a starting point."
        ),
        load_settings=False,
    ),
)
