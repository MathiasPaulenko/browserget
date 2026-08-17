"""Logging configuration with verbosity levels."""

from __future__ import annotations

import logging
import sys


def setup_logging(verbose: bool = False, debug: bool = False, quiet: bool = False) -> None:
    """Configure the root logger with the appropriate verbosity level.

    Verbosity mapping:

    - ``quiet``: WARNING level — only warnings and errors.
    - default: INFO level — progress and results.
    - ``verbose``: DEBUG level — includes HTTP URLs, cache paths, version
      resolution.
    - ``debug``: DEBUG level with full tracebacks on exceptions.

    All output goes to stderr.

    Args:
        verbose: Enable DEBUG level output.
        debug: Enable DEBUG level with full tracebacks.
        quiet: Restrict output to WARNING level and above.
    """
    if debug or verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    if debug:
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
    else:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Quiet stdlib urllib unless debugging
    urllib_level = logging.DEBUG if debug else logging.WARNING
    logging.getLogger("urllib").setLevel(urllib_level)
