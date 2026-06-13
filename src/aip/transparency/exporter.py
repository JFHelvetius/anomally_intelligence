"""Exportar el transparency log como bundle estático portable (Phase 1C).

El bundle es una carpeta auto-contenida que cualquier servidor estático
(GitHub Pages, S3, IPFS, ``python -m http.server``) puede servir. Permite
que el portal de verificación opere sin ningún backend del operador — solo
descarga JSON + PEM y verifica criptográficamente client-side.

Layout del bundle:

    <out>/
        index.json              ← metadata + manifest summaries (entry point)
        public-key.pem          ← clave pública del operador (PEM SPKI)
        latest.json             ← copia del manifest más reciente
        manifest-000000.json    ← uno por secuencia, bytes idénticos al archive
        manifest-000001.json
        ...
        README.md               ← explicación humana del bundle

El ``index.json`` lleva todos los campos de resumen necesarios para que el
portal arranque sin descargar cada manifest individual primero.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any

from aip.errors import AIPError
from aip.notarize import (
    OTS_EXTENSION,
    decode_dtf_from_bytes,
    verify_proof,
)
from aip.storage.atomic_io import atomic_write_text
from aip.transparency.store import (
    LATEST_FILENAME,
    TRANSPARENCY_DIRNAME,
    decode_manifest,
    list_sequences,
    manifest_filename,
    manifest_path,
)
from aip.transparency.witness import (
    WITNESSES_DIRNAME,
    list_all_witnesses,
)

BUNDLE_TYPE = "aip.transparency.bundle.v1"
BUNDLE_SCHEMA_VERSION = "1"
INDEX_FILENAME = "index.json"
PUBLIC_KEY_FILENAME = "public-key.pem"
README_FILENAME = "README.md"


def _summary_entry(
    manifest_dict: dict[str, Any],
    witness_summaries: list[dict[str, Any]],
    notarization: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resumen incrustado en ``index.json`` por manifest. Incluye witnesses y
    notarization para que el portal arranque sin extra round-trips."""
    return {
        "sequence": manifest_dict["sequence"],
        "filename": manifest_filename(manifest_dict["sequence"]),
        "manifest_hash": manifest_dict["manifest_hash"],
        "previous_manifest_hash": manifest_dict["previous_manifest_hash"],
        "audit_chain_head_hash": manifest_dict["audit_chain_head_hash"],
        "audit_entry_count": manifest_dict["audit_entry_count"],
        "evidence_count": manifest_dict["evidence_count"],
        "attestation_count": manifest_dict["attestation_count"],
        "workspace_count": manifest_dict["workspace_count"],
        "timeline_count": manifest_dict["timeline_count"],
        "snapshot_count": manifest_dict["snapshot_count"],
        "justification_count": manifest_dict["justification_count"],
        "signed_at": manifest_dict["signed_at"],
        "operator_id": manifest_dict["operator_id"],
        "public_key_fingerprint": manifest_dict["public_key_fingerprint"],
        "witnesses": witness_summaries,
        "witness_count": len(witness_summaries),
        "notarization": notarization,
    }


def _ots_summary(ots_path: Path) -> dict[str, Any] | None:
    """Parsea un fichero .ots y devuelve resumen de anclajes Bitcoin + pendings.

    Devuelve ``None`` si el fichero no existe o no se puede parsear. Si existe
    pero todavía no tiene atestación Bitcoin (recién submitted), devuelve un
    dict con ``bitcoin_anchors=[]`` y ``pending_count>0`` — el portal lo
    muestra como "pending notarization".
    """
    if not ots_path.is_file():
        return None
    try:
        ots_bytes = ots_path.read_bytes()
        dtf = decode_dtf_from_bytes(ots_bytes)
        # verify_proof requires expected_sha256 == proof leaf; we use the
        # leaf itself so the file_hash_matches branch is satisfied — what
        # we want here is the walk of the tree to extract claims, not a
        # bind to a specific file.
        result = verify_proof(dtf, expected_sha256=dtf.file_digest)
    except (OSError, ValueError):
        return None
    return {
        "ots_filename": ots_path.name,
        "leaf_sha256": dtf.file_digest.hex(),
        "bitcoin_anchors": [
            {
                "height": c.height,
                "expected_merkle_root_le_hex": c.expected_merkle_root_le.hex(),
            }
            for c in result.bitcoin_claims
        ],
        "pending_count": len(result.pending_claims),
        "pending_calendars": [p.calendar_uri for p in result.pending_claims],
    }


