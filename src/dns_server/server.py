"""Server entry point and lifecycle management."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import NoReturn

from .config import Config
from .protocol import DNSUDPProtocol


async def serve(config_path: str, host: str, port: int, log_level: str = "INFO") -> NoReturn:
    """Run the asynchronous UDP DNS server.

    Initializes configuration, binds a UDP socket, and runs until cancelled.

    Args:
        config_path (str): Path to the YAML configuration file.
        host (str): IP address to bind to.
        port (int): UDP port number to listen on.
        log_level (str, optional): Logging verbosity level. Defaults to "INFO".

    Raises:
        OSError: If the socket cannot be bound.
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    config = Config(config_path)
    loop = asyncio.get_running_loop()

    transport, _ = await loop.create_datagram_endpoint(
        lambda: DNSUDPProtocol(config),
        local_addr=(host, port),
        family=socket.AF_INET,
    )

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("server task cancelled")
    finally:
        logger.info("shutting down…")
        transport.close()
