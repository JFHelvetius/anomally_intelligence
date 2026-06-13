"""Standalone Evidence Report HTML exporter.

Genera un fichero HTML único, auto-contenido, que cualquiera puede abrir en
cualquier navegador moderno sin backend. El HTML recomputa las hashes
client-side al cargar — el receptor (periodista, investigador externo) no
necesita confiar en quien lo emitió.

Verificaciones client-side incluidas en v1:

- Audit entry hashes: ``SHA-256(JCS(canonical_fields)) == entry_hash``
- Manifest hashes: ``SHA-256(JCS(manifest_excluding_self)) == manifest_hash``
- Capture certificate hash: ``SHA-256(JCS(cert_excluding_self)) == certificate_hash``
- Inference proof hashes: ``SHA-256(JCS(proof_excluding_self)) == proof_hash``
- Chain linkage: ``entry[N].prev_hash == entry[N-1].entry_hash``

Lo que NO verifica v1:

- Firmas ed25519 (manifest, witness, capture cert) — sólo las muestra
- Bitcoin merkle root vs block header — sólo muestra la afirmación
- Estructura del DAG de inference proofs — sólo verifica el self-hash

Para verificación criptográfica completa el receptor debe usar la CLI:
``aip transparency verify --public-key``, ``aip capture verify --public-key``, etc.
"""

from __future__ import annotations

from aip.report.builder import build_report_html, load_report_data

__all__ = [
    "build_report_html",
    "load_report_data",
]
