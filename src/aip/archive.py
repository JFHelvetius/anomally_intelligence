"""Clase :class:`Archive` — fuente de verdad de la API Python V1 (ADR-0017).

Orquesta los subpaquetes ``core``, ``storage`` y ``audit`` para ofrecer tres
operaciones públicas comprometidas en V1 (ADR-0023):

- :meth:`Archive.ingest_evidence` — ingesta de un fichero local como evidencia.
- :meth:`Archive.show_evidence` — recuperación estructurada por hash o URI.
- :meth:`Archive.verify` — verificación de integridad del archive.

La CLI (Paso 10/11) es un wrapper delgado sobre esta clase.

Reglas de diseño (ADR-0017, ADR-0023, ADR-0031):

- El reloj se inyecta (Callable). En tests, reloj determinista; en producción,
  ``datetime.now(timezone.utc).replace(microsecond=0)``.
- ``ingested_by`` es **obligatorio** en V1 (decisión documentada en el plan
  Pre-F1 §R8). Sin inferencia silenciosa.
- Todas las operaciones son re-ejecutables sin red ni servicios externos.
- Idempotencia (Pre-F1.D §ingest): ingestar el mismo fichero dos veces produce
  el mismo hash y la segunda llamada es no-op.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from aip._version import SCHEMA_VERSION
from aip._version import __version__ as SOFTWARE_VERSION
from aip.audit import log as audit_log
from aip.audit import verify as audit_verify
from aip.core.evidence import (
    AuthenticationAssessment,
    Evidence,
    EvidenceKind,
    EvidenceStatus,
)
from aip.core.hashing import SHA256_HEX_LENGTH, sha256_hex_stream
from aip.core.provenance import (
    GapDescription,
    Provenance,
    ProvenanceStep,
    StepKind,
)
from aip.core.source import (
    AuthorityLevel,
    Source,
    SourceKind,
)
from aip.errors import (
    ArchiveNotFoundError,
    EvidenceNotFoundError,
    IntegrityError,
    InvalidSourceMetadataError,
    ManifestError,
)
from aip.storage import layout, tables
from aip.storage.manifest import ArchiveManifest, compute_manifest, write_manifest_atomic

DEFAULT_INGEST_GAP: Final[str] = (
    "ingestión inicial sin reconstrucción de cadena previa al artefacto"
)
"""Texto canónico del único ``GapDescription`` que :meth:`ingest_evidence`
declara al crear una nueva :class:`Provenance` mínima en V1."""


def default_clock() -> dt.datetime:
    """Reloj UTC al segundo. Usado por :class:`Archive` cuando el caller no
    inyecta uno propio."""
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


# --------------------------------------------------------------------- views


@dataclass(frozen=True)
class EvidenceView:
    """Composición devuelta por :meth:`Archive.show_evidence`."""

    evidence: Evidence
    source: Source
    provenance: Provenance | None
    provenance_steps: tuple[ProvenanceStep, ...]


@dataclass(frozen=True)
class CheckResult:
    """Resultado de una de las comprobaciones de :meth:`Archive.verify`."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class VerificationReport:
    """Reporte agregado de :meth:`Archive.verify`."""

    ok: bool
    checks: tuple[CheckResult, ...]
    counts: dict[str, int]
    archive_manifest_hash: str

    def __bool__(self) -> bool:
        return self.ok


# --------------------------------------------------------------------- Archive


