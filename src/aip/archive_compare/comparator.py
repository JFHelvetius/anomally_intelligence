"""Cross-archive comparator (pure logic — no I/O beyond reading the archives).

The comparison strategy is deliberately conservative: we only flag
disagreement on artifacts whose canonical form is content-derived and must
be byte-identical across archives. Anything that legitimately differs
between independent operators (chain positions, timestamps, signing keys)
is excluded.

Lo que el módulo intenta atrapar:

- Operador A y operador B ingestan el mismo fichero (mismo SHA-256). Las
  parámetros del audit log (``size_bytes`` y, en futuras versiones,
  cualquier metadato derivado del contenido) deben coincidir. Si A dice
  ``size_bytes=7264`` y B dice ``7000``, alguien mintió.
- Ambos archives emiten un certificado de captura para la misma evidencia.
  Como ``certificate_hash`` es un JCS self-hash, debe ser idéntico si el
  contenido del cert lo es.
- Ambos archives mantienen un inference proof con el mismo ``proof_id`` y
  el mismo ``target_justification_hash``. El ``proof_hash`` debe coincidir
  iff la DAG declarada es idéntica.

Lo que el módulo NO intenta atrapar:

- Cadenas de transparencia, manifest hashes, witness attestations — todo
  esto es per-archive y diverge legítimamente.
- Identidad del firmante o de las llaves — fuera de scope (ADR-0043 cubre
  la vinculación clave-identidad externamente).
- Veracidad de las premisas — fuera de scope siempre.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from aip.archive import CAPTURE_CERTIFICATES_DIRNAME, Archive
from aip.audit import log as audit_log
from aip.justification.logic.store import INFERENCE_PROOFS_DIRNAME

_INGEST_ACTION = "ingest_evidence"
# Parameters that are content-derived and must therefore be identical
# across archives that ingested the same file. ``size_bytes`` is the only
# such field today; future fields (e.g., MIME-as-detected) should be added
# here.
_CONTENT_DERIVED_PARAMS: frozenset[str] = frozenset({"size_bytes"})


# --------------------------------------------------------------------- models


@dataclass(frozen=True, slots=True)
class EvidenceDivergence:
    """Single evidence hash and how the two archives describe it.

    ``in_archive_a`` / ``in_archive_b`` indicate presence. If both are
    True, the rest of the fields are populated to report agreement.
    """

    evidence_hash: str
    in_archive_a: bool
    in_archive_b: bool
    audit_params_a: dict[str, str] = field(default_factory=dict)
    audit_params_b: dict[str, str] = field(default_factory=dict)
    audit_params_match: bool | None = None       # None if missing in either
    diverging_param_fields: tuple[str, ...] = ()
    capture_cert_hash_a: str | None = None
    capture_cert_hash_b: str | None = None
    capture_cert_match: bool | None = None       # None if absent in either

    @property
    def is_shared(self) -> bool:
        return self.in_archive_a and self.in_archive_b

    @property
    def has_divergence(self) -> bool:
        """True only if both sides have data AND something disagrees."""
        if not self.is_shared:
            return False
        if self.audit_params_match is False:
            return True
        return self.capture_cert_match is False


@dataclass(frozen=True, slots=True)
class ProofDivergence:
    """Inference proof matched by ``proof_id`` across both archives."""

    proof_id: str
    target_justification_hash_a: str | None
    target_justification_hash_b: str | None
    proof_hash_a: str | None
    proof_hash_b: str | None
    in_archive_a: bool
    in_archive_b: bool

    @property
    def is_shared(self) -> bool:
        return self.in_archive_a and self.in_archive_b

    @property
    def matches(self) -> bool | None:
        if not self.is_shared:
            return None
        return (
            self.proof_hash_a == self.proof_hash_b
            and self.target_justification_hash_a == self.target_justification_hash_b
        )

    @property
    def has_divergence(self) -> bool:
        return self.is_shared and self.matches is False


@dataclass(frozen=True, slots=True)
class CrossArchiveReport:
    """Summary of comparing archive A against archive B.

    ``has_divergence`` is True if any shared artifact disagrees. The CLI
    uses it for its exit code.
    """

    archive_a_label: str
    archive_b_label: str
    shared_evidence: tuple[EvidenceDivergence, ...]
    a_only_evidence_hashes: tuple[str, ...]
    b_only_evidence_hashes: tuple[str, ...]
    shared_proofs: tuple[ProofDivergence, ...]
    a_only_proof_ids: tuple[str, ...]
    b_only_proof_ids: tuple[str, ...]

    @property
    def has_divergence(self) -> bool:
        return any(e.has_divergence for e in self.shared_evidence) or any(
            p.has_divergence for p in self.shared_proofs
        )

    @property
    def shared_count(self) -> int:
        return len(self.shared_evidence)


# --------------------------------------------------------------------- helpers


def _ingest_entries_by_hash(archive_root: Path) -> dict[str, dict[str, str]]:
    """Walk the audit log and return ``{evidence_hash: params}`` for ingests.

    ``target`` carries the canonical URI ``aip:evidence/sha256:<hash>``; we
    extract the hash. If an evidence appears more than once (re-ingestion),
    the last occurrence wins — re-ingestion is an event the user should be
    aware of, but for the divergence check we compare the latest known
    state on each side.
    """
    out: dict[str, dict[str, str]] = {}
    for entry in audit_log.iter_entries(archive_root):
        if entry.action != _INGEST_ACTION:
            continue
        target = entry.target
        # aip:evidence/sha256:<hash>
        if "sha256:" not in target:
            continue
        ev_hash = target.rsplit("sha256:", 1)[-1].lower()
        out[ev_hash] = dict(entry.parameters)
    return out


def _capture_cert_hash_for(archive_root: Path, evidence_hash: str) -> str | None:
    """Return the capture certificate hash linked to an evidence, if any.

    The link is implicit: a capture cert file under
    ``capture-certificates/<cert_hash>.json`` is associated to an evidence
    via the ingest's provenance steps. We do the lightest possible scan:
    open the cert and check whether its ``evidence_hash`` field points at
    the evidence we care about. This avoids reconstructing the full
    ``EvidenceView`` for every evidence on both sides.
    """
    cert_dir = archive_root / CAPTURE_CERTIFICATES_DIRNAME
    if not cert_dir.is_dir():
        return None
    for f in sorted(cert_dir.iterdir(), key=lambda p: p.name):
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        if data.get("evidence_hash", "").lower() == evidence_hash.lower():
            ch = data.get("certificate_hash")
            return ch if isinstance(ch, str) else None
    return None


def _proofs_by_id(archive_root: Path) -> dict[str, dict[str, str]]:
    """``{proof_id: {target_justification_hash, proof_hash}}`` for the archive."""
    d = archive_root / INFERENCE_PROOFS_DIRNAME
    out: dict[str, dict[str, str]] = {}
    if not d.is_dir():
        return out
    for f in sorted(d.iterdir(), key=lambda p: p.name):
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("proof_id")
        if not isinstance(pid, str):
            continue
        out[pid] = {
            "target_justification_hash": str(
                data.get("target_justification_hash", "")
            ),
            "proof_hash": str(data.get("proof_hash", "")),
        }
    return out


def _compare_params(
    a: dict[str, str], b: dict[str, str]
) -> tuple[bool, tuple[str, ...]]:
    """Compare only the content-derived subset of ingest params.

    Returns ``(match, diverging_fields)``. We deliberately allow fields
    outside :data:`_CONTENT_DERIVED_PARAMS` to differ — they may reflect
    operator-specific annotation rather than content disagreement.
    """
    diverging: list[str] = []
    for key in sorted(_CONTENT_DERIVED_PARAMS):
        va = a.get(key)
        vb = b.get(key)
        if va is None and vb is None:
            # Neither archive recorded this field — not informative.
            continue
        if va != vb:
            diverging.append(key)
    return (len(diverging) == 0, tuple(diverging))


# --------------------------------------------------------------------- main


def compare_archives(
    root_a: Path, root_b: Path, *, label_a: str | None = None, label_b: str | None = None
) -> CrossArchiveReport:
    """Build a full :class:`CrossArchiveReport` for the two archives.

    Raises ``FileNotFoundError`` if either root does not exist. Otherwise
    treats absent sub-trees (no audit log, no certs, no proofs) as empty —
    a brand-new archive compared against a populated one yields a clean
    diff rather than an error.
    """
    if not root_a.is_dir():
        raise FileNotFoundError(f"archive root not found: {root_a}")
    if not root_b.is_dir():
        raise FileNotFoundError(f"archive root not found: {root_b}")

    # Force-open both archives once to validate basic shape — we don't use
    # the resulting object directly because all our reads go through the
    # lower-level helpers, but if the archive is malformed we want to fail
    # fast with a recognizable error from the storage layer.
    Archive.open(root_a)
    Archive.open(root_b)

    ingests_a = _ingest_entries_by_hash(root_a)
    ingests_b = _ingest_entries_by_hash(root_b)
    hashes_a = set(ingests_a)
    hashes_b = set(ingests_b)
    shared_hashes = sorted(hashes_a & hashes_b)
    a_only = sorted(hashes_a - hashes_b)
    b_only = sorted(hashes_b - hashes_a)

    shared_evidence: list[EvidenceDivergence] = []
    for h in shared_hashes:
        params_a = ingests_a[h]
        params_b = ingests_b[h]
        params_match, diverging = _compare_params(params_a, params_b)
        cert_a = _capture_cert_hash_for(root_a, h)
        cert_b = _capture_cert_hash_for(root_b, h)
        cert_match: bool | None = (
            None if cert_a is None or cert_b is None else cert_a == cert_b
        )
        shared_evidence.append(
            EvidenceDivergence(
                evidence_hash=h,
                in_archive_a=True,
                in_archive_b=True,
                audit_params_a=params_a,
                audit_params_b=params_b,
                audit_params_match=params_match,
                diverging_param_fields=diverging,
                capture_cert_hash_a=cert_a,
                capture_cert_hash_b=cert_b,
                capture_cert_match=cert_match,
            )
        )

    proofs_a = _proofs_by_id(root_a)
    proofs_b = _proofs_by_id(root_b)
    proof_ids = sorted(set(proofs_a) | set(proofs_b))
    shared_proofs: list[ProofDivergence] = []
    a_only_proofs: list[str] = []
    b_only_proofs: list[str] = []
    for pid in proof_ids:
        in_a = pid in proofs_a
        in_b = pid in proofs_b
        if in_a and in_b:
            shared_proofs.append(
                ProofDivergence(
                    proof_id=pid,
                    target_justification_hash_a=proofs_a[pid][
                        "target_justification_hash"
                    ],
                    target_justification_hash_b=proofs_b[pid][
                        "target_justification_hash"
                    ],
                    proof_hash_a=proofs_a[pid]["proof_hash"],
                    proof_hash_b=proofs_b[pid]["proof_hash"],
                    in_archive_a=True,
                    in_archive_b=True,
                )
            )
        elif in_a:
            a_only_proofs.append(pid)
        else:
            b_only_proofs.append(pid)

    return CrossArchiveReport(
        archive_a_label=label_a or root_a.name,
        archive_b_label=label_b or root_b.name,
        shared_evidence=tuple(shared_evidence),
        a_only_evidence_hashes=tuple(a_only),
        b_only_evidence_hashes=tuple(b_only),
        shared_proofs=tuple(shared_proofs),
        a_only_proof_ids=tuple(a_only_proofs),
        b_only_proof_ids=tuple(b_only_proofs),
    )


__all__ = [
    "CrossArchiveReport",
    "EvidenceDivergence",
    "ProofDivergence",
    "compare_archives",
]
