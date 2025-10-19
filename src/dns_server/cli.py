"""Command-line interface for the DNS server."""
from __future__ import annotations
import argparse
import asyncio
import sys
from .server import serve


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Authoritative DNS server (YAML-backed)")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML configuration file")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5353, help="UDP port number (default: 5353)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the command-line interface."""
    args = parse_args()

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(serve(args.config, args.host, args.port, args.log_level))
