# scripts/

Utilidades auxiliares del mantenedor. **No** son código de producción.

Conforme a ADR-0030:

- No se distribuyen como parte del paquete `aip`.
- No están sujetas a los umbrales de cobertura del ADR-0031.
- No están sujetas a la disciplina de tipos estrictos.
- No deben importarse desde `src/aip/`.

Su único propósito es asistir al mantenedor en tareas operativas puntuales (preparación de fixtures, scripts de empaquetado, generadores de datos sintéticos para tests, etc.).

## Inventario

| Script | Propósito | Cuándo se ejecuta |
|---|---|---|
| `fetch_demo_fixture.py` | Descarga el PDF del Twining Memo, computa SHA-256, lo coloca en `tests/data/`, emite el bloque "Pinned values" listo para pegar en `docs/phase-1/demo-evidence-selection.md`. | Una vez, en Pre-F1.C, para cerrar la acción operativa que desbloquea los tests de reproducibilidad. |

## Ejemplo de uso de `fetch_demo_fixture.py`

```bash
python scripts/fetch_demo_fixture.py \
    --url "https://<fuente pública estable>/twining-memo.pdf" \
    --target tests/data/twining-memo-1947-09-23.pdf \
    --actor @jfhelvetius
```

El script imprime a `stderr` los logs del proceso y a `stdout` el bloque Markdown con los pinned values. Redirigir stdout permite copiarlos limpiamente.

El bloque emitido **no se inserta automáticamente** en `demo-evidence-selection.md`. El mantenedor lo pega manualmente y hace commit explícito con motivo (ADR-0030 C9 + disciplina del bus factor = 1).
