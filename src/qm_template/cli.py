# PYTHON_ARGCOMPLETE_OK
import argparse
import sys
from collections.abc import Sequence

import argcomplete
from pydantic import ValidationError

from qm_template import PROGRAM, __version__
from qm_template.commands import COMMANDS
from qm_template.config import (
    Settings,
    format_settings_error,
    load_settings,
    resolve_config_path,
)
from qm_template.errors import QmTemplateError, UserCancelled
from qm_template.log import log, setup_logging


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c",
        "--config",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="configuration file (default: /etc/qm-template/config.toml)",
    )
    common.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS,
        help="increase log verbosity (-v: debug, -vv: with log levels and timestamps)",
    )
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description=(
            "Download cloud images, create Proxmox VE VM templates and "
            "prepare local VM artifacts."
        ),
        parents=[common],
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for command in COMMANDS:
        subparser = subparsers.add_parser(
            command.name,
            aliases=list(command.aliases),
            parents=[common],
            help=command.help,
            description=command.description,
        )
        command.add_arguments(subparser)
        subparser.set_defaults(handler=command.run, load_settings=command.load_settings)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)
    setup_logging(getattr(args, "verbose", 0))
    try:
        config_path, explicit = resolve_config_path(getattr(args, "config", None))
        settings = (
            load_settings(config_path, explicit=explicit)
            if args.load_settings
            else Settings()
        )
        args.handler(args, settings)
    except ValidationError as exc:
        log.error("%s", format_settings_error(exc, source=None))
        return 1
    except UserCancelled:
        log.info("Operation cancelled by user")
        return 0
    except QmTemplateError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        log.warning("Interrupted")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
