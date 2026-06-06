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

V1 implementa dos acciones (ADR-0023):

- :attr:`ActionKind.ARCHIVE_BOOTSTRAP` — primera entrada de un archive nuevo.
- :attr:`ActionKind.INGEST_EVIDENCE` — ingesta de un blob como evidencia.

Otras acciones del ADR-0019 (``create_claim``, ``revise_case``, ``enclave_access``,
etc.) están diferidas. Cuando se incorporen, deberán añadirse a esta enum sin
romper la cadena histórica (la enum es por valor, los valores existentes son
estables).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Iterator
from enum import Enum
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aip.core.hashing import hash_object
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


class ActionKind(str, Enum):
    """Acciones registrables en el audit log (subset V1)."""

    ARCHIVE_BOOTSTRAP = "archive_bootstrap"
    INGEST_EVIDENCE = "ingest_evidence"


class ResultKind(str, Enum):
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

    def to_canonical_dict(self) -> dict[str, object]:
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
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
) -> dict[str, object]:
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
    timestamp = raw_timestamp.astimezone(dt.timezone.utc).replace(microsecond=0)

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
