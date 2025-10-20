"""CLI for the DNS server."""
from __future__ import annotations

import argparse
import asyncio

from .server import serve


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed CLI options:
            - config (str): Path to YAML config file.
            - host (str): Bind address.
            - port (int): UDP port.
            - log_level (str): Logging level.
    """
    parser = argparse.ArgumentParser(
        description="Authoritative DNS server (YAML-backed)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=5353, help="UDP port")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    return parser.parse_args()


def main() -> None:
    """Run the CLI entry point.

    Initializes the event loop policy on Windows and starts the DNS server
    with parameters provided via the command line.

    Returns:
        None
    """
    args = parse_args()
    try:
        asyncio.run(serve(args.config, args.host, args.port, args.log_level))
    except (KeyboardInterrupt, SystemExit, SystemError):
        pass
