"""Property-based tests sobre ``aip.audit.log`` + ``aip.audit.verify``.

Verifican que **toda cadena válida construida por la API** se valida bien,
y que **cualquier mutación de cualquier campo** rompe la verificación.

Cuatro invariantes que sostienen la cadena de evidencia del audit log:

1. **Construcción ⇒ verificación OK** para cualquier secuencia de inputs válidos.
2. **prev_hash chaining** correcto entry-a-entry.
3. **Mutación de campo de payload** ⇒ ``entry_hash mismatch``.
4. **Mutación de ``entry_hash``** ⇒ ``entry_hash mismatch``.

Si alguna invariante falla, la cadena audit deja de ser garantía estructural
contra tampering — bug arquitectónico crítico que invalidaría el release v0.1.0.
"""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from aip.audit import log, verify

_PROFILE = settings(
    max_examples=40,
    deadline=4000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    derandomize=True,
)


@contextmanager
def _fresh_archive():
    """Archive root limpio por ejemplo de Hypothesis. Necesario porque
    ``tmp_path`` se reutiliza entre ejemplos del mismo test function."""
    with tempfile.TemporaryDirectory(prefix="aip_prop_") as td:
        root = Path(td) / "archive"
        root.mkdir()
        yield root


# --------------------------------------------------------------------- strategies


# Reloj determinista que avanza 1 minuto por entrada. Coherente con
# ``AuditEntry`` (timestamp tz-aware, microsegundos = 0).
def _build_clock(start: dt.datetime) -> Any:
    counter = {"i": 0}

    def _clock() -> dt.datetime:
        ts = start + dt.timedelta(minutes=counter["i"])
        counter["i"] += 1
        return ts

    return _clock


# Acción no-bootstrap (V1: solo INGEST_EVIDENCE en la práctica).
_action_strategy = st.just(log.ActionKind.INGEST_EVIDENCE)

_actor_strategy = (
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="@.-_",
        ),
        min_size=1,
        max_size=20,
    )
    .map(lambda s: "@" + s.lstrip("@") if not s.startswith("@") else s)
    .filter(lambda s: len(s) >= 2)
)

_hash_strategy = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)

_target_strategy = _hash_strategy.map(lambda h: f"aip:evidence/sha256:{h}")

_param_value_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    max_size=30,
)
_parameters_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_",
        ),
        min_size=1,
        max_size=20,
    ),
    values=_param_value_strategy,
    max_size=4,
)

# Lista de tuplas (action, target, actor, parameters) que serán ingest_evidence.
_chain_inputs_strategy = st.lists(
    st.tuples(_action_strategy, _target_strategy, _actor_strategy, _parameters_strategy),
    min_size=0,
    max_size=5,
)


# --------------------------------------------------------------------- helpers


def _build_chain(
    root: Path,
    inputs: list[tuple[Any, str, str, dict[str, str]]],
) -> list[log.AuditEntry]:
    """Bootstrap + N append_entry sobre un archive limpio, devuelve entradas."""
    clock = _build_clock(dt.datetime(2026, 6, 4, 0, 0, 0, tzinfo=dt.UTC))
    boot = log.bootstrap(root, actor="@bootstrap", clock=clock, schema_version="0.1.0")
    assert boot is not None
    entries: list[log.AuditEntry] = [boot]
    for action, target, actor, params in inputs:
        entry = log.append_entry(
            root,
            action=action,
            target=target,
            actor=actor,
            parameters=params,
            schema_version="0.1.0",
            clock=clock,
        )
        entries.append(entry)
    return entries


def _read_jsonl(root: Path) -> list[dict[str, Any]]:
    """Lee el audit.log usando ``\\n`` como único separador.

    Importante: NO usamos ``str.splitlines()`` porque divide también en otros
    code points (U+0085 NEXT LINE, U+2028, U+2029) que pueden aparecer dentro
    de valores ``parameters`` no-ASCII. La producción (``iter_entries`` en
    ``aip.audit.log``) itera el fichero con ``for line in fh``, que en modo
    texto solo divide en ``\\n``/``\\r\\n``/``\\r``, así que no es vulnerable
    al mismo edge case. Este helper de test debe imitar ese comportamiento.
    """
    path = root / "audit.log"
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()
    ]


def _write_jsonl(root: Path, entries: list[dict[str, Any]]) -> None:
    path = root / "audit.log"
    path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------- properties


@given(inputs=_chain_inputs_strategy)
@_PROFILE
def test_any_valid_chain_verifies_ok(inputs: list[tuple[Any, str, str, dict[str, str]]]) -> None:
    """Toda cadena construida por la API verifica OK. (Invariante 1)"""
    with _fresh_archive() as root:
        entries = _build_chain(root, inputs)
        result = verify.verify_chain(root)
        assert result.ok is True, result.first_failure_reason
        assert result.total_entries == len(entries)


