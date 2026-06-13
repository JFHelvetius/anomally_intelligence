"""Cross-archive divergence detection.

Compares two AIP archives that may share evidence and reports whether the
overlapping artifacts agree byte-for-byte where they should. Designed for
investigative contexts where the same evidence is independently ingested
by two operators and we want to detect silent tampering.

What we compare for **shared evidence** (same SHA-256 in both archives):

- **Ingest audit parameters**: ``size_bytes`` and any other parameters
  attached to the ``ingest_evidence`` action. These are content-derived
  and must match. Chain-position fields (``seq``, ``prev_hash``,
  ``entry_hash``, ``timestamp``, ``actor``) legitimately differ between
  archives and are excluded from the comparison.
- **Capture certificate hash**: if both archives carry a cert for the
  same evidence, their ``certificate_hash`` (JCS self-hash) must match
  bit-for-bit. A mismatch means one of the certs was re-emitted with
  modified content.

What we compare for **inference proofs**: any proof with the same
``proof_id`` and ``target_justification_hash`` is matched across archives.
Mismatching ``proof_hash`` flags tampering.

What we deliberately do **not** compare:

- Transparency manifests, audit chain heads, sequence numbers — these are
  per-archive and divergence is expected.
- Witnesses, OTS proofs — these attest to specific manifests, not to the
  underlying evidence.
- Operator identities, signing keys — out of scope; trust is per-archive.

The module is pure logic; the CLI wrapper (``aip diff archives``) handles
JSON output and exit codes.
"""

from __future__ import annotations

from aip.archive_compare.comparator import (
    CrossArchiveReport,
    EvidenceDivergence,
    ProofDivergence,
    compare_archives,
)

__all__ = [
    "CrossArchiveReport",
    "EvidenceDivergence",
    "ProofDivergence",
    "compare_archives",
]