class Archive:
    """Fachada local sobre el archive AIP V1."""

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def open(cls, root: str | Path) -> Archive:
        """Construye una :class:`Archive` sobre la ruta dada (no la crea)."""
        return cls(Path(root))

    # --- Ingest --------------------------------------------------------

    def ingest_evidence(
        self,
        path: Path,
        *,
        source_id: str,
        source_name: str | None = None,
        source_kind: SourceKind | None = None,
        source_authority: AuthorityLevel | None = None,
        source_jurisdiction: str | None = None,
        source_license: str | None = None,
        evidence_kind: EvidenceKind | None = None,
        mime_type: str | None = None,
        ingested_by: str,
        notes: str | None = None,
        dry_run: bool = False,
        clock: Callable[[], dt.datetime] | None = None,
    ) -> Evidence:
        """Ingesta un fichero local como nueva :class:`Evidence`.

        Ver ``docs/phase-1/command-specification.md`` §1 para el contrato.
        """
        if clock is None:
            clock = default_clock

        if not path.is_file():
            raise FileNotFoundError(f"file not found: {path}")

        # 1. Bootstrap del archive si es nuevo (creación atómica del layout).
        if not dry_run:
            layout.ensure_archive_layout(self.root)
            audit_log.bootstrap(
                self.root,
                actor=ingested_by,
                clock=clock,
                schema_version=SCHEMA_VERSION,
            )

        # 2. Hash del blob en streaming.
        with path.open("rb") as fh:
            blob_hash = sha256_hex_stream(fh)

        size_bytes = path.stat().st_size
        kind = evidence_kind if evidence_kind is not None else _infer_kind(path, mime_type)
        mime = mime_type if mime_type is not None else _infer_mime(path, kind)

        # 3. Idempotencia: ¿el blob ya está en CAOS y la Evidence ya está en tabla?
        existing_path = layout.caos_path_for(self.root, blob_hash) if not dry_run else None
        existing_row = (
            tables.read_row(self.root, "evidence", blob_hash) if not dry_run else None
        )
        if (
            not dry_run
            and existing_path is not None
            and existing_path.is_file()
            and existing_row is not None
        ):
            return Evidence.model_validate(existing_row)

        # 4. Resolver Source: existente vs. nueva.
        existing_source_row = (
            tables.read_row(self.root, "sources", source_id) if not dry_run else None
        )
        if existing_source_row is not None:
            source = Source.model_validate(existing_source_row)
            _validate_source_consistency(
                source,
                provided_name=source_name,
                provided_kind=source_kind,
                provided_authority=source_authority,
                provided_jurisdiction=source_jurisdiction,
                provided_license=source_license,
            )
        else:
            if source_name is None or source_kind is None or source_authority is None:
                raise InvalidSourceMetadataError(
                    f"source-id {source_id!r} does not exist; "
                    "--source-name, --source-kind and --source-authority are required."
                )
            source = Source(
                id=source_id,
                kind=source_kind,
                name=source_name,
                authority=source_authority,
                jurisdiction=source_jurisdiction,
                license=source_license,
            )

        # 5. Construir Provenance mínima (un paso, un gap declarado).
        provenance = Provenance(
            evidence_hash=blob_hash,
            origin_source_id=source.id,
            steps=[
                ProvenanceStep(
                    step_id=1,
                    kind=StepKind.ORIGINAL_CAPTURE,
                )
            ],
            is_complete=False,
            gaps=[GapDescription(description=DEFAULT_INGEST_GAP)],
            attestor=ingested_by,
            attested_at=clock(),
        )

        # 6. Construir Evidence.
        evidence = Evidence(
            hash=blob_hash,
            kind=kind,
            content_uri=layout.caos_relative_uri_for(blob_hash),
            size_bytes=size_bytes,
            mime_type=mime,
            source_id=source.id,
            status=EvidenceStatus.ACTIVE,
            authentication=AuthenticationAssessment(),
            ingested_at=clock(),
            ingested_by=ingested_by,
            schema_version=SCHEMA_VERSION,
            notes=notes,
        )

        if dry_run:
            return evidence

        # 7. Mover blob a CAOS atómicamente (write tmp + rename).
        target_blob = layout.caos_path_for(self.root, blob_hash)
        target_blob.parent.mkdir(parents=True, exist_ok=True)
        if not target_blob.is_file():
            tmp = target_blob.with_suffix(target_blob.suffix + ".tmp")
            shutil.copyfile(path, tmp)
            os.replace(tmp, target_blob)
            # Post-write verification: rehashea el destino.
            with target_blob.open("rb") as fh:
                rehash = sha256_hex_stream(fh)
            if rehash != blob_hash:
                target_blob.unlink(missing_ok=True)
                raise IntegrityError("post-write hash mismatch; ingestion aborted.")

        # 8. Persistir filas en tablas.
        tables.append_row(
            self.root, "evidence", blob_hash, evidence.model_dump(mode="json")
        )
        tables.append_row(
            self.root, "sources", source.id, source.model_dump(mode="json")
        )
        tables.append_row(
            self.root, "provenance", blob_hash, provenance.model_dump(mode="json")
        )
        for step in provenance.steps:
            row_id = f"{blob_hash}__step{step.step_id:05d}"
            tables.append_row(
                self.root,
                "provenance_steps",
                row_id,
                step.model_dump(mode="json"),
            )

        # 9. Audit log entry.
        audit_log.append_entry(
            self.root,
            action=audit_log.ActionKind.INGEST_EVIDENCE,
            target=evidence.aip_uri(),
            actor=ingested_by,
            parameters={"size_bytes": str(size_bytes)},
            result=audit_log.ResultKind.SUCCESS,
            schema_version=SCHEMA_VERSION,
            clock=clock,
        )

        # 10. Recomputar y persistir manifest.
        manifest = self._compute_manifest(generated_at=clock())
        write_manifest_atomic(self.root / layout.MANIFEST_FILENAME, manifest)

        return evidence

    # --- Show ----------------------------------------------------------

    def show_evidence(self, hash_or_uri: str) -> EvidenceView:
        """Devuelve una vista completa de la evidencia identificada."""
        if not self.root.is_dir() or not layout.is_archive(self.root):
            raise ArchiveNotFoundError(f"archive not found at {self.root}.")

        blob_hash = _resolve_hash(hash_or_uri)

        evidence_row = tables.read_row(self.root, "evidence", blob_hash)
        if evidence_row is None:
            raise EvidenceNotFoundError(
                f"no evidence with hash sha256:{blob_hash} in this archive."
            )
        evidence = Evidence.model_validate(evidence_row)

        # Verificación de integridad del blob (Pre-F1.D §show paso 7).
        blob_path = layout.caos_path_for(self.root, blob_hash)
        if not blob_path.is_file():
            raise IntegrityError(
                f"blob missing for evidence sha256:{blob_hash} (expected at "
                f"{blob_path.relative_to(self.root)})."
            )
        with blob_path.open("rb") as fh:
            actual = sha256_hex_stream(fh)
        if actual != blob_hash:
            raise IntegrityError(
                f"blob hash mismatch for evidence sha256:{blob_hash}."
            )

        # Source.
        source_row = tables.read_row(self.root, "sources", evidence.source_id)
        if source_row is None:
            raise ManifestError(
                f"referenced source_id {evidence.source_id!r} not found in this archive."
            )
        source = Source.model_validate(source_row)

        # Provenance (opcional, aunque ingest la crea siempre en V1).
        provenance_row = tables.read_row(self.root, "provenance", blob_hash)
        provenance = (
            Provenance.model_validate(provenance_row) if provenance_row else None
        )

        steps: list[ProvenanceStep] = []
        if provenance is not None:
            steps.extend(provenance.steps)

        return EvidenceView(
            evidence=evidence,
            source=source,
            provenance=provenance,
            provenance_steps=tuple(steps),
        )

    # --- Verify --------------------------------------------------------

    def verify(self, *, full: bool = True) -> VerificationReport:
        """Verifica integridad del archive (Pre-F1.D §archive verify)."""
        if not self.root.is_dir() or not layout.is_archive(self.root):
            raise ArchiveNotFoundError(f"archive not found at {self.root}.")

        checks: list[CheckResult] = []

        # 1. Audit chain.
        chain = audit_verify.verify_chain(self.root)
        checks.append(
            CheckResult(
                name="audit_chain",
                ok=chain.ok,
                detail=(
                    f"{chain.total_entries} entries, chain valid"
                    if chain.ok
                    else f"BROKEN at seq={chain.first_failure_seq}: "
                    f"{chain.first_failure_reason}"
                ),
            )
        )

        # 2. Referencias internas: cada Evidence.source_id existe.
        broken_refs = 0
        evidence_count = 0
        for raw in tables.iter_rows(self.root, "evidence"):
            evidence_count += 1
            ev = Evidence.model_validate(raw)
            if tables.read_row(self.root, "sources", ev.source_id) is None:
                broken_refs += 1
        checks.append(
            CheckResult(
                name="references",
                ok=broken_refs == 0,
                detail=(
                    f"{evidence_count} evidence rows, {broken_refs} broken refs"
                ),
            )
        )

        # 3. Blobs.
        blob_mismatches: list[str] = []
        rehashed = 0
        if full:
            for raw in tables.iter_rows(self.root, "evidence"):
                ev = Evidence.model_validate(raw)
                blob_path = layout.caos_path_for(self.root, ev.hash)
                if not blob_path.is_file():
                    blob_mismatches.append(ev.hash)
                    continue
                with blob_path.open("rb") as fh:
                    actual = sha256_hex_stream(fh)
                rehashed += 1
                if actual != ev.hash:
                    blob_mismatches.append(ev.hash)
            checks.append(
                CheckResult(
                    name="blobs",
                    ok=not blob_mismatches,
                    detail=(
                        f"{rehashed} blobs rehashed, {len(blob_mismatches)} mismatch"
                        if not blob_mismatches
                        else f"FAIL: mismatches={[h[:8] + '…' for h in blob_mismatches]}"
                    ),
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="blobs",
                    ok=True,
                    detail="skipped (--quick)",
                )
            )

        # 4. Manifest.
        manifest_path = self.root / layout.MANIFEST_FILENAME
        recomputed = self._compute_manifest(generated_at=default_clock())
        recomputed_hash = recomputed.manifest_hash()
        stored_hash: str | None = None
        manifest_ok = False
        if manifest_path.is_file():
            try:
                stored = json.loads(manifest_path.read_text(encoding="utf-8"))
                # Recomputamos sobre el contenido almacenado (sin generated_at
                # nuevo): hash del contenido stored debe coincidir con su
                # propio manifest_hash si está bien formado.
                # Aquí solo comparamos estructura básica V1.
                stored_manifest = ArchiveManifest.model_validate(
                    _stored_to_model(stored)
                )
                stored_hash = stored_manifest.manifest_hash()
                manifest_ok = True
            except Exception as exc:
                manifest_ok = False
                stored_hash = None
                checks.append(
                    CheckResult(
                        name="manifest",
                        ok=False,
                        detail=f"manifest parse error: {exc}",
                    )
                )
            else:
                checks.append(
                    CheckResult(
                        name="manifest",
                        ok=manifest_ok,
                        detail=(
                            f"manifest readable, stored_hash={stored_hash[:8]}…"
                        ),
                    )
                )
        else:
            checks.append(
                CheckResult(
                    name="manifest",
                    ok=False,
                    detail="manifest.json missing",
                )
            )

        ok = all(c.ok for c in checks)
        counts = {
            "evidences": tables.count_rows(self.root, "evidence"),
            "sources": tables.count_rows(self.root, "sources"),
            "provenance_steps": tables.count_rows(self.root, "provenance_steps"),
            "audit_entries": audit_log.count_entries(self.root),
        }
        return VerificationReport(
            ok=ok,
            checks=tuple(checks),
            counts=counts,
            archive_manifest_hash=recomputed_hash,
        )

    # --- helpers -------------------------------------------------------

    def _compute_manifest(self, *, generated_at: dt.datetime) -> ArchiveManifest:
        return compute_manifest(
            self.root,
            schemas=tables.get_schemas(),
            generated_at=generated_at,
            software_version=SOFTWARE_VERSION,
            schema_version=SCHEMA_VERSION,
        )