def _build_witness_summaries(
    seq: int, all_witnesses: dict[int, Any]
) -> list[dict[str, Any]]:
    """Lista de resúmenes de witness para un manifest concreto."""
    out: list[dict[str, Any]] = []
    for w in all_witnesses.get(seq, []):
        out.append(
            _witness_summary(
                seq,
                w.attestation_hash,
                {
                    "witness_operator_id": w.witness_operator_id,
                    "witness_public_key_fingerprint": w.witness_public_key_fingerprint,
                    "witnessed_at": w.witnessed_at,
                    "statement": w.statement,
                },
            )
        )
    return out


def _witness_summary(
    seq: int, attestation_hash: str, witness_dict: dict[str, Any]
) -> dict[str, Any]:
    """Resumen ligero por witness incrustado en ``index.json``."""
    return {
        "attestation_hash": attestation_hash,
        "filename": (
            f"{WITNESSES_DIRNAME}/manifest-{seq:06d}/{attestation_hash}.json"
        ),
        "witness_operator_id": witness_dict["witness_operator_id"],
        "witness_public_key_fingerprint": witness_dict[
            "witness_public_key_fingerprint"
        ],
        "witnessed_at": witness_dict["witnessed_at"],
        "statement": witness_dict.get("statement"),
    }


def _render_readme(
    *,
    operator_id: str,
    fingerprint: str,
    exported_at: str,
    manifest_count: int,
    first_seq: int,
    last_seq: int,
) -> str:
    fp_short = fingerprint[:24]
    seq_range = f"{first_seq}..{last_seq}"
    return f"""# AIP Transparency Log Bundle

| Operator | Fingerprint | Exported | Manifests |
|---|---|---|---|
| `{operator_id}` | `{fp_short}…` | `{exported_at}` | {manifest_count} (seq {seq_range}) |

## Qué es esto

Un transparency log firmado del archive AIP. Cada `manifest-NNNNNN.json`
es una snapshot ed25519-firmada del estado del archive en un instante. La
cadena `previous_manifest_hash` ata cada manifest al anterior: manipular
uno viejo invalida todos los posteriores. Cualquier tercero puede verificar
offline usando `public-key.pem` sin necesidad de confiar en el operador
ni acceder al archive original.

## Cómo verificar

**Vía portal web** — abre el AIP Transparency Portal, configura la URL del
bundle apuntando al directorio que contiene este README, y el portal
verificará automáticamente todos los manifests client-side (SHA-256(JCS) +
ed25519).

**Vía CLI** — si tienes los manifests bajo `<archive>/transparency/`:

```
aip transparency verify --chain --archive-root <archive> --public-key public-key.pem
```

## Layout

- `index.json` — metadata del bundle + resúmenes de manifests (entry point)
- `public-key.pem` — clave pública del operador (PEM SubjectPublicKeyInfo)
- `latest.json` — copia del manifest más reciente
- `manifest-NNNNNN.json` — un fichero por secuencia, bytes idénticos al archive

## Trust model

- `public-key.pem` identifica al operador. Su fingerprint SHA-256 del DER
  aparece en cada manifest (`public_key_fingerprint`).
- Si el operador rota su clave, cambia el fingerprint — el portal lo detecta.
- No hay PKI: la identidad real del operador está fuera de este sistema. Lo
  único que se prueba es el vínculo clave-estado.
- No hay TSA: el `signed_at` lo provee el operador. Es operator-supplied.

Generado por `aip transparency export` (Phase 1C).
"""


