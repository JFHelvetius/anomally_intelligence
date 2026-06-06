# tests/data/

Fixtures binarios versionados usados por el suite de tests.

Cada binario lleva atribución, licencia y uso explícitos. No se admite ningún
binario sin entrada correspondiente en la tabla siguiente.

## Inventario

| Fichero | Fuente | Licencia | Usado por | Pinned values |
|---|---|---|---|---|
| `twining-memo-1947-09-23.pdf` | NARA / copia de dominio público (URL pendiente de Pre-F1.C) | Dominio público (17 U.S.C. § 105) | `tests/integration/demo_pipeline_test.py`, `tests/reproducibility/manifest_hash_test.py` | `docs/phase-1/demo-evidence-selection.md` |

## Restricciones (ADR-0031, ADR-0014, ADR-0020)

- Cada fichero debe poder versionarse cómodamente (≤ 5 MB indicativo).
- Sin información identificable de testigos vivos no consentida.
- Procedencia con licencia verificable (dominio público, CC, etc.).
- Añadir un fichero exige actualizar simultáneamente este README y la
  documentación correspondiente en `docs/phase-1/` (o sucesoras).
