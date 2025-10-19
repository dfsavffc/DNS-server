"""Configuration loading and record indexing."""
from __future__ import annotations

import ipaddress
import logging
import os
from typing import Dict, List, Tuple

import yaml
from dnslib import A, AAAA, CNAME, MX, NS, PTR, TXT, DNSLabel, QTYPE, RR

from .records import Record

logger = logging.getLogger(__name__)

SUPPORTED_QTYPES: dict[str, int] = {
    "A": QTYPE.A,
    "AAAA": QTYPE.AAAA,
    "CNAME": QTYPE.CNAME,
    "TXT": QTYPE.TXT,
    "MX": QTYPE.MX,
    "NS": QTYPE.NS,
    "PTR": QTYPE.PTR,
}


class Config:
    """Manages configuration state and indexed DNS records."""

    def __init__(self, path: str) -> None:
        """Initialize configuration and load records from a file."""
        self.path = path
        self._mtime = 0.0
        self.default_ttl = 300
        self.records: List[Record] = []
        self.index: Dict[Tuple[str, str], List[Record]] = {}
        self.load(force=True)

    def load(self, force: bool = False) -> None:
        """Load or reload the YAML configuration file.

        Args:
            force: Force reload regardless of modification time.
        """
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            if force:
                raise
            return

        if not force and st.st_mtime <= self._mtime:
            return

        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.default_ttl = int(data.get("default_ttl", 300))
        raw_records = data.get("records", [])
        if not isinstance(raw_records, list):
            raise ValueError("'records' must be a list")

        recs: List[Record] = []
        for i, item in enumerate(raw_records, 1):
            try:
                name = str(item["name"]).strip()
                rtype = str(item["type"]).upper().strip()
                value = str(item["value"]).strip()
                ttl = int(item.get("ttl", self.default_ttl))
                if not name.endswith("."):
                    raise ValueError("record name must be a fully-qualified domain ending with '.'")
                if rtype not in SUPPORTED_QTYPES:
                    raise ValueError(f"unsupported type '{rtype}'")
                recs.append(Record(name=name, rtype=rtype, value=value, ttl=ttl))
            except Exception as exc:
                raise ValueError(f"Error in record #{i}: {exc}") from exc

        index: Dict[Tuple[str, str], List[Record]] = {}
        for rec in recs:
            index.setdefault((rec.name.lower(), rec.rtype), []).append(rec)

        self.records = recs
        self.index = index
        self._mtime = st.st_mtime
        logger.info("configuration loaded: %d records", len(self.records))

    def maybe_reload(self) -> None:
        """Reload the configuration file if it has been modified."""
        try:
            self.load(force=False)
        except Exception as exc:
            logger.error("failed to reload configuration: %s", exc)

    def _to_rrs(self, name_lc: str, rtype: str) -> List[RR]:
        """Convert stored records into `dnslib.RR` objects."""
        out: List[RR] = []
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
                elif rtype == "MX":
                    prio_str, host = rec.value.split(maxsplit=1)
                    out.append(
                        RR(label, QTYPE.MX, rdata=MX(int(prio_str), DNSLabel(host)), ttl=rec.ttl)
                    )
                elif rtype == "NS":
                    out.append(RR(label, QTYPE.NS, rdata=NS(DNSLabel(rec.value)), ttl=rec.ttl))
                elif rtype == "PTR":
                    out.append(RR(label, QTYPE.PTR, rdata=PTR(DNSLabel(rec.value)), ttl=rec.ttl))
            except Exception:
                logger.warning("invalid record skipped: %s %s", rtype, rec.value)
        return out

    def lookup(self, qname: DNSLabel, qtype: int) -> tuple[List[RR], List[RR]]:
        """Resolve a query against the record index.

        Args:
            qname: Queried domain name.
            qtype: Numeric DNS query type (see `dnslib.QTYPE`).

        Returns:
            A tuple of `(answers, additionals)` lists of RR objects.
        """
        name = str(qname).lower()
        answers: List[RR] = []
        additionals: List[RR] = []

        if qtype == QTYPE.ANY:
            for t in SUPPORTED_QTYPES.keys():
                answers.extend(self._to_rrs(name, t))
            return answers, additionals

        qtype_name = QTYPE.get(qtype)
        if qtype_name in SUPPORTED_QTYPES:
            answers.extend(self._to_rrs(name, qtype_name))

        if not answers:  # Handle CNAME fallback
            cname_rrs = self._to_rrs(name, "CNAME")
            if cname_rrs:
                answers.extend(cname_rrs)
                target = str(cname_rrs[0].rdata.label)
                for t in ("A", "AAAA"):
                    additionals.extend(self._to_rrs(target.lower(), t))

        return answers, additionals
