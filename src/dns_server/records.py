"""Data structures representing DNS records."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Record:
    """Single DNS record entry.

    Attributes:
        name (str): Fully qualified domain name (must end with a dot).
        rtype (str): DNS record type (A, AAAA, CNAME, TXT, NS, PTR).
        value (str): Record value.
        ttl (int): Time to live, in seconds.
    """

    name: str
    rtype: str
    value: str
    ttl: int
