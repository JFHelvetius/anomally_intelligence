"""AIP Transparency Log (Phase 1A).

Publica el estado del archive como manifests firmados encadenados — base
para verificación pública sin necesidad de confiar en el operador. El
portal estático (Phase 1B) y la publicación a Git público (Phase 1C) se
construyen sobre estos primitivos.

Propiedades centrales:

- **Off-line verifiable.** Dado un manifest y la clave pública del operador,
  cualquier tercero verifica firma + cadena sin acceso al archive.
- **Append-only.** ``previous_manifest_hash`` ata cada manifest al anterior;
  alterar uno viejo invalida la cadena hasta la cabeza.
- **State-pinning.** ``audit_chain_head_hash`` + ``archive_manifest_hash`` atan
  el manifest al estado completo del archive en el instante firmado.

Lo que **NO** prueba (consistente con ADR-0041):

- Identidad real del firmante (sin PKI).
- Momento absoluto (sin TSA — ``signed_at`` es operator-supplied).
- Veracidad del contenido — sólo el vínculo clave-estado.
"""

from __future__ import annotations

from aip.transparency.models import (
    MANIFEST_TYPE,
    SIGNATURE_ALGORITHM,
    TRANSPARENCY_SCHEMA_VERSION,
    ZERO_HASH,
    TransparencyManifest,
)
from aip.transparency.signer import (
    compute_manifest_hash,
    sign_manifest,
    verify_chain,
    verify_manifest,
)
from aip.transparency.state import ArchiveState, collect_archive_state
from aip.transparency.store import (
    LATEST_FILENAME,
    TRANSPARENCY_DIRNAME,
    TransparencyError,
    decode_manifest,
    detect_gaps,
    encode_manifest,
    latest_path,
    list_sequences,
    load_chain,
    load_latest,
    load_manifest,
    manifest_filename,
    manifest_path,
    persist_manifest,
    transparency_dir,
)

__all__ = [
    "LATEST_FILENAME",
    "MANIFEST_TYPE",
    "SIGNATURE_ALGORITHM",
    "TRANSPARENCY_DIRNAME",
    "TRANSPARENCY_SCHEMA_VERSION",
    "ZERO_HASH",
    "ArchiveState",
    "TransparencyError",
    "TransparencyManifest",
    "collect_archive_state",
    "compute_manifest_hash",
    "decode_manifest",
    "detect_gaps",
    "encode_manifest",
    "latest_path",
    "list_sequences",
    "load_chain",
    "load_latest",
    "load_manifest",
    "manifest_filename",
    "manifest_path",
    "persist_manifest",
    "sign_manifest",
    "transparency_dir",
    "verify_chain",
    "verify_manifest",
]