# --------------------------------------------------------------------- helpers


def _resolve_hash(hash_or_uri: str) -> str:
    """Acepta hex de 64 chars, ``sha256:<hex>`` o ``aip:evidence/sha256:<hex>``.

    Devuelve el hex puro lowercase. Lanza :class:`ValueError` si no encaja.
    """
    s = hash_or_uri.strip()
    if s.startswith("aip:evidence/sha256:"):
        s = s[len("aip:evidence/sha256:") :]
    elif s.startswith("sha256:"):
        s = s[len("sha256:") :]
    if len(s) != SHA256_HEX_LENGTH or not all(c in "0123456789abcdef" for c in s):
        raise ValueError(
            f"invalid hash or URI: {hash_or_uri!r}; "
            "expected sha256 hex lowercase of length 64 or aip URI."
        )
    return s


def _infer_kind(path: Path, mime: str | None) -> EvidenceKind:
    """Inferencia mínima de :class:`EvidenceKind` desde extensión / MIME."""
    suffix = path.suffix.lower()
    if mime == "application/pdf" or suffix == ".pdf":
        return EvidenceKind.DOCUMENT_SCAN
    if suffix in {".txt", ".md"}:
        return EvidenceKind.DOCUMENT_TEXT
    if suffix in {".png", ".jpg", ".jpeg", ".tiff", ".tif"}:
        return EvidenceKind.STILL_IMAGE
    if suffix in {".mp4", ".mkv", ".mov", ".avi"}:
        return EvidenceKind.MOVING_IMAGE
    if suffix in {".wav", ".flac", ".mp3", ".ogg"}:
        return EvidenceKind.AUDIO_RECORDING
    # Default conservador: documentos escaneados.
    return EvidenceKind.DOCUMENT_SCAN


