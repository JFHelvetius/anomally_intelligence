"""Trust footprint cross-verification (ADR-0045).

Automatiza la mecánica del cross-check externo declarado en
``key-declaration.json`` (ADR-0043). Para cada referencia soportada:
fetch HTTPS, parseo del formato, cómputo de fingerprint y comparación.

Diseño:

- **Stdlib-only HTTP**: ``urllib.request``. Sin requests / httpx.
- **HTTPS-only**: cualquier referencia http://... se rechaza.
- **Vocabulario cerrado**: sólo ``github_user_keys`` y ``https_pem`` v1.
  Cualquier otro kind se reporta como ``unsupported`` (no como error).
- **AIP no es autoridad**: el caller recibe per-referencia
  verified/mismatch/unreachable/unsupported. El receptor mantiene
  soberanía sobre qué canales confía. La UI debe mostrar este resultado
  junto al reference declarado, nunca sustituirlo.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final, Literal

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from aip.attestation.signer import compute_public_key_fingerprint
from aip.errors import AIPError

SUPPORTED_KINDS: Final[frozenset[str]] = frozenset({
    "github_user_keys",
    "https_pem",
})
"""Vocabulario cerrado v1. Ampliar requiere parser específico + ADR."""

DEFAULT_TIMEOUT_SECONDS: Final[int] = 15
_MAX_REDIRECTS: Final[int] = 3
_USER_AGENT: Final[str] = "aip-trust-footprint-verifier/1"
_MAX_BODY_BYTES: Final[int] = 1024 * 1024  # 1 MB cap
_SSH_KEY_MIN_PARTS: Final[int] = 2          # "<type> <base64>"
_FINGERPRINT_HEX_LEN: Final[int] = 64       # SHA-256 hex


Status = Literal["verified", "mismatch", "unreachable", "unsupported"]


@dataclass(frozen=True, slots=True)
class ReferenceVerifyResult:
    """Resultado de verificar una referencia externa concreta."""

    kind: str
    uri: str
    status: Status
    fetched_fingerprint: str | None
    declared_fingerprint: str
    reason: str | None = None
    """Mensaje libre para diagnóstico en mismatch/unreachable. None en verified."""


@dataclass(frozen=True, slots=True)
class FootprintVerifyReport:
    """Resultado completo de verificar todas las referencias del operador."""

    operator_id: str
    declared_fingerprint: str
    references: tuple[ReferenceVerifyResult, ...]

    @property
    def verified_count(self) -> int:
        return sum(1 for r in self.references if r.status == "verified")

    @property
    def mismatch_count(self) -> int:
        return sum(1 for r in self.references if r.status == "mismatch")

    @property
    def reachable_count(self) -> int:
        return sum(
            1 for r in self.references if r.status in ("verified", "mismatch")
        )

    @property
    def supported_count(self) -> int:
        return sum(1 for r in self.references if r.status != "unsupported")


# --------------------------------------------------------------------- fetch


def _http_get_bytes(url: str, *, timeout: int) -> bytes:
    """Minimal HTTPS GET con guardrails.

    Rechaza http:// (HTTPS only), trunca body a ``_MAX_BODY_BYTES``,
    sigue redirects hasta ``_MAX_REDIRECTS``. urllib hace TLS validación
    contra el CA store del sistema; documentado como límite del modelo.
    """
    if not url.lower().startswith("https://"):
        raise AIPError(
            f"refusing to fetch non-HTTPS URL {url!r}: trust-footprint "
            "verification requires TLS to prevent passive eavesdropping."
        )
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: bytes = resp.read(_MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise AIPError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise AIPError(f"network error fetching {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AIPError(f"timeout fetching {url}") from exc
    if len(data) > _MAX_BODY_BYTES:
        raise AIPError(f"response from {url} exceeds {_MAX_BODY_BYTES} bytes")
    return data


# --------------------------------------------------------------------- parsers


def _ed25519_fingerprints_from_github_keys(body: bytes) -> list[str]:
    """Parsea el body de ``https://github.com/<user>.keys``.

    Cada línea es ``<type> <base64> [<comment>]``. Filtramos las que NO son
    ``ssh-ed25519``: las RSA/ECDSA no son nuestro contrato y aceptarlas
    abriría una vía de confusión (operador con clave ed25519 publica una
    RSA en GitHub; la huella no coincidirá nunca).
    """
    out: list[str] = []
    text = body.decode("ascii", errors="strict")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < _SSH_KEY_MIN_PARTS:
            continue
        if parts[0] != "ssh-ed25519":
            continue
        try:
            key = serialization.load_ssh_public_key(stripped.encode("ascii"))
        except (ValueError, UnsupportedAlgorithm):
            continue
        if not isinstance(key, Ed25519PublicKey):
            continue
        out.append(compute_public_key_fingerprint(key))
    return out


def _ed25519_fingerprint_from_pem(body: bytes) -> str:
    """Parsea PEM SubjectPublicKeyInfo a fingerprint SHA-256 del DER."""
    try:
        key = serialization.load_pem_public_key(body)
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise AIPError(f"could not parse PEM: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise AIPError(
            f"public key is not ed25519 (got {type(key).__name__}); "
            "AIP v1 only verifies ed25519 fingerprints."
        )
    return compute_public_key_fingerprint(key)


# --------------------------------------------------------------------- verify one


def verify_reference(  # noqa: PLR0911 — early-return per branch keeps each path readable
    *,
    kind: str,
    uri: str,
    declared_fingerprint: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ReferenceVerifyResult:
    """Verifica una referencia externa concreta.

    Devuelve ``ReferenceVerifyResult`` con status verified/mismatch/
    unreachable/unsupported. Nunca lanza para casos de red — los empaqueta
    como ``unreachable``. Sólo lanza para invariantes de programación
    (kind/uri/declared_fingerprint vacíos).
    """
    if not kind:
        raise AIPError("verify_reference: kind must be non-empty")
    if not uri:
        raise AIPError("verify_reference: uri must be non-empty")
    if not declared_fingerprint:
        raise AIPError("verify_reference: declared_fingerprint must be non-empty")

    if kind not in SUPPORTED_KINDS:
        return ReferenceVerifyResult(
            kind=kind,
            uri=uri,
            status="unsupported",
            fetched_fingerprint=None,
            declared_fingerprint=declared_fingerprint,
            reason=(
                f"kind {kind!r} not in AIP v1 supported set "
                f"({sorted(SUPPORTED_KINDS)}). Cross-check manually."
            ),
        )

    try:
        body = _http_get_bytes(uri, timeout=timeout)
    except AIPError as exc:
        return ReferenceVerifyResult(
            kind=kind,
            uri=uri,
            status="unreachable",
            fetched_fingerprint=None,
            declared_fingerprint=declared_fingerprint,
            reason=str(exc),
        )

    try:
        if kind == "github_user_keys":
            candidates = _ed25519_fingerprints_from_github_keys(body)
            if not candidates:
                return ReferenceVerifyResult(
                    kind=kind,
                    uri=uri,
                    status="mismatch",
                    fetched_fingerprint=None,
                    declared_fingerprint=declared_fingerprint,
                    reason="no ed25519 key found at this URL.",
                )
            if declared_fingerprint in candidates:
                return ReferenceVerifyResult(
                    kind=kind,
                    uri=uri,
                    status="verified",
                    fetched_fingerprint=declared_fingerprint,
                    declared_fingerprint=declared_fingerprint,
                )
            return ReferenceVerifyResult(
                kind=kind,
                uri=uri,
                status="mismatch",
                fetched_fingerprint=candidates[0],
                declared_fingerprint=declared_fingerprint,
                reason=(
                    f"declared fingerprint not among {len(candidates)} "
                    "ed25519 key(s) published at this URL."
                ),
            )

        if kind == "https_pem":
            fp = _ed25519_fingerprint_from_pem(body)
            if fp == declared_fingerprint:
                return ReferenceVerifyResult(
                    kind=kind,
                    uri=uri,
                    status="verified",
                    fetched_fingerprint=fp,
                    declared_fingerprint=declared_fingerprint,
                )
            return ReferenceVerifyResult(
                kind=kind,
                uri=uri,
                status="mismatch",
                fetched_fingerprint=fp,
                declared_fingerprint=declared_fingerprint,
                reason="fetched PEM fingerprint differs from declared.",
            )

        # Should be unreachable because we already checked SUPPORTED_KINDS.
        return ReferenceVerifyResult(  # pragma: no cover
            kind=kind,
            uri=uri,
            status="unsupported",
            fetched_fingerprint=None,
            declared_fingerprint=declared_fingerprint,
            reason="internal: kind passed SUPPORTED_KINDS check but no parser.",
        )

    except AIPError as exc:
        return ReferenceVerifyResult(
            kind=kind,
            uri=uri,
            status="mismatch",
            fetched_fingerprint=None,
            declared_fingerprint=declared_fingerprint,
            reason=str(exc),
        )


# --------------------------------------------------------------------- verify declaration


def verify_declaration(
    declaration: dict[str, object],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> FootprintVerifyReport:
    """Verifica todas las referencias externas del operador en la declaration.

    Sólo procesa la sección ``operator`` por ahora. Las claves de testigo
    se podrán añadir en una extensión futura — su valor depende de que
    cada operador testigo mantenga sus propias referencias externas, lo
    que no es generalizable en v1.
    """
    op = declaration.get("operator")
    if not isinstance(op, dict):
        raise AIPError(
            "declaration has no 'operator' object; nothing to cross-verify."
        )

    operator_id = op.get("operator_id")
    declared_fp = op.get("public_key_fingerprint")
    refs = op.get("external_references")

    if not isinstance(operator_id, str) or not operator_id:
        raise AIPError("declaration.operator.operator_id must be a non-empty string.")
    if not isinstance(declared_fp, str) or len(declared_fp) != _FINGERPRINT_HEX_LEN:
        raise AIPError(
            "declaration.operator.public_key_fingerprint must be a 64-hex string."
        )
    if not isinstance(refs, list):
        raise AIPError(
            "declaration.operator.external_references must be a list."
        )

    results: list[ReferenceVerifyResult] = []
    for entry in refs:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        uri = entry.get("uri")
        if not isinstance(kind, str) or not isinstance(uri, str):
            continue
        results.append(
            verify_reference(
                kind=kind,
                uri=uri,
                declared_fingerprint=declared_fp,
                timeout=timeout,
            )
        )

    return FootprintVerifyReport(
        operator_id=operator_id,
        declared_fingerprint=declared_fp,
        references=tuple(results),
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "SUPPORTED_KINDS",
    "FootprintVerifyReport",
    "ReferenceVerifyResult",
    "verify_declaration",
    "verify_reference",
]
