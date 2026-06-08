"""Audit log append-only con cadena de hashes (ADR-0019).

Formato de almacenamiento: **JSONL** (un JSON canonicalizado por línea) en el
fichero ``audit.log`` en la raíz del archive. Cada línea contiene una entrada
con todos sus campos incluyendo ``entry_hash``.

Cada entrada lleva ``prev_hash`` apuntando al ``entry_hash`` de la anterior,
formando una cadena verificable. La entrada de bootstrap (``seq=0``) tiene
``prev_hash = "0" * 64`` como sentinela.

El reloj (``clock``) se inyecta para que los tests sean reproducibles bit a
bit (ADR-0031 R1, R7). En producción se usa
``datetime.now(timezone.utc).replace(microsecond=0)``.

Acciones registradas (ADR-0023 + ADR-0019 §enmienda E1):

Capa base:

- :attr:`ActionKind.ARCHIVE_BOOTSTRAP` — primera entrada de un archive nuevo.
- :attr:`ActionKind.INGEST_EVIDENCE` — ingesta de un blob como evidencia.

Capa derivada (ADR-0019 §enmienda E1, 2026-06-07): cada operación que
persiste un artefacto derivado en su localización canónica del archive
emite una entry. Esto extiende la cadena hash-chained desde "1/9 dominios"
a "6/6 dominios con estado persistido":

- :attr:`ActionKind.ASSESS_AUTHENTICATION` — fila nueva en la tabla
  ``authentication_assessments`` (ADR-0032).
- :attr:`ActionKind.BUILD_WORKSPACE` — ``<archive>/workspaces/<id>.json``
  (ADR-0036).
- :attr:`ActionKind.BUILD_TIMELINE` — ``<archive>/timelines/<id>.json``
  (ADR-0037).
- :attr:`ActionKind.BUILD_SNAPSHOT` — ``<archive>/snapshots/<id>.json``
  (ADR-0038).
- :attr:`ActionKind.BUILD_JUSTIFICATION` —
  ``<archive>/justifications/<id>.json`` (ADR-0040).
- :attr:`ActionKind.SIGN_ATTESTATION` —
  ``<archive>/attestations/<id>.json`` (ADR-0041).

Deliberadamente excluidas en V1: ``COMPUTE_DIFF`` y ``ASSEMBLE_CONTEXT``.
Diff (ADR-0039) y Context Bundle (ADR-0035) no tienen localización
canónica en el archive — son artefactos emitidos por la CLI a stdout o a
``--output``. Añadirlos al audit log sería un error de categoría
(registraría ejecución de queries, no cambios de estado del archive).

Otras acciones del ADR-0019 originales (``create_claim``, ``revise_case``,
``enclave_access``, etc.) siguen diferidas por ADR-0023.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Iterator
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aip.core.hashing import JsonValue, hash_object
from aip.storage.layout import AUDIT_LOG_FILENAME

# --------------------------------------------------------------------- constants

ZERO_HASH: Final[str] = "0" * 64
"""Hash sentinela para ``prev_hash`` de la entrada de bootstrap."""

BOOTSTRAP_TARGET: Final[str] = "aip:archive/bootstrap"
"""URI sentinela del target del bootstrap. No es resolvable; identifica el
evento de creación del archive en sí."""

_SHA256_HEX_PATTERN: Final[str] = r"^[a-f0-9]{64}$"

Sha256Hex = Annotated[
    str,
    Field(pattern=_SHA256_HEX_PATTERN, min_length=64, max_length=64),
]


# --------------------------------------------------------------------- enums


class ActionKind(StrEnum):
    """Acciones registrables en el audit log.

    Los valores string son **estables forever** — modificarlos invalidaría
    cadenas históricas. Añadir un nuevo valor es seguro; renombrar /
    eliminar uno existente NO lo es.
    """

    # --- Capa base (V1 original) -------------------------------------
    ARCHIVE_BOOTSTRAP = "archive_bootstrap"
    INGEST_EVIDENCE = "ingest_evidence"
    # --- Capa derivada (ADR-0019 §enmienda E1, 2026-06-07) -----------
    ASSESS_AUTHENTICATION = "assess_authentication"
    BUILD_WORKSPACE = "build_workspace"
    BUILD_TIMELINE = "build_timeline"
    BUILD_SNAPSHOT = "build_snapshot"
    BUILD_JUSTIFICATION = "build_justification"
    SIGN_ATTESTATION = "sign_attestation"


class ResultKind(StrEnum):
    """Resultado de la acción auditada."""

    SUCCESS = "success"
    FAILURE = "failure"


# --------------------------------------------------------------------- type


class AuditEntry(BaseModel):
    """Entrada inmutable del audit log (ADR-0019)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int = Field(ge=0)
    prev_hash: Sha256Hex
    timestamp: dt.datetime
    actor: str = Field(min_length=1)
    action: ActionKind
    target: str = Field(min_length=1)
    parameters: dict[str, str] = Field(default_factory=dict)
    result: ResultKind
    schema_version: str = Field(min_length=1)
    entry_hash: Sha256Hex

    @field_validator("timestamp")
    @classmethod
    def _timestamp_tz_aware_and_no_subsecond(
        cls, value: dt.datetime
    ) -> dt.datetime:
        if value.tzinfo is None:
            raise ValueError(
                "AuditEntry.timestamp must be timezone-aware (use UTC)."
            )
        if value.microsecond != 0:
            raise ValueError(
                "AuditEntry.timestamp must have microsecond=0 for canonical "
                "reproducibility (ADR-0024 L2)."
            )
        return value

    def to_canonical_dict(self) -> dict[str, JsonValue]:
        """Estructura JCS-compatible (con timestamp ISO Z) **incluyendo**
        ``entry_hash``. Útil para serializar a JSONL."""
        return {
            **_base_canonical_dict(
                seq=self.seq,
                prev_hash=self.prev_hash,
                timestamp=self.timestamp,
                actor=self.actor,
                action=self.action,
                target=self.target,
                parameters=self.parameters,
                result=self.result,
                schema_version=self.schema_version,
            ),
            "entry_hash": self.entry_hash,
        }


