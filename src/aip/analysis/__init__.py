"""Capa analítica derivada (ADR-0032).

``aip.analysis`` aloja artefactos **derivados** del archive: lecturas estructuradas
y reproducibles del estado actual de Evidence + Source + Provenance, no nuevas
fuentes de verdad. Su contrato es:

- Sin red, sin APIs externas, sin ML, sin NLP, sin OCR, sin scoring probabilístico
  (ADR-0032 §restricciones).
- Salida determinista: mismo archive ⇒ mismo resultado.
- Borrar cualquier artefacto derivado no toca nunca la evidencia original
  (ADR-0032 §principio).

Subpaquetes V1:

- :mod:`aip.analysis.authentication` — motor de evaluación de autenticidad
  derivado, persiste en la tabla ``authentication_assessments`` ya prevista
  por ADR-0015 y reservada vacía hasta ADR-0032.
"""

from __future__ import annotations
