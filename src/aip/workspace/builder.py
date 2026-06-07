"""Constructor, persistencia y verificación de Workspaces (ADR-0036).

Cero ejecución de motores analíticos. Las únicas operaciones permitidas:

- Lectura de ``<archive>/manifest.json`` para derivar ``source_manifest_hash``.
- Escritura de ``<archive>/workspaces/<id>.json`` para persistir.
- Hashing SHA-256 sobre strings canónicos.
- JCS canonicalization sobre estructuras JSON-compatibles.

No importa de ``aip.analysis``, ``aip.graph``, ``aip.impact`` ni
``aip.context`` — el test ``test_workspace_imports_no_engines`` lo
verifica estructuralmente vía AST.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.errors import AIPError
from aip.storage import layout
from aip.storage.manifest import ArchiveManifest
from aip.workspace.models import (
    ALLOWED_REFERENCE_TYPES,
    InvestigationWorkspace,
    WorkspaceReference,
)

WORKSPACES_DIRNAME: str = "workspaces"
"""Directorio bajo la raíz del archive donde se persisten workspaces.
**No** entra en ``V1_TABLES`` ni en ``compute_manifest`` — por
construcción el ``archive_manifest_hash`` es invariante ante operaciones
de workspace (ADR-0036 §persistencia + §G5)."""


# --------------------------------------------------------------------- errors


class InvalidReferenceTypeError(ValueError):
    """``reference_type`` fuera de la taxonomía cerrada de ADR-0036."""


class DuplicateReferenceError(ValueError):
    """Dos referencias con la misma ``(reference_type, identifier)``."""


class WorkspaceNotFoundError(AIPError):
    """El workspace solicitado no existe bajo ``<archive>/workspaces/``."""

    cli_exit_code = 1


# --------------------------------------------------------------------- hashing


def compute_artifact_hash(reference_type: str, identifier: str) -> str:
    """SHA-256 hex de la cadena canónica ``f"{reference_type}:{identifier}"``.

    Pura función de los strings de la referencia. **Cero acceso al
    archive, cero ejecución de motores** (G3). El hash funciona como
    huella verificable del par sin necesidad de resolver el artefacto.
    """
    if reference_type not in ALLOWED_REFERENCE_TYPES:
        raise InvalidReferenceTypeError(
            f"invalid reference_type {reference_type!r}; "
            f"must be one of {sorted(ALLOWED_REFERENCE_TYPES)}."
        )
    if not identifier:
        raise ValueError("identifier must be non-empty.")
    canonical = f"{reference_type}:{identifier}"
    return sha256_hex(canonical.encode("utf-8"))


def compute_workspace_hash(workspace: InvestigationWorkspace) -> str:
    """SHA-256 hex de la canonicalización JCS del workspace **excluyendo**
    el campo ``workspace_hash``. Mismo patrón que ``ContextBundle``."""
    data = dataclasses.asdict(workspace)
    data.pop("workspace_hash", None)
    normalized = cast(JsonValue, _normalize_for_jcs(data))
    return sha256_hex(jcs_canonicalize(normalized))


def verify_workspace_hash(workspace: InvestigationWorkspace) -> bool:
    """Verifica que ``workspace_hash`` coincide con su recomputo offline.

    Devuelve ``True`` si la auto-consistencia se mantiene. No requiere
    acceso al archive — propiedad estructural del workspace (G4).
    """
    return compute_workspace_hash(workspace) == workspace.workspace_hash


# --------------------------------------------------------------------- create


def create_workspace(
    *,
    archive_root: Path,
    workspace_id: str,
    title: str,
    references_input: Iterable[tuple[str, str]],
) -> InvestigationWorkspace:
    """Construye un :class:`InvestigationWorkspace` determinista.

    Args:
        archive_root: Raíz del archive AIP (debe ser archive válido con
            ``manifest.json`` presente, requerido para
            ``source_manifest_hash``).
        workspace_id: Identidad ASCII-safe del workspace.
        title: Título legible del workspace.
        references_input: Iterable de pares
            ``(reference_type, identifier)``. Duplicados ``(type,
            identifier)`` → ``DuplicateReferenceError``.

    Raises:
        InvalidReferenceTypeError: si algún ``reference_type`` es inválido.
        DuplicateReferenceError: si hay duplicados en ``references_input``.
        FileNotFoundError: si ``manifest.json`` no existe en el archive.
    """
    if not archive_root.is_dir() or not layout.is_archive(archive_root):
        raise FileNotFoundError(
            f"archive not found or invalid at {archive_root}."
        )
    manifest_path = archive_root / layout.MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"manifest.json missing at {manifest_path}; "
            "required to derive source_manifest_hash."
        )
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored_manifest = ArchiveManifest.model_validate(stored)
    source_manifest_hash = stored_manifest.manifest_hash()

    # Detección temprana de duplicados antes de construir el modelo
    # (para devolver el error específico, no el genérico del dataclass).
    seen: set[tuple[str, str]] = set()
    refs: list[WorkspaceReference] = []
    for ref_type, identifier in references_input:
        if ref_type not in ALLOWED_REFERENCE_TYPES:
            raise InvalidReferenceTypeError(
                f"invalid reference_type {ref_type!r}; "
                f"must be one of {sorted(ALLOWED_REFERENCE_TYPES)}."
            )
        key = (ref_type, identifier)
        if key in seen:
            raise DuplicateReferenceError(
                f"duplicate reference {key} in workspace inputs (ADR-0036 §G7)."
            )
        seen.add(key)
        refs.append(
            WorkspaceReference(
                reference_type=ref_type,
                identifier=identifier,
                artifact_hash=compute_artifact_hash(ref_type, identifier),
            )
        )

    sorted_refs = tuple(sorted(refs))

    # Construir bundle parcial con workspace_hash placeholder y luego
    # rellenarlo. Patrón AuditEntry.entry_hash / ContextBundle.context_bundle_hash.
    partial = InvestigationWorkspace(
        workspace_id=workspace_id,
        title=title,
        references=sorted_refs,
        source_manifest_hash=source_manifest_hash,
        workspace_hash="0" * 64,
    )
    final_hash = compute_workspace_hash(partial)
    return dataclasses.replace(partial, workspace_hash=final_hash)


# --------------------------------------------------------------------- persistence


def workspace_path(archive_root: Path, workspace_id: str) -> Path:
    """Path canónico de un workspace bajo el archive (ADR-0036 §persistencia)."""
    return archive_root / WORKSPACES_DIRNAME / f"{workspace_id}.json"


def persist_workspace(
    workspace: InvestigationWorkspace,
    *,
    archive_root: Path,
    extra_output: Path | None = None,
) -> Path:
    """Persiste el workspace en su localización canónica + opcional copia.

    Siempre escribe ``<archive>/workspaces/<workspace_id>.json``. Si
    ``extra_output`` se proporciona, también escribe ahí (idéntico
    contenido). Devuelve el path canónico.
    """
    archive_target = workspace_path(archive_root, workspace.workspace_id)
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    payload = encode_workspace(workspace)
    archive_target.write_text(payload, encoding="utf-8")
    if extra_output is not None:
        extra_output.parent.mkdir(parents=True, exist_ok=True)
        extra_output.write_text(payload, encoding="utf-8")
    return archive_target


def load_workspace(
    *, archive_root: Path, workspace_id: str
) -> InvestigationWorkspace:
    """Carga un workspace desde su localización canónica."""
    target = workspace_path(archive_root, workspace_id)
    if not target.is_file():
        raise WorkspaceNotFoundError(
            f"workspace {workspace_id!r} not found at {target}."
        )
    return decode_workspace(target.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- encoding


def encode_workspace(workspace: InvestigationWorkspace) -> str:
    """Serializa un workspace a JSON canónico (``sort_keys=True``).

    Termina con newline (mismo patrón que ``write_manifest_atomic``).
    """
    data = dataclasses.asdict(workspace)
    normalized = _normalize_for_jcs(data)
    return (
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def decode_workspace(payload: str) -> InvestigationWorkspace:
    """Reconstruye un workspace desde su JSON canónico."""
    data = json.loads(payload)
    refs_data = data.get("references", [])
    references = tuple(
        WorkspaceReference(
            reference_type=r["reference_type"],
            identifier=r["identifier"],
            artifact_hash=r["artifact_hash"],
        )
        for r in refs_data
    )
    return InvestigationWorkspace(
        workspace_id=data["workspace_id"],
        title=data["title"],
        references=references,
        source_manifest_hash=data["source_manifest_hash"],
        workspace_hash=data["workspace_hash"],
        schema_version=data.get("schema_version", ""),
    )


# --------------------------------------------------------------------- internals


def _normalize_for_jcs(obj: object) -> object:
    """Convierte tuplas a listas recursivamente para JCS (ver
    ``aip.context.assembler._normalize_for_jcs``)."""
    if isinstance(obj, tuple):
        return [_normalize_for_jcs(x) for x in obj]
    if isinstance(obj, list):
        return [_normalize_for_jcs(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_for_jcs(v) for k, v in obj.items()}
    return obj
