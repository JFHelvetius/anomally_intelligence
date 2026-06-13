"""C2PA verifier (ADR-0046).

Parses a pre-extracted C2PA manifest JSON (operator-supplied via
``c2patool extract`` or equivalent) and verifies:

1. Each manifest's ``c2pa.hash.data`` assertion binds it to the declared
   evidence SHA-256.
2. The chain of ``parent_manifest_label`` references is contiguous —
   every parent referenced exists in the supplied chain.
3. Signature verdicts per manifest. In v1 the operator pre-validates
   X.509 chains externally and reports the verdict as a boolean inside
   the JSON; AIP does not re-implement X.509 verification yet — that is
   ADR-0047 (deferred). This keeps v1 honest: we surface what the
   operator-supplied tooling reported and bind it into a hash chain.

What v1 does NOT do (each is a separate ADR if/when needed):

- Extract JUMBF from binary media files.
- Verify X.509 certificate chains against a CRL/OCSP.
- Parse the full C2PA spec — only the structural subset above.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Final, cast

from aip.c2pa.models import (
    C2PA_REPORT_SCHEMA_VERSION,
    C2PA_REPORT_TYPE,
    C2PAAssertion,
    C2PAManifest,
    C2PAReport,
    C2PASignatureInfo,
)
from aip.core.hashing import JsonValue, jcs_canonicalize, sha256_hex
from aip.errors import AIPError

C2PA_ATTESTATIONS_DIRNAME: Final[str] = "c2pa-attestations"
DEFAULT_TRUST_LIST_NAME: Final[str] = "c2pa-default-trust-list-v1"
_HASH_DATA_LABEL: Final[str] = "c2pa.hash.data"
_SHA256_HEX_LEN: Final[int] = 64


# --------------------------------------------------------------------- parse


def parse_manifest_json(payload: dict[str, Any]) -> tuple[C2PAManifest, ...]:
    """Parse the operator-supplied manifest chain JSON.

    Expected shape (operator-supplied via c2patool / c2pa-python):

        {
          "manifests": [
            {
              "label": "<unique label>",
              "parent_manifest_label": "<previous label or null>",
              "signature_info": {
                "issuer_common_name": "...",
                "issuer_organization": "...",
                "cert_serial": "...",
                "not_before": "ISO-8601 UTC",
                "not_after": "ISO-8601 UTC",
                "chain_verified": true,
                "failure_reason": null,
                "chain_verified_against": "<trust list name>"
              },
              "assertions": [
                {"label": "c2pa.hash.data", "data": {"sha256": "<hex>"}},
                ...
              ]
            },
            ...
          ]
        }

    Raises ``AIPError`` on missing keys, bad types, or empty chain.
    """
    raw_manifests = payload.get("manifests")
    if not isinstance(raw_manifests, list) or not raw_manifests:
        raise AIPError(
            "C2PA manifest JSON must contain a non-empty 'manifests' list."
        )

    out: list[C2PAManifest] = []
    for i, raw in enumerate(raw_manifests):
        if not isinstance(raw, dict):
            raise AIPError(f"manifest[{i}] is not a JSON object.")
        out.append(_parse_one_manifest(raw, index=i))
    return tuple(out)


def _parse_one_manifest(raw: dict[str, Any], *, index: int) -> C2PAManifest:
    label = raw.get("label")
    if not isinstance(label, str) or not label:
        raise AIPError(f"manifest[{index}] missing non-empty 'label'.")

    parent = raw.get("parent_manifest_label")
    if parent is not None and not isinstance(parent, str):
        raise AIPError(
            f"manifest[{index}].parent_manifest_label must be string or null."
        )

    sig_raw = raw.get("signature_info")
    if not isinstance(sig_raw, dict):
        raise AIPError(
            f"manifest[{index}] missing 'signature_info' object."
        )
    sig = _parse_signature(sig_raw, index=index)

    assertions_raw = raw.get("assertions")
    if not isinstance(assertions_raw, list):
        raise AIPError(f"manifest[{index}].assertions must be a list.")
    assertions: list[C2PAAssertion] = []
    for j, a in enumerate(assertions_raw):
        if not isinstance(a, dict):
            raise AIPError(f"manifest[{index}].assertions[{j}] must be an object.")
        a_label = a.get("label")
        if not isinstance(a_label, str) or not a_label:
            raise AIPError(
                f"manifest[{index}].assertions[{j}] missing 'label'."
            )
        a_data = a.get("data") or {}
        if not isinstance(a_data, dict):
            raise AIPError(
                f"manifest[{index}].assertions[{j}].data must be an object."
            )
        assertions.append(C2PAAssertion(label=a_label, data=a_data))

    return C2PAManifest(
        label=label,
        parent_manifest_label=parent,
        signature_info=sig,
        assertions=tuple(assertions),
    )


def _parse_signature(raw: dict[str, Any], *, index: int) -> C2PASignatureInfo:
    required_str_keys = (
        "issuer_common_name",
        "cert_serial",
        "not_before",
        "not_after",
        "chain_verified_against",
    )
    for k in required_str_keys:
        if not isinstance(raw.get(k), str) or not raw[k]:
            raise AIPError(
                f"manifest[{index}].signature_info missing string '{k}'."
            )
    chain_verified = raw.get("chain_verified")
    if not isinstance(chain_verified, bool):
        raise AIPError(
            f"manifest[{index}].signature_info.chain_verified must be a boolean."
        )
    organization = raw.get("issuer_organization")
    if organization is not None and not isinstance(organization, str):
        raise AIPError(
            f"manifest[{index}].signature_info.issuer_organization must be "
            "string or null."
        )
    failure_reason = raw.get("failure_reason")
    if failure_reason is not None and not isinstance(failure_reason, str):
        raise AIPError(
            f"manifest[{index}].signature_info.failure_reason must be string or null."
        )

    # ADR-0047: optional cert_chain_pem field. When present and an
    # operator-supplied trust list is later passed to verify_manifest_chain,
    # AIP recomputes chain_verified in-process and overrides the operator
    # value. Absent → AIP stays in operator-supplied mode.
    cert_chain_raw = raw.get("cert_chain_pem", [])
    if not isinstance(cert_chain_raw, list):
        raise AIPError(
            f"manifest[{index}].signature_info.cert_chain_pem must be a list of PEM strings."
        )
    cert_chain: list[str] = []
    for j, pem in enumerate(cert_chain_raw):
        if not isinstance(pem, str):
            raise AIPError(
                f"manifest[{index}].signature_info.cert_chain_pem[{j}] must be string."
            )
        cert_chain.append(pem)

    return C2PASignatureInfo(
        issuer_common_name=raw["issuer_common_name"],
        issuer_organization=organization,
        cert_serial=raw["cert_serial"],
        not_before=raw["not_before"],
        not_after=raw["not_after"],
        chain_verified_against=raw["chain_verified_against"],
        chain_verified=chain_verified,
        failure_reason=failure_reason,
        cert_chain_pem=tuple(cert_chain),
        verification_mode="operator-supplied",
    )


# --------------------------------------------------------------------- verify


def recompute_signatures_with_trust_list(
    manifests: tuple[C2PAManifest, ...],
    *,
    trust_list_pem: str,
    trust_list_name: str,
    now: dt.datetime | None = None,
) -> tuple[C2PAManifest, ...]:
    """ADR-0047: re-verify each manifest's X.509 chain in-process.

    Returns a new tuple of manifests with ``signature_info.chain_verified``,
    ``failure_reason``, ``chain_verified_against`` and ``verification_mode``
    overwritten to reflect AIP's own computation. Manifests that supply no
    ``cert_chain_pem`` are returned unchanged — AIP keeps the operator-
    supplied verdict and flags ``verification_mode="operator-supplied"``.
    """
    # Lazy import: this module is only loaded when the trust list path is
    # exercised, keeping the cold path light.
    from aip.c2pa.x509_verifier import verify_x509_chain  # noqa: PLC0415

    out: list[C2PAManifest] = []
    for m in manifests:
        sig = m.signature_info
        if not sig.cert_chain_pem:
            out.append(m)
            continue
        result = verify_x509_chain(
            list(sig.cert_chain_pem),
            trust_list_pem=trust_list_pem,
            now=now,
        )
        new_sig = C2PASignatureInfo(
            issuer_common_name=sig.issuer_common_name,
            issuer_organization=sig.issuer_organization,
            cert_serial=sig.cert_serial,
            not_before=sig.not_before,
            not_after=sig.not_after,
            chain_verified_against=(
                f"{trust_list_name} (root: {result.trust_anchor_subject})"
                if result.verified and result.trust_anchor_subject
                else trust_list_name
            ),
            chain_verified=result.verified,
            failure_reason=result.reason,
            cert_chain_pem=sig.cert_chain_pem,
            verification_mode="in-process" if result.used_chain else "operator-supplied",
        )
        out.append(
            C2PAManifest(
                label=m.label,
                signature_info=new_sig,
                assertions=m.assertions,
                parent_manifest_label=m.parent_manifest_label,
            )
        )
    return tuple(out)


def verify_manifest_chain(
    manifests: tuple[C2PAManifest, ...],
    *,
    evidence_sha256: str,
    trust_list_name: str = DEFAULT_TRUST_LIST_NAME,
    trust_list_pem: str | None = None,
    now: dt.datetime | None = None,
) -> C2PAReport:
    """Build a ``C2PAReport`` after running every structural check.

    The result is honest about partial failures: a chain that links
    correctly but whose signatures didn't verify yields
    ``chain_verified=False`` with a specific ``failure_reason``.

    ``now`` is the clock injection point for tests; defaults to UTC.
    """
    if len(evidence_sha256) != _SHA256_HEX_LEN or any(
        c not in "0123456789abcdef" for c in evidence_sha256.lower()
    ):
        raise AIPError(
            f"evidence_sha256 must be 64 lowercase hex chars; got {evidence_sha256!r}."
        )
    if not manifests:
        raise AIPError("verify_manifest_chain: empty manifest chain.")

    # ADR-0047: if a trust list is supplied, recompute each manifest's
    # X.509 chain verdict in-process. The structural checks below then
    # run against the AIP-computed signature_info, not the operator-
    # supplied one.
    if trust_list_pem is not None:
        manifests = recompute_signatures_with_trust_list(
            manifests,
            trust_list_pem=trust_list_pem,
            trust_list_name=trust_list_name,
            now=now,
        )

    failure_reason = _first_chain_failure(manifests, evidence_sha256=evidence_sha256)

    verified_at = (now or dt.datetime.now(dt.UTC)).replace(microsecond=0)
    verified_at_iso = verified_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    report_without_hash: dict[str, JsonValue] = {
        "report_type": C2PA_REPORT_TYPE,
        "schema_version": C2PA_REPORT_SCHEMA_VERSION,
        "evidence_sha256": evidence_sha256.lower(),
        "verified_at": verified_at_iso,
        "trust_list_name": trust_list_name,
        "chain_verified": failure_reason is None,
        "failure_reason": failure_reason,
        "manifests": [_manifest_to_jsonable(m) for m in manifests],
    }
    report_hash = sha256_hex(jcs_canonicalize(cast(JsonValue, report_without_hash)))

    return C2PAReport(
        report_type=C2PA_REPORT_TYPE,
        schema_version=C2PA_REPORT_SCHEMA_VERSION,
        evidence_sha256=evidence_sha256.lower(),
        verified_at=verified_at_iso,
        trust_list_name=trust_list_name,
        chain_verified=failure_reason is None,
        failure_reason=failure_reason,
        manifests=manifests,
        report_hash=report_hash,
    )


def _first_chain_failure(  # noqa: PLR0911 — each branch reports a specific failure
    manifests: tuple[C2PAManifest, ...], *, evidence_sha256: str
) -> str | None:
    """Run structural checks. Returns None if everything passes."""
    # 1. Exactly one root (parent=None). C2PA allows multiple ingredient
    #    chains, but v1 only handles the linear case.
    roots = [m for m in manifests if m.parent_manifest_label is None]
    if len(roots) != 1:
        return (
            f"expected exactly one root manifest (parent=null); "
            f"found {len(roots)}."
        )

    # 2. Every parent reference must exist.
    labels = {m.label for m in manifests}
    if len(labels) != len(manifests):
        return "duplicate manifest labels — chain identity not unique."
    for m in manifests:
        if m.parent_manifest_label is not None and m.parent_manifest_label not in labels:
            return (
                f"manifest {m.label!r} references unknown parent "
                f"{m.parent_manifest_label!r}."
            )

    # 3. Each manifest's signature must report verified.
    for m in manifests:
        if not m.signature_info.chain_verified:
            return (
                f"manifest {m.label!r} signature did not verify against "
                f"{m.signature_info.chain_verified_against!r}: "
                f"{m.signature_info.failure_reason or 'no reason given'}."
            )

    # 4. The final (leaf) manifest's c2pa.hash.data must match the
    #    declared evidence SHA-256. Leaf = the only manifest no other
    #    manifest claims as parent.
    parent_of = {m.parent_manifest_label for m in manifests if m.parent_manifest_label}
    leaves = [m for m in manifests if m.label not in parent_of]
    if len(leaves) != 1:
        return (
            f"expected exactly one leaf manifest (no children); "
            f"found {len(leaves)}."
        )
    leaf = leaves[0]
    hash_assertion = _find_assertion(leaf, _HASH_DATA_LABEL)
    if hash_assertion is None:
        return (
            f"leaf manifest {leaf.label!r} has no c2pa.hash.data assertion — "
            "cannot bind to evidence."
        )
    declared = hash_assertion.data.get("sha256")
    if not isinstance(declared, str) or declared.lower() != evidence_sha256.lower():
        return (
            f"leaf manifest c2pa.hash.data ({declared!r}) does not match "
            f"declared evidence_sha256 ({evidence_sha256!r})."
        )
    return None


def _find_assertion(m: C2PAManifest, label: str) -> C2PAAssertion | None:
    for a in m.assertions:
        if a.label == label:
            return a
    return None


def _manifest_to_jsonable(m: C2PAManifest) -> JsonValue:
    return cast(JsonValue, {
        "label": m.label,
        "parent_manifest_label": m.parent_manifest_label,
        "signature_info": {
            "issuer_common_name": m.signature_info.issuer_common_name,
            "issuer_organization": m.signature_info.issuer_organization,
            "cert_serial": m.signature_info.cert_serial,
            "not_before": m.signature_info.not_before,
            "not_after": m.signature_info.not_after,
            "chain_verified_against": m.signature_info.chain_verified_against,
            "chain_verified": m.signature_info.chain_verified,
            "failure_reason": m.signature_info.failure_reason,
            "verification_mode": m.signature_info.verification_mode,
            # cert_chain_pem is deliberately NOT included in the persisted
            # JCS hash — its bytes are large and the verdict is already
            # captured in chain_verified + failure_reason. The raw chain
            # can be re-supplied on the next verify run if needed.
        },
        "assertions": [
            {"label": a.label, "data": dict(a.data)} for a in m.assertions
        ],
    })


# --------------------------------------------------------------------- persist


def persist_report(archive_root: Path, report: C2PAReport) -> Path:
    """Write the report to ``<archive>/c2pa-attestations/<evidence>.json``.

    Idempotent: overwriting an existing report is allowed because each
    run is fully derived from inputs. The on-disk JSON is sorted+indented
    for diffability.
    """
    target_dir = archive_root / C2PA_ATTESTATIONS_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{report.evidence_sha256}.json"
    target.write_text(
        json.dumps(
            _report_to_jsonable(report),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def _report_to_jsonable(report: C2PAReport) -> dict[str, JsonValue]:
    return {
        "report_type": report.report_type,
        "schema_version": report.schema_version,
        "evidence_sha256": report.evidence_sha256,
        "verified_at": report.verified_at,
        "trust_list_name": report.trust_list_name,
        "chain_verified": report.chain_verified,
        "failure_reason": report.failure_reason,
        "manifests": [_manifest_to_jsonable(m) for m in report.manifests],
        "report_hash": report.report_hash,
    }


__all__ = [
    "C2PA_ATTESTATIONS_DIRNAME",
    "DEFAULT_TRUST_LIST_NAME",
    "parse_manifest_json",
    "persist_report",
    "verify_manifest_chain",
]