# --------------------------------------------------------------------- helpers


def _format_utc_second(value: dt.datetime) -> str:
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_canonical_dict(
    *,
    seq: int,
    prev_hash: str,
    timestamp: dt.datetime,
    actor: str,
    action: ActionKind,
    target: str,
    parameters: dict[str, str],
    result: ResultKind,
    schema_version: str,
) -> dict[str, JsonValue]:
    """Diccionario canónico SIN ``entry_hash`` (lo que se hashea)."""
    return {
        "seq": seq,
        "prev_hash": prev_hash,
        "timestamp": _format_utc_second(timestamp),
        "actor": actor,
        "action": action.value,
        "target": target,
        "parameters": dict(parameters),
        "result": result.value,
        "schema_version": schema_version,
    }


def compute_entry_hash(
    *,
    seq: int,
    prev_hash: str,
    timestamp: dt.datetime,
    actor: str,
    action: ActionKind,
    target: str,
    parameters: dict[str, str],
    result: ResultKind,
    schema_version: str,
) -> str:
    """SHA-256 hex del JCS de los campos canónicos (sin ``entry_hash``)."""
    return hash_object(
        _base_canonical_dict(
            seq=seq,
            prev_hash=prev_hash,
            timestamp=timestamp,
            actor=actor,
            action=action,
            target=target,
            parameters=parameters,
            result=result,
            schema_version=schema_version,
        )
    )


def _log_path(root: Path) -> Path:
    return root / AUDIT_LOG_FILENAME


# --------------------------------------------------------------------- reads


def iter_entries(root: Path) -> Iterator[AuditEntry]:
    """Itera todas las entradas del audit log en orden de aparición.

    Si el fichero no existe, no produce nada.
    """
    log_path = _log_path(root)
    if not log_path.is_file():
        return
    with log_path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            data = json.loads(line)
            yield AuditEntry.model_validate(data)


def last_entry(root: Path) -> AuditEntry | None:
    """Devuelve la última entrada o ``None`` si el log no existe o está vacío."""
    last: AuditEntry | None = None
    for entry in iter_entries(root):
        last = entry
    return last


def count_entries(root: Path) -> int:
    """Número de entradas en el audit log."""
    return sum(1 for _ in iter_entries(root))


# --------------------------------------------------------------------- writes


