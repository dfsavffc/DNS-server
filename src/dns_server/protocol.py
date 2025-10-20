"""Asyncio UDP protocol for the authoritative DNS server."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from dnslib import DNSHeader, DNSRecord, QTYPE, RCODE
from dnslib.dns import DNSError

from .config import Config

logger = logging.getLogger(__name__)


class DNSUDPProtocol(asyncio.DatagramProtocol):
    """Authoritative DNS handler over UDP.

    Attributes:
        transport: Active UDP transport or None until connected.
        config: Shared configuration and record index.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the protocol.

        Args:
            config: Loaded configuration backing responses.
        """
        self.transport: asyncio.DatagramTransport | None = None
        self.config = config

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called by asyncio when the UDP socket is ready.

        Args:
            transport: Created datagram transport.
        """
        self.transport = transport  # type: ignore[assignment]
        sock = self.transport.get_extra_info("socket")
        logger.info("UDP listening on %s", sock.getsockname() if sock else "?")

    def datagram_received(self, data: bytes, addr: Any) -> None:
        """Process a single DNS datagram.

        Args:
            data: Raw DNS message bytes.
            addr: Client address tuple as provided by asyncio.

        Returns:
            None
        """
        logger.debug("received %d bytes from %s", len(data), addr)
        self.config.maybe_reload()

        try:
            request = DNSRecord.parse(data)
        except DNSError:
            logger.debug("failed to parse request from %s", addr)
            return

        reply = DNSRecord(DNSHeader(id=request.header.id, qr=1, aa=1, ra=0), q=request.q)
        qname = request.q.qname
        qtype = request.q.qtype
        logger.debug("%s query: %s %s", addr, qname, QTYPE.get(qtype))

        answers, additionals = self.config.lookup(qname, qtype)
        if answers:
            for rr in answers:
                reply.add_answer(rr)
            for rr in additionals:
                reply.add_ar(rr)
        else:
            reply.header.rcode = RCODE.NXDOMAIN

        if self.transport:
            try:
                self.transport.sendto(reply.pack(), addr)
            except (OSError, RuntimeError) as exc:
                logger.warning("failed to send response to %s: %s", addr, exc)