def export_bundle(
    archive_root: Path,
    out_dir: Path,
    *,
    exported_at: dt.datetime,
) -> dict[str, Any]:
    """Exporta el transparency log de ``archive_root`` a ``out_dir``.

    Pre-condiciones:

    - ``archive_root/transparency/`` existe y tiene al menos un manifest.
    - ``archive_root/transparency/public-key.pem`` existe.

    Devuelve un dict resumen con counts + paths absolutos.
    Idempotente: re-ejecutarlo sobre el mismo ``out_dir`` reemplaza los
    ficheros sin warning. No borra ficheros del bundle que no existan ya
    en el archive — los deja para que el operador limpie manualmente si
    desea.
    """
    if not archive_root.is_dir():
        raise AIPError(f"archive root not found: {archive_root}")

    src_dir = archive_root / TRANSPARENCY_DIRNAME
    if not src_dir.is_dir():
        raise AIPError(
            f"archive has no transparency log at {src_dir}. "
            "Run 'aip transparency publish' first."
        )

    sequences = list_sequences(archive_root)
    if not sequences:
        raise AIPError(
            f"no manifests in {src_dir}. "
            "Run 'aip transparency publish' before exporting."
        )

    src_pk = src_dir / PUBLIC_KEY_FILENAME
    if not src_pk.is_file():
        raise AIPError(
            f"operator public key not published at {src_pk}. "
            "Copy your ed25519 PEM SPKI public key there before exporting."
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── collect witnesses up-front (Door #3) ────────────────────────
    # Pre-leemos los witnesses persistidos en el archive para sumarizarlos
    # en index.json y copiarlos a la subcarpeta witnesses/ del bundle.
    all_witnesses = list_all_witnesses(archive_root)

    # ── copy manifests + build summaries (incl. witnesses & .ots) ────
    manifest_summaries: list[dict[str, Any]] = []
    notarized_count = 0
    bitcoin_anchored_count = 0
    for seq in sequences:
        src = manifest_path(archive_root, seq)
        shutil.copy2(src, out_dir / src.name)
        data = json.loads(src.read_text(encoding="utf-8"))

        witness_summaries = _build_witness_summaries(seq, all_witnesses)

        # OpenTimestamps sidecar (Phase 4 integration). Convention from CLI:
        # the .ots lives next to the manifest with the manifest's filename
        # + ".ots" suffix.
        ots_src = src.with_suffix(src.suffix + OTS_EXTENSION)
        notarization = _ots_summary(ots_src)
        if notarization is not None:
            notarized_count += 1
            if notarization["bitcoin_anchors"]:
                bitcoin_anchored_count += 1
            shutil.copy2(ots_src, out_dir / ots_src.name)

        manifest_summaries.append(
            _summary_entry(data, witness_summaries, notarization)
        )

    # ── copy witnesses preserving manifest-NNNNNN/ structure ─────────
    src_witnesses_root = src_dir / WITNESSES_DIRNAME
    if src_witnesses_root.is_dir():
        dst_witnesses_root = out_dir / WITNESSES_DIRNAME
        dst_witnesses_root.mkdir(parents=True, exist_ok=True)
        for seq, witnesses in all_witnesses.items():
            seq_dir_src = src_witnesses_root / f"manifest-{seq:06d}"
            seq_dir_dst = dst_witnesses_root / f"manifest-{seq:06d}"
            seq_dir_dst.mkdir(parents=True, exist_ok=True)
            for w in witnesses:
                file_src = seq_dir_src / f"{w.attestation_hash}.json"
                if file_src.is_file():
                    shutil.copy2(file_src, seq_dir_dst / file_src.name)

    # ── copy public key ─────────────────────────────────────────────
    shutil.copy2(src_pk, out_dir / PUBLIC_KEY_FILENAME)

    # ── copy latest.json ────────────────────────────────────────────
    src_latest = src_dir / LATEST_FILENAME
    if src_latest.is_file():
        shutil.copy2(src_latest, out_dir / LATEST_FILENAME)

    # ── build index.json ────────────────────────────────────────────
    last_manifest = decode_manifest(
        manifest_path(archive_root, sequences[-1]).read_text(encoding="utf-8")
    )
    exported_iso = (
        exported_at.astimezone(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    total_witnesses = sum(len(ws) for ws in all_witnesses.values())
    index = {
        "$type": BUNDLE_TYPE,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "exported_at": exported_iso,
        "operator": {
            "id": last_manifest.operator_id,
            "public_key_fingerprint": last_manifest.public_key_fingerprint,
            "public_key_file": PUBLIC_KEY_FILENAME,
        },
        "manifests": manifest_summaries,
        "head": {
            "sequence": last_manifest.sequence,
            "manifest_hash": last_manifest.manifest_hash,
            "signed_at": last_manifest.signed_at,
            "audit_chain_head_hash": last_manifest.audit_chain_head_hash,
        },
        "total_witnesses": total_witnesses,
        "manifests_with_witnesses": sum(
            1 for ws in all_witnesses.values() if ws
        ),
        "notarized_count": notarized_count,
        "bitcoin_anchored_count": bitcoin_anchored_count,
    }
    atomic_write_text(
        out_dir / INDEX_FILENAME,
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    # ── README ──────────────────────────────────────────────────────
    atomic_write_text(
        out_dir / README_FILENAME,
        _render_readme(
            operator_id=last_manifest.operator_id,
            fingerprint=last_manifest.public_key_fingerprint,
            exported_at=exported_iso,
            manifest_count=len(sequences),
            first_seq=sequences[0],
            last_seq=sequences[-1],
        ),
    )

    return {
        "ok": True,
        "out_dir": str(out_dir),
        "manifest_count": len(sequences),
        "first_sequence": sequences[0],
        "last_sequence": sequences[-1],
        "operator_id": last_manifest.operator_id,
        "public_key_fingerprint": last_manifest.public_key_fingerprint,
        "head_manifest_hash": last_manifest.manifest_hash,
        "exported_at": exported_iso,
        "witness_count": total_witnesses,
        "manifests_with_witnesses": sum(
            1 for ws in all_witnesses.values() if ws
        ),
        "notarized_count": notarized_count,
        "bitcoin_anchored_count": bitcoin_anchored_count,
    }
