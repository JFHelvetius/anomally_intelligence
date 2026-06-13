"""Cross-operator multi-signature witness attestations (Door #3).

Permite que operadores distintos del que publicó un :class:`TransparencyManifest`
emitan firmas ed25519 atestiguando haber visto ese estado. La acumulación de
witnesses de operadores diversos hace progresivamente más caro coaccionar la
falsificación de la cadena.

Propiedades centrales:

- **Independencia del target.** El witness sólo necesita acceso al manifest
  publicado (descarga); no necesita acceso al archive del target operator.
- **Off-line verifiable.** Una :class:`WitnessAttestation` + la clave pública
  del witness son suficientes para que cualquier tercero verifique offline.
- **Acumulativo.** El target operator (o el portal de verificación pública)
  puede coleccionar witnesses indefinidamente. Cada uno adicional sube el
  costo de falsificación.

Lo que **NO** define el sistema:

- Quorum policy ("requiere 2-de-3"). Eso es decisión del verificador externo,
  no del archive. El sistema solo cuenta y verifica.
- Independencia real del witness. Que A y B sean dos operadores distintos en
  el sentido criptográfico (claves distintas) no garantiza que no sean la
  misma persona física. Auditar el grafo de relaciones es trabajo humano.
"""

from __future__ import annotations

from aip.transparency.witness.models import (
    ATTESTATION_TYPE,
    SIGNATURE_ALGORITHM,
    WITNESS_SCHEMA_VERSION,
    WitnessAttestation,
)
from aip.transparency.witness.signer import (
    compute_attestation_hash,
    sign_witness,
    verify_witness,
)
from aip.transparency.witness.store import (
    WITNESSES_DIRNAME,
    WitnessError,
    decode_witness,
    encode_witness,
    list_all_witnesses,
    list_witnesses_for_manifest,
    manifest_witnesses_dir,
    persist_witness,
    witness_path,
    witnesses_root,
)

__all__ = [
    "ATTESTATION_TYPE",
    "SIGNATURE_ALGORITHM",
    "WITNESSES_DIRNAME",
    "WITNESS_SCHEMA_VERSION",
    "WitnessAttestation",
    "WitnessError",
    "compute_attestation_hash",
    "decode_witness",
    "encode_witness",
    "list_all_witnesses",
    "list_witnesses_for_manifest",
    "manifest_witnesses_dir",
    "persist_witness",
    "sign_witness",
    "verify_witness",
    "witness_path",
    "witnesses_root",
]
