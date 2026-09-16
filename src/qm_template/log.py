import logging
import sys

from qm_template import PROGRAM

log = logging.getLogger(PROGRAM)


def setup_logging(verbosity: int = 0) -> None:
    """Configure the root logger to write to stderr.

    Verbosity 0 keeps the normal status output, 1 adds debug messages and 2
    also prefixes the log level, logger name and timestamp.
    """
    level = logging.DEBUG if verbosity else logging.INFO
    fmt = (
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
        if verbosity > 1
        else "%(message)s"
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=level, handlers=[handler], force=True)
