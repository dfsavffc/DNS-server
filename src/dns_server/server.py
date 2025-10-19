"""Server entrypoint and lifecycle management."""
from __future__ import annotations

import asyncio
import logging
import socket

from .config import Config
from .protocol import DNSUDPProtocol


async def serve(config_path: str, host: str, port: int, log_level: str = "INFO") -> None:
    """Run the asynchronous UDP DNS server.

    The server runs indefinitely until the surrounding event loop is cancelled.
    Cancellation (e.g., Ctrl+C) will trigger the 'finally' block and close the transport.

    Args:
        config_path: Path to the YAML configuration file.
        host: Address to bind the UDP socket to.
        port: UDP port number to listen on.
        log_level: Logging verbosity level.
    """
    logging.basicConfig(
        level=getattr(logging, log_level),
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
    finally:
        logger.info("shutting down…")
        transport.close()
