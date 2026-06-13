"""AIP Capture-at-Source (Phase 2 / Door #2).

Extiende la cadena de procedencia HACIA ATRÁS en el tiempo respecto del
ingest: un :class:`CaptureCertificate` vincula el SHA-256 de un fichero al
momento de captura y operador declarados, *antes* de que el fichero entre
al archive. El ingest puede ocurrir minutos, horas o años después.

Propiedades centrales:

- **Independiente del archive.** El certificate se genera y verifica sin
  necesidad de un archive AIP — pure crypto sobre bytes de fichero.
- **Off-line verifiable.** Dado el certificate + clave pública + fichero,
  cualquier tercero verifica el vínculo bytes-operador-momento.
- **Origin-pinning.** Si el operador altera el fichero más tarde, su SHA-256
  cambia y la firma deja de cuadrar.

Limitaciones (consistente con ADR-0041):

- ``operator_id`` operator-supplied (sin PKI).
- ``captured_at`` operator-supplied (sin TSA).
- ``device_id`` operator-supplied (sin attestation de hardware).
- No prueba veracidad del contenido — sólo el vínculo bytes-operador-momento.
"""

from __future__ import annotations

from aip.capture.models import (
    CAPTURE_SCHEMA_VERSION,
    CERTIFICATE_TYPE,
    SIGNATURE_ALGORITHM,
    CaptureCertificate,
)
from aip.capture.signer import (
    compute_certificate_hash,
    hash_file,
    sign_capture,
    verify_capture,
)
from aip.capture.store import decode_certificate, encode_certificate

__all__ = [
    "CAPTURE_SCHEMA_VERSION",
    "CERTIFICATE_TYPE",
    "SIGNATURE_ALGORITHM",
    "CaptureCertificate",
    "compute_certificate_hash",
    "decode_certificate",
    "encode_certificate",
    "hash_file",
    "sign_capture",
    "verify_capture",
]