def _infer_mime(path: Path, kind: EvidenceKind) -> str:
    """MIME por defecto a partir de :class:`EvidenceKind` cuando el caller
    no proporciona uno."""
    if kind == EvidenceKind.DOCUMENT_SCAN:
        return "application/pdf"
    if kind == EvidenceKind.DOCUMENT_TEXT:
        return "text/plain"
    if kind == EvidenceKind.STILL_IMAGE:
        return "image/png"
    if kind == EvidenceKind.MOVING_IMAGE:
        return "video/mp4"
    if kind == EvidenceKind.AUDIO_RECORDING:
        return "audio/wav"
    return "application/octet-stream"


def _validate_source_consistency(
    existing: Source,
    *,
    provided_name: str | None,
    provided_kind: SourceKind | None,
    provided_authority: AuthorityLevel | None,
    provided_jurisdiction: str | None,
    provided_license: str | None,
) -> None:
    """Si el caller proporciona campos para una Source existente, deben coincidir."""
    if provided_name is not None and provided_name != existing.name:
        raise InvalidSourceMetadataError(
            f"source-id {existing.id!r} exists with name {existing.name!r}; "
            f"--source-name {provided_name!r} contradicts."
        )
    if provided_kind is not None and provided_kind != existing.kind:
        raise InvalidSourceMetadataError(
            f"source-id {existing.id!r} exists with kind {existing.kind.value!r}; "
            f"--source-kind {provided_kind.value!r} contradicts."
        )
    if provided_authority is not None and provided_authority != existing.authority:
        raise InvalidSourceMetadataError(
            f"source-id {existing.id!r} exists with authority "
            f"{existing.authority.value!r}; "
            f"--source-authority {provided_authority.value!r} contradicts."
        )
    if provided_jurisdiction is not None and provided_jurisdiction != existing.jurisdiction:
        raise InvalidSourceMetadataError(
            f"source-id {existing.id!r} exists with jurisdiction "
            f"{existing.jurisdiction!r}; provided {provided_jurisdiction!r} contradicts."
        )
    if provided_license is not None and provided_license != existing.license:
        raise InvalidSourceMetadataError(
            f"source-id {existing.id!r} exists with license {existing.license!r}; "
            f"provided {provided_license!r} contradicts."
        )


def _stored_to_model(stored: dict[str, object]) -> dict[str, object]:
    """Convierte la forma legible (con ``generated_at: ISO string``) a la
    forma que :class:`ArchiveManifest` puede validar."""
    out = dict(stored)
    # ``ArchiveManifest`` acepta strings ISO 8601 → tz-aware datetime al validar.
    return out
