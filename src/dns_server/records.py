"""Data structures representing DNS records."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class Record:
    """Represents a single DNS record loaded from YAML.

    Attributes:
        name: Fully-qualified domain name (must end with a dot).
        rtype: DNS record type (A, AAAA, CNAME, TXT, MX, NS, PTR).
        value: Record value; for MX, formatted as "<priority> <host>".
        ttl: Time to live (in seconds).
    """

    name: str
    rtype: str
    value: str
    ttl: int
