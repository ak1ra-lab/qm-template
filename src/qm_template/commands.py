import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from qm_template import PROGRAM
from qm_template.checksum import fetch_checksum, save_checksum, verify_checksum
from qm_template.config import Settings
from qm_template.distros import DISTROS
from qm_template.download import download_image, part_path, select_downloaders
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.images import (
    checksum_sidecar,
    find_images,
    human_size,
    image_sidecars,
    orphaned_sidecars,
    superseded_images,
)
from qm_template.log import log
from qm_template.pve import (
    build_qm_create,
    check_storage,
    choose_image,
    choose_vm_id,
    default_vm_name,
    prompt,
    run_qm,
    sshkeys_file,
    vm_config_path,
)
from qm_template.shell import pretty


def add_download_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "distro",
        nargs="?",
        help="distro name (default from configuration)",
    )
    parser.add_argument("--release", help="distro release or codename")
    parser.add_argument("--variant", help="image variant")
    parser.add_argument("--arch", help="image architecture")
    parser.add_argument("--tag", help="specific image tag/version")
    parser.add_argument(
        "--quiet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="hide downloader progress output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the download command and exit",
    )


def run_download(args: argparse.Namespace, settings: Settings) -> None:
    name = args.distro or settings.download.default_distro
    distro = DISTROS.get(name)
    if distro is None:
        raise QmTemplateError(
            f"unknown distro {name!r} (run `{PROGRAM} distros` for a list)"
        )
    overrides = {
        "release": args.release,
        "variant": args.variant,
        "arch": args.arch,
        "tag": args.tag,
    }
    if args.tag and not distro.supports_tag:
        log.warning("%s does not support --tag, ignoring it", distro.name)
        overrides["tag"] = None
    params = distro.merge(settings.download.defaults.get(distro.name, {}), overrides)
    image = distro.resolve(params)
    log.info("Image: %s", image.local_path)
    log.debug("URL: %s", image.url)
    log.debug("Checksum: %s (%s)", image.checksum_url, image.algorithm)
    destination = settings.images_dir / image.local_path
    quiet = settings.download.quiet if args.quiet is None else args.quiet
    downloaders = select_downloaders(
        settings.download.preferred, settings.download.connections, quiet=quiet
    )
    if args.dry_run:
        print(pretty(downloaders[0].build_command(image.url, part_path(destination))))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = fetch_checksum(image.checksum_url, image.filename)
    if destination.is_file():
        if verify_checksum(destination, expected, image.algorithm):
            save_checksum(destination, expected, image.algorithm)
            log.info("Already up to date: %s", destination)
            return
        log.warning("Checksum mismatch for %s, removing it", destination)
        destination.unlink()
    part = download_image(image, destination, downloaders)
    log.info("Verifying checksum")
    if not verify_checksum(part, expected, image.algorithm):
        part.unlink(missing_ok=True)
        raise QmTemplateError("downloaded image failed checksum verification")
    part.replace(destination)
    save_checksum(destination, expected, image.algorithm)
    log.info("Saved %s", destination)


def add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pattern", nargs="?", help="regex to filter local images")
    parser.add_argument("--vm-id", type=int, help="VM ID (prompted when omitted)")
    parser.add_argument(
        "--vm-name", help="VM name (derived from the image when omitted)"
    )
    parser.add_argument("--storage", help="Proxmox storage for VM disks")
    parser.add_argument("--cores", type=int, help="number of CPU cores")
    parser.add_argument("--memory", type=int, help="memory in MiB")
    parser.add_argument("--bridge", help="network bridge")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the assembled qm command and exit",
    )


