"""Tests del firmador, verificador, persistencia y guardrails (ADR-0041)."""

from __future__ import annotations

import ast
import dataclasses
import datetime as dt
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from aip.attestation import (
    AttestationNotFoundError,
    OperatorAttestation,
    compute_attestation_hash,
    compute_public_key_fingerprint,
    decode_attestation,
    encode_attestation,
    extract_artifact_self_hash,
    generate_keypair,
    load_attestation,
    load_private_key,
    load_public_key,
    persist_attestation,
    serialize_private_key_pem,
    serialize_public_key_pem,
    sign_artifact,
    verify_attestation,
)
from aip.attestation.models import (
    ALLOWED_ARTIFACT_KINDS,
    SIGNATURE_ALGORITHM,
)
from aip.attestation.signer import ATTESTATIONS_DIRNAME
from aip.storage.layout import V1_TABLES

_SIGNED_AT = dt.datetime(2026, 6, 7, 12, 0, 0, tzinfo=dt.UTC)
_HASH_64 = "a" * 64


def _write_workspace_artifact(path: Path, workspace_hash: str = _HASH_64) -> Path:
    data = {
        "workspace_id": "w-1",
        "workspace_hash": workspace_hash,
        "references": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------- keys


def test_generate_keypair_returns_ed25519_pair() -> None:
    priv, pub = generate_keypair()
    assert isinstance(priv, Ed25519PrivateKey)
    assert priv.public_key().public_bytes_raw() == pub.public_bytes_raw()


def test_keypair_pem_roundtrip(tmp_path: Path) -> None:
    priv, pub = generate_keypair()
    priv_path = tmp_path / "priv.pem"
    pub_path = tmp_path / "pub.pem"
    priv_path.write_bytes(serialize_private_key_pem(priv))
    pub_path.write_bytes(serialize_public_key_pem(pub))
    priv_loaded = load_private_key(priv_path)
    pub_loaded = load_public_key(pub_path)
    assert priv_loaded.public_key().public_bytes_raw() == priv.public_key().public_bytes_raw()
    assert pub_loaded.public_bytes_raw() == pub.public_bytes_raw()


def test_public_key_fingerprint_is_stable() -> None:
    priv, pub = generate_keypair()
    fp1 = compute_public_key_fingerprint(pub)
    fp2 = compute_public_key_fingerprint(priv.public_key())
    assert fp1 == fp2
    assert len(fp1) == 64


def test_load_private_key_rejects_non_ed25519(tmp_path: Path) -> None:
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    p = tmp_path / "rsa.pem"
    p.write_bytes(pem)
    with pytest.raises(ValueError, match="not ed25519"):
        load_private_key(p)


# ---------------------------------------------------------------- sign / verify


def test_sign_and_verify_full_cycle(tmp_path: Path) -> None:
    priv, pub = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    assert verify_attestation(att, public_key=pub) is True
    assert att.signed_at == "2026-06-07T12:00:00Z"
    assert att.signature_algorithm == SIGNATURE_ALGORITHM
    assert att.public_key_fingerprint == compute_public_key_fingerprint(pub)
    assert att.artifact_hash == _HASH_64
    assert len(att.signature) == 128


def test_signed_payload_is_deterministic(tmp_path: Path) -> None:
    """G1: mismo artefacto + misma clave + mismo signed_at ⇒ misma firma."""
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    a1 = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    a2 = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    assert a1.signature == a2.signature
    assert a1.attestation_hash == a2.attestation_hash


def test_verify_structural_without_public_key(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    # Sin clave pública: sólo recomputa attestation_hash.
    assert verify_attestation(att) is True


def test_tampered_artifact_hash_invalidates_signature(tmp_path: Path) -> None:
    """G3: cambiar artifact_hash rompe la firma ed25519."""
    priv, pub = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    tampered = dataclasses.replace(
        att,
        artifact_hash="b" * 64,
        attestation_hash=compute_attestation_hash(dataclasses.replace(att, artifact_hash="b" * 64)),
    )
    # attestation_hash recomputado pasa, pero la firma no.
    assert verify_attestation(tampered, public_key=pub) is False


def test_tampered_signature_fails_verify(tmp_path: Path) -> None:
    priv, pub = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    flipped = att.signature[:-2] + ("ff" if att.signature[-2:] != "ff" else "00")
    bad = dataclasses.replace(att, signature=flipped)
    bad = dataclasses.replace(bad, attestation_hash=compute_attestation_hash(bad))
    assert verify_attestation(bad, public_key=pub) is False


def test_wrong_public_key_fails_verify(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    _, wrong_pub = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    # fingerprint mismatch detected first.
    assert verify_attestation(att, public_key=wrong_pub) is False


def test_corrupted_attestation_hash_fails_structural(tmp_path: Path) -> None:
    priv, pub = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    corrupted = dataclasses.replace(att, attestation_hash="c" * 64)
    assert verify_attestation(corrupted) is False
    assert verify_attestation(corrupted, public_key=pub) is False


def test_sign_requires_tz_aware_signed_at(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    naive = dt.datetime(2026, 6, 7, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        sign_artifact(
            artifact_kind="workspace",
            artifact_path=artifact,
            private_key=priv,
            signer_id="@op",
            signed_at=naive,
        )


def test_sign_rejects_invalid_kind(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    with pytest.raises(ValueError, match="artifact_kind"):
        sign_artifact(
            artifact_kind="banana",  # type: ignore[arg-type]
            artifact_path=artifact,
            private_key=priv,
            signer_id="@op",
            signed_at=_SIGNED_AT,
        )


def test_signed_at_microseconds_discarded(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    when = dt.datetime(2026, 6, 7, 12, 0, 0, 999999, tzinfo=dt.UTC)
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=when,
    )
    assert att.signed_at == "2026-06-07T12:00:00Z"


# ---------------------------------------------------------------- extract self hash


def test_extract_self_hash_workspace(tmp_path: Path) -> None:
    artifact = _write_workspace_artifact(tmp_path / "ws.json", workspace_hash="d" * 64)
    assert extract_artifact_self_hash("workspace", artifact) == "d" * 64


def test_extract_self_hash_missing_field(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"workspace_id": "w"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing self-hash field"):
        extract_artifact_self_hash("workspace", p)


def test_extract_self_hash_invalid_kind(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    p.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid artifact_kind"):
        extract_artifact_self_hash("banana", p)


def test_extract_self_hash_root_not_object(tmp_path: Path) -> None:
    p = tmp_path / "arr.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        extract_artifact_self_hash("workspace", p)


# ---------------------------------------------------------------- persistence / encoding


def test_persist_and_load_roundtrip(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    archive = tmp_path / "archive"
    target = persist_attestation(
        att,
        archive_root=archive,
        attestation_id="att-1",
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    assert target.is_file()
    assert target.parent.name == "attestations"
    loaded = load_attestation(archive_root=archive, attestation_id="att-1")
    assert loaded == att


def test_load_attestation_not_found(tmp_path: Path) -> None:
    with pytest.raises(AttestationNotFoundError, match="att-missing"):
        load_attestation(archive_root=tmp_path / "archive", attestation_id="att-missing")


def test_encode_decode_roundtrip() -> None:
    att = OperatorAttestation(
        artifact_kind="workspace",
        artifact_hash="a" * 64,
        signer_id="@op",
        public_key_fingerprint="f" * 64,
        signature="0" * 128,
        signature_algorithm=SIGNATURE_ALGORITHM,
        signed_at="2026-06-07T12:00:00Z",
        attestation_hash="b" * 64,
    )
    decoded = decode_attestation(encode_attestation(att))
    assert decoded == att


def test_encoded_json_is_canonical_sorted() -> None:
    att = OperatorAttestation(
        artifact_kind="workspace",
        artifact_hash="a" * 64,
        signer_id="@op",
        public_key_fingerprint="f" * 64,
        signature="0" * 128,
        signature_algorithm=SIGNATURE_ALGORITHM,
        signed_at="2026-06-07T12:00:00Z",
        attestation_hash="b" * 64,
    )
    encoded = encode_attestation(att)
    parsed = json.loads(encoded)
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert encoded.endswith("\n")


def test_persist_extra_output(tmp_path: Path) -> None:
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    archive = tmp_path / "archive"
    extra = tmp_path / "out" / "sig.json"
    persist_attestation(
        att,
        archive_root=archive,
        attestation_id="att-1",
        extra_output=extra,
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    assert extra.is_file()
    assert decode_attestation(extra.read_text(encoding="utf-8")) == att


# ---------------------------------------------------------------- G4 / backward compat


def test_attestations_dir_is_peripheral_to_manifest() -> None:
    """G4 (estructural): ``<archive>/attestations/`` no entra en
    ``V1_TABLES`` ni en el computo del manifest. Por construcción,
    ``archive_manifest_hash`` permanece invariante ante operaciones de
    attestation."""
    assert ATTESTATIONS_DIRNAME == "attestations"
    assert ATTESTATIONS_DIRNAME not in V1_TABLES


def test_persist_attestation_creates_peripheral_dir_only(
    tmp_path: Path,
) -> None:
    """G4 (operacional, refinado por ADR-0019 §E1): persistir bajo
    ``<archive>/attestations/`` no crea ni toca ``manifest.json`` ni
    ningún directorio de ``V1_TABLES``.

    Sí escribe ``audit.log`` en la raíz del archive — la entry
    ``SIGN_ATTESTATION`` que registra el acto criptográfico. Eso es el
    cierre del ciclo "vínculo clave-artefacto + trazabilidad histórica".
    """
    priv, _ = generate_keypair()
    artifact = _write_workspace_artifact(tmp_path / "ws.json")
    att = sign_artifact(
        artifact_kind="workspace",
        artifact_path=artifact,
        private_key=priv,
        signer_id="@op",
        signed_at=_SIGNED_AT,
    )
    archive = tmp_path / "archive"
    persist_attestation(
        att,
        archive_root=archive,
        attestation_id="att-1",
        actor="@test",
        clock=lambda: dt.datetime(2026, 6, 4, tzinfo=dt.UTC),
    )
    children = {p.name for p in archive.iterdir()}
    assert children == {"attestations", "audit.log"}
    for table in V1_TABLES:
        assert not (archive / table).exists()
    assert not (archive / "manifest.json").exists()


# ---------------------------------------------------------------- G6 forbidden tokens

_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "severity",
    "criticality",
    "risk_score",
    "risk_level",
    "danger",
    "high_risk",
    "likelihood",
    "probability",
    "bayesian",
    "confidence_score",
    "confidence_percent",
    "recommend_action",
    "recommendation",
    "suggested_action",
    "automated_decision",
    "causal_inference",
    "ranking",
    "embedding",
    "clustering",
    "summary_text",
    "report_text",
    "explanation",
    "better",
    "worse",
    "important_",
    "relevant_",
    "regression",
    "improvement",
    "infer_",
    "predict_",
)


def _attestation_source_files() -> list[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "attestation"
    cli_module = repo / "src" / "aip" / "cli" / "attestation_commands.py"
    files = list(pkg.glob("*.py"))
    files.append(cli_module)
    return files


def test_no_prohibited_tokens_in_attestation_module() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _attestation_source_files():
        text = path.read_text(encoding="utf-8").lower()
        for token in _FORBIDDEN_TOKENS:
            if token in text:
                offenders.append((path.name, token))
    assert offenders == [], f"Forbidden tokens in attestation (ADR-0041 §G6): {offenders}"


# ---------------------------------------------------------------- G7 import boundary


def test_attestation_imports_only_allowed_modules() -> None:
    """G7 + S16: attestation/ sólo puede depender de core/, storage/,
    errors y de la librería ``cryptography`` (única crypto dep)."""
    here = Path(__file__).resolve()
    repo = here.parents[3]
    pkg = repo / "src" / "aip" / "attestation"
    forbidden_aip = {
        "analysis",
        "graph",
        "impact",
        "context",
        "workspace",
        "timeline",
        "snapshot",
        "diff",
        "justification",
        "integrity",
        "cli",
    }
    forbidden_external = {
        "numpy",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "openai",
        "anthropic",
        "requests",
        "urllib",
        "urllib3",
        "httpx",
    }
    offenders: list[tuple[str, str]] = []
    for module_path in pkg.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    mods.append(n.name)
            for mod in mods:
                parts = mod.split(".")
                if len(parts) >= 2 and parts[0] == "aip" and parts[1] in forbidden_aip:
                    offenders.append((module_path.name, mod))
                if parts[0] in forbidden_external:
                    offenders.append((module_path.name, mod))
    assert offenders == [], f"attestation/ imports forbidden modules: {offenders}"


def test_signer_uses_cryptography_only_for_crypto() -> None:
    """La única dependencia externa de attestation/ debe ser
    ``cryptography``. Tests pinea que ``hashlib`` (stdlib) y
    ``cryptography`` son las únicas dependencias de crypto."""
    stdlib_allowed = {
        "aip",
        "collections",  # collections.abc.Callable
        "dataclasses",
        "datetime",
        "hashlib",
        "json",
        "pathlib",
        "typing",
        "__future__",
    }
    here = Path(__file__).resolve()
    repo = here.parents[3]
    signer = repo / "src" / "aip" / "attestation" / "signer.py"
    tree = ast.parse(signer.read_text(encoding="utf-8"))
    external_crypto_libs: set[str] = set()
    for node in ast.walk(tree):
        mod: str | None = None
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
        elif isinstance(node, ast.Import):
            for n in node.names:
                if n.name.split(".")[0] not in stdlib_allowed:
                    external_crypto_libs.add(n.name.split(".")[0])
        if mod and mod.split(".")[0] not in stdlib_allowed:
            external_crypto_libs.add(mod.split(".")[0])
    assert external_crypto_libs == {"cryptography"}, (
        f"signer.py external imports must be exactly {{'cryptography'}}; got {external_crypto_libs}"
    )


# ---------------------------------------------------------------- closed taxonomy


def test_allowed_artifact_kinds_match_adr() -> None:
    expected = {
        "workspace",
        "timeline",
        "snapshot",
        "justification",
        "context_bundle",
        "manifest",
    }
    assert set(ALLOWED_ARTIFACT_KINDS) == expected