@given(inputs=_chain_inputs_strategy)
@_PROFILE
def test_prev_hash_chains_correctly(inputs: list[tuple[Any, str, str, dict[str, str]]]) -> None:
    """``entry.prev_hash == entries[i-1].entry_hash`` para todo i ≥ 1. (Invariante 2)"""
    with _fresh_archive() as root:
        entries = _build_chain(root, inputs)
        assert entries[0].prev_hash == log.ZERO_HASH
        for i in range(1, len(entries)):
            assert entries[i].prev_hash == entries[i - 1].entry_hash
            assert entries[i].seq == entries[i - 1].seq + 1


@given(
    inputs=_chain_inputs_strategy.filter(lambda lst: len(lst) >= 1),
    new_actor=_actor_strategy,
)
@_PROFILE
def test_actor_mutation_breaks_chain(
    inputs: list[tuple[Any, str, str, dict[str, str]]],
    new_actor: str,
) -> None:
    """Cambiar ``actor`` sin recomputar ``entry_hash`` ⇒ entry_hash mismatch.

    (Invariante 3: tampering de payload se detecta.)
    """
    with _fresh_archive() as root:
        _build_chain(root, inputs)
        raw = _read_jsonl(root)
        # Mutamos siempre la última entrada (no es bootstrap).
        if raw[-1]["actor"] == new_actor:
            return  # no es realmente una mutación
        raw[-1]["actor"] = new_actor
        _write_jsonl(root, raw)
        result = verify.verify_chain(root)
        assert result.ok is False
        assert "entry_hash mismatch" in (result.first_failure_reason or "")


@given(
    inputs=_chain_inputs_strategy.filter(lambda lst: len(lst) >= 1),
    bogus_hash=_hash_strategy,
)
@_PROFILE
def test_entry_hash_mutation_breaks_chain(
    inputs: list[tuple[Any, str, str, dict[str, str]]],
    bogus_hash: str,
) -> None:
    """Cambiar ``entry_hash`` directamente ⇒ verificación falla.

    Cubre el caso donde el atacante intenta sustituir un hash por otro hash
    válido (mismo formato) sin tocar el payload.
    (Invariante 4.)
    """
    with _fresh_archive() as root:
        _build_chain(root, inputs)
        raw = _read_jsonl(root)
        last_idx = len(raw) - 1
        if raw[last_idx]["entry_hash"] == bogus_hash:
            return
        raw[last_idx]["entry_hash"] = bogus_hash
        _write_jsonl(root, raw)
        result = verify.verify_chain(root)
        assert result.ok is False


@given(
    inputs=_chain_inputs_strategy.filter(lambda lst: len(lst) >= 2),
)
@_PROFILE
def test_deleted_entry_breaks_chain(
    inputs: list[tuple[Any, str, str, dict[str, str]]],
) -> None:
    """Borrar una entrada intermedia ⇒ ``seq mismatch`` o ``prev_hash mismatch``.

    Una entrada faltante rompe la cadena: la siguiente entrada tiene ``seq``
    que ya no es consecutivo Y su ``prev_hash`` referencia un hash que ya
    no es de la entrada anterior en disco.
    """
    with _fresh_archive() as root:
        _build_chain(root, inputs)
        raw = _read_jsonl(root)
        # Borramos la entrada en seq=1 (no el bootstrap).
        del raw[1]
        _write_jsonl(root, raw)
        result = verify.verify_chain(root)
        assert result.ok is False
        reason = result.first_failure_reason or ""
        assert "seq mismatch" in reason or "prev_hash mismatch" in reason


@pytest.mark.parametrize("field", ["actor", "target", "schema_version"])
def test_any_payload_field_mutation_detected(field: str, tmp_path: Path) -> None:
    """Smoke determinista: mutar cualquier campo de payload rompe la cadena.

    Complementa al property test sobre ``actor`` cubriendo más campos sin
    pagar el coste de generación aleatoria por campo.
    """
    root = tmp_path / "archive"
    root.mkdir()
    inputs: list[tuple[Any, str, str, dict[str, str]]] = [
        (log.ActionKind.INGEST_EVIDENCE, "aip:evidence/sha256:" + "a" * 64, "@x", {}),
        (log.ActionKind.INGEST_EVIDENCE, "aip:evidence/sha256:" + "b" * 64, "@y", {}),
    ]
    _build_chain(root, inputs)
    raw = _read_jsonl(root)
    original = raw[-1][field]
    raw[-1][field] = "TAMPERED" if isinstance(original, str) else original + "_x"
    _write_jsonl(root, raw)
    result = verify.verify_chain(root)
    assert result.ok is False