def run_create(args: argparse.Namespace, settings: Settings) -> None:
    create = replace(
        settings.create,
        storage=(args.storage if args.storage is not None else settings.create.storage),
        cores=args.cores if args.cores is not None else settings.create.cores,
        memory=args.memory if args.memory is not None else settings.create.memory,
        bridge=args.bridge if args.bridge is not None else settings.create.bridge,
    )
    if create.cores < 1:
        raise QmTemplateError("cores must be a positive integer")
    if create.memory < 1:
        raise QmTemplateError("memory must be a positive integer")

    images = find_images(settings.images_dir, args.pattern)
    if len(images) == 1:
        image = images[0]
        log.info("Selected image: %s", image.name)
    else:
        image = choose_image(images, settings.images_dir)

    vm_name = args.vm_name or default_vm_name(image)
    if args.vm_id is not None:
        if args.vm_id <= 0:
            raise QmTemplateError("VM ID must be a positive integer")
        if vm_config_path(args.vm_id).exists():
            raise QmTemplateError(f"VM ID {args.vm_id} is already in use")
        vm_id = args.vm_id
    else:
        vm_id = choose_vm_id()
    log.info("Creating VM %d (%s)", vm_id, vm_name)
    log.debug(
        "storage=%s cores=%d memory=%d bridge=%s",
        create.storage,
        create.cores,
        create.memory,
        create.bridge,
    )

    check_storage(create.storage)
    with sshkeys_file(create) as sshkeys:
        command = build_qm_create(vm_id, vm_name, image, sshkeys, create)
        if args.dry_run:
            print(pretty(command))
            return
        run_qm(command)
    log.info("Template %s (ID %d) created", vm_name, vm_id)


def add_distros_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run_distros(args: argparse.Namespace, settings: Settings) -> None:
    for distro in DISTROS.values():
        params = distro.merge(settings.download.defaults.get(distro.name, {}), {})
        rendered = " ".join(f"{key}={value}" for key, value in sorted(params.items()))
        print(f"{distro.name:<12} {distro.description:<26} {rendered}")


def add_images_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pattern", nargs="?", help="regex to filter local images")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="remove superseded builds and orphaned checksum files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="with --prune, list the files that would be removed",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="remove without asking for confirmation",
    )


def _print_images(images: Sequence[Path], directory: Path) -> None:
    for image in images:
        sidecar = checksum_sidecar(image)
        algorithm = sidecar.suffix.lstrip(".") if sidecar else "-"
        print(
            f"{human_size(image.stat().st_size):>9}  {algorithm:<7}  "
            f"{image.relative_to(directory)}"
        )


def run_images(args: argparse.Namespace, settings: Settings) -> None:
    images = find_images(settings.images_dir, args.pattern, required=False)
    if not args.prune:
        if not images:
            log.info("No cloud images found in %s", settings.images_dir)
            return
        _print_images(images, settings.images_dir)
        return
    superseded = superseded_images(images, settings.images_dir)
    candidates = set(superseded) | set(orphaned_sidecars(settings.images_dir))
    for image in superseded:
        candidates.update(image_sidecars(image))
    candidates = sorted(candidates)
    if not candidates:
        log.info("Nothing to prune in %s", settings.images_dir)
        return
    for path in candidates:
        print(path.relative_to(settings.images_dir))
    if args.dry_run:
        log.info("%d file(s) would be removed", len(candidates))
        return
    if not args.yes:
        answer = prompt(f"Remove {len(candidates)} file(s)? [y/N] ")
        if answer.lower() not in {"y", "yes"}:
            raise UserCancelled
    for path in candidates:
        path.unlink(missing_ok=True)
    log.info("Removed %d file(s)", len(candidates))


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace, Settings], None]
    description: str = ""
    aliases: tuple[str, ...] = ()


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
        name="images",
        help="list local images and prune superseded builds",
        add_arguments=add_images_arguments,
        run=run_images,
        description="List downloaded cloud images, or prune superseded builds.",
    ),
    Command(
        name="distros",
        help="list supported distros",
        add_arguments=add_distros_arguments,
        run=run_distros,
        description="List supported distros with their configured defaults.",
    ),
)
