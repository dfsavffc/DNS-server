"""Configuration loading and DNS record indexing."""
from __future__ import annotations

import ipaddress
import logging
import os

import yaml
from dnslib import A, AAAA, CNAME, NS, PTR, TXT, DNSLabel, QTYPE, RR

from .records import Record

logger = logging.getLogger(__name__)

# Stable order for QTYPE.ANY responses.
SUPPORTED_ORDER: tuple[str, ...] = ("A", "AAAA", "CNAME", "TXT", "NS", "PTR")
SUPPORTED_QTYPES: dict[str, int] = {
    "A": QTYPE.A,
    "AAAA": QTYPE.AAAA,
    "CNAME": QTYPE.CNAME,
    "TXT": QTYPE.TXT,
    "NS": QTYPE.NS,
    "PTR": QTYPE.PTR,
}


class Config:
    """Parsed configuration with indexed DNS records.

    Args:
        path: Filesystem path to the YAML configuration.

    Attributes:
        path: Path to the YAML config file.
        default_ttl: Default TTL applied to records without explicit TTL.
        records: Linear list of parsed records.
        index: Lookup index keyed by (fqdn_lower, rtype).
    """

    def __init__(self, path: str) -> None:
        """Initialize and load configuration.

        Args:
            path: Path to YAML file.
        """
        self.path = path
        self._mtime = 0.0
        self.default_ttl = 300
        self.records: list[Record] = []
        self.index: dict[tuple[str, str], list[Record]] = {}
        self.load(force=True)

    def load(self, force: bool = False) -> None:
        """Load or reload YAML configuration.

        Args:
            force: Reload regardless of file mtime.

        Raises:
            ValueError: On invalid YAML structure or record data.
            FileNotFoundError: If the config is missing and `force=True`.
        """
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            if force:
                raise
            return

        if not force and st.st_mtime <= self._mtime:
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"YAML parsing error: {exc}") from exc

        try:
            self.default_ttl = int(data.get("default_ttl", 300))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid default_ttl: {exc}") from exc

        raw = data.get("records", [])
        if not isinstance(raw, list):
            raise ValueError("'records' must be a list")

        recs: list[Record] = []
        for i, item in enumerate(raw, 1):
            if not isinstance(item, dict):
                raise ValueError(f"record #{i}: mapping required, got {type(item).__name__}")
            try:
                name = str(item["name"]).strip()
                rtype = str(item["type"]).upper().strip()
                value = str(item["value"]).strip()
                ttl = int(item.get("ttl", self.default_ttl))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"malformed record #{i}: {exc}") from exc

            if not name.endswith("."):
                raise ValueError(f"record #{i}: name must end with '.' (got {name!r})")
            if rtype not in SUPPORTED_QTYPES:
                raise ValueError(f"record #{i}: unsupported type '{rtype}'")

            recs.append(Record(name=name, rtype=rtype, value=value, ttl=ttl))

        index: dict[tuple[str, str], list[Record]] = {}
        for rec in recs:
            index.setdefault((rec.name.lower(), rec.rtype), []).append(rec)

        self.records = recs
        self.index = index
        self._mtime = st.st_mtime
        logger.info("configuration loaded: %d records", len(self.records))

    def maybe_reload(self) -> None:
        """Reload on mtime change; keep last good config on errors.

        Returns:
            None
        """
        try:
            self.load(force=False)
        except (ValueError, yaml.YAMLError, OSError) as exc:
            logger.error("failed to reload configuration: %s", exc)

    def _to_rrs(self, name_lc: str, rtype: str) -> list[RR]:
        """Build `dnslib.RR` for a (name, rtype) pair.

        Malformed entries are skipped with a warning.

        Args:
            name_lc: Lowercased FQDN (with trailing dot).
            rtype: Record type name (e.g., "A", "AAAA").

        Returns:
            List of `RR` objects for the given key.
        """
        out: list[RR] = []
        for rec in self.index.get((name_lc, rtype), []):
            label = DNSLabel(rec.name)
            try:
                if rtype == "A":
                    ipaddress.IPv4Address(rec.value)
                    out.append(RR(label, QTYPE.A, rdata=A(rec.value), ttl=rec.ttl))
                elif rtype == "AAAA":
                    ipaddress.IPv6Address(rec.value)
                    out.append(RR(label, QTYPE.AAAA, rdata=AAAA(rec.value), ttl=rec.ttl))
                elif rtype == "CNAME":
                    out.append(RR(label, QTYPE.CNAME, rdata=CNAME(DNSLabel(rec.value)), ttl=rec.ttl))
                elif rtype == "TXT":
                    out.append(RR(label, QTYPE.TXT, rdata=TXT(rec.value), ttl=rec.ttl))
                elif rtype == "NS":
                    out.append(RR(label, QTYPE.NS, rdata=NS(DNSLabel(rec.value)), ttl=rec.ttl))
                elif rtype == "PTR":
                    out.append(RR(label, QTYPE.PTR, rdata=PTR(DNSLabel(rec.value)), ttl=rec.ttl))
            except ipaddress.AddressValueError:
                logger.warning("invalid IP skipped: %s %s", rtype, rec.value)
            except (ValueError, IndexError):
                logger.warning("invalid record skipped: %s %s", rtype, rec.value)
            except Exception as exc:  # last-resort guard
                logger.warning("unexpected error for %s %s: %s", rtype, rec.value, exc)
        return out

    def lookup(self, qname: DNSLabel, qtype: int) -> tuple[list[RR], list[RR]]:
        """Resolve records for the given query.

        Args:
            qname: Queried domain name (FQDN label).
            qtype: Numeric DNS type (`dnslib.QTYPE`).

        Returns:
            Tuple of (answers, additionals) as lists of `RR`.
        """
        name = str(qname).lower()
        answers: list[RR] = []
        additionals: list[RR] = []

        if qtype == QTYPE.ANY:
            for t in SUPPORTED_ORDER:
                answers.extend(self._to_rrs(name, t))
            cname_targets = [str(rr.rdata.label) for rr in answers if rr.rtype == QTYPE.CNAME]
            if cname_targets:
                target = cname_targets[0].lower()
                additionals.extend(self._to_rrs(target, "A"))
                additionals.extend(self._to_rrs(target, "AAAA"))
            return answers, additionals

        qtype_name = QTYPE.get(qtype)
        if qtype_name in SUPPORTED_QTYPES:
            answers.extend(self._to_rrs(name, qtype_name))

        if not answers:
            cname_rrs = self._to_rrs(name, "CNAME")
            if cname_rrs:
                answers.extend(cname_rrs)
                target = str(cname_rrs[0].rdata.label).lower()
                additionals.extend(self._to_rrs(target, "A"))
                additionals.extend(self._to_rrs(target, "AAAA"))

        return answers, additionals