def append_entry(
    root: Path,
    *,
    action: ActionKind,
    target: str,
    actor: str,
    parameters: dict[str, str] | None = None,
    result: ResultKind = ResultKind.SUCCESS,
    schema_version: str,
    clock: Callable[[], dt.datetime],
) -> AuditEntry:
    """Construye y persiste una nueva entrada del audit log.

    Lee la última entrada existente para calcular ``seq`` y ``prev_hash``.
    El timestamp viene del ``clock`` inyectado (se descartan microsegundos).
    """
    parameters = dict(parameters or {})
    previous = last_entry(root)
    if previous is None:
        seq = 0
        prev_hash = ZERO_HASH
    else:
        seq = previous.seq + 1
        prev_hash = previous.entry_hash

    raw_timestamp = clock()
    if raw_timestamp.tzinfo is None:
        raise ValueError("clock() must return a timezone-aware datetime.")
    timestamp = raw_timestamp.astimezone(dt.UTC).replace(microsecond=0)

    entry_hash = compute_entry_hash(
        seq=seq,
        prev_hash=prev_hash,
        timestamp=timestamp,
        actor=actor,
        action=action,
        target=target,
        parameters=parameters,
        result=result,
        schema_version=schema_version,
    )

    entry = AuditEntry(
        seq=seq,
        prev_hash=prev_hash,
        timestamp=timestamp,
        actor=actor,
        action=action,
        target=target,
        parameters=parameters,
        result=result,
        schema_version=schema_version,
        entry_hash=entry_hash,
    )

    log_path = _log_path(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Append-only. Encoding UTF-8 explícito; newline LF (ADR-0030 C9).
    with log_path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(entry.to_canonical_dict(), ensure_ascii=False) + "\n")

    return entry


def bootstrap(
    root: Path,
    *,
    actor: str,
    clock: Callable[[], dt.datetime],
    schema_version: str,
) -> AuditEntry | None:
    """Escribe la entrada de bootstrap si el log aún no existe.

    Devuelve la entrada nueva si la creó, o ``None`` si el log ya tenía
    entradas (operación idempotente).
    """
    if last_entry(root) is not None:
        return None
    return append_entry(
        root,
        action=ActionKind.ARCHIVE_BOOTSTRAP,
        target=BOOTSTRAP_TARGET,
        actor=actor,
        parameters={},
        result=ResultKind.SUCCESS,
        schema_version=schema_version,
        clock=clock,
    )


# --------------------------------------------------------------------- derived helper


def record_derived_artifact(
    root: Path,
    *,
    action: ActionKind,
    artifact_kind: str,
    artifact_id: str,
    self_hash: str,
    actor: str,
    clock: Callable[[], dt.datetime],
    schema_version: str,
    extra_parameters: dict[str, str] | None = None,
) -> AuditEntry:
    """Emite una entry de audit para la persistencia de un artefacto derivado.

    Helper compartido por los 6 puntos canónicos de persistencia derivada
    (ADR-0019 §enmienda E1). Construye un ``target`` con el esquema URI
    canónico (``aip:<kind>/<id>``) y un ``parameters`` que incluye al menos
    el self-hash del artefacto recién persistido.

    Args:
        root: raíz del archive.
        action: una de las :class:`ActionKind` de capa derivada
            (ASSESS_AUTHENTICATION, BUILD_WORKSPACE, BUILD_TIMELINE,
            BUILD_SNAPSHOT, BUILD_JUSTIFICATION, SIGN_ATTESTATION).
        artifact_kind: prefijo del URI (``workspace``, ``timeline``,
            ``snapshot``, ``justification``, ``attestation``, ``assessment``).
        artifact_id: identificador del artefacto.
        self_hash: hash auto-referente del artefacto persistido.
        actor: identificador del operador (operator-supplied; no
            autenticado por PKI en V1).
        clock: reloj inyectable (callable que devuelve datetime tz-aware).
        schema_version: SemVer del esquema lógico de datos.
        extra_parameters: parámetros adicionales opcionales que se
            mezclan con ``{"self_hash": self_hash}``.

    Raises:
        ValueError: si ``action`` no es de la capa derivada.
    """
    if action not in _DERIVED_ACTION_KINDS:
        raise ValueError(
            f"record_derived_artifact requires a derived ActionKind; "
            f"got {action!r}. Allowed: "
            f"{sorted(a.value for a in _DERIVED_ACTION_KINDS)}."
        )
    parameters: dict[str, str] = {"self_hash": self_hash}
    if extra_parameters is not None:
        parameters.update(extra_parameters)
    return append_entry(
        root,
        action=action,
        target=f"aip:{artifact_kind}/{artifact_id}",
        actor=actor,
        parameters=parameters,
        result=ResultKind.SUCCESS,
        schema_version=schema_version,
        clock=clock,
    )


_DERIVED_ACTION_KINDS: Final[frozenset[ActionKind]] = frozenset(
    {
        ActionKind.ASSESS_AUTHENTICATION,
        ActionKind.BUILD_WORKSPACE,
        ActionKind.BUILD_TIMELINE,
        ActionKind.BUILD_SNAPSHOT,
        ActionKind.BUILD_JUSTIFICATION,
        ActionKind.SIGN_ATTESTATION,
    }
)
"""Subconjunto de :class:`ActionKind` introducido por la enmienda E1 al
ADR-0019. Restringe :func:`record_derived_artifact` a la capa derivada."""
