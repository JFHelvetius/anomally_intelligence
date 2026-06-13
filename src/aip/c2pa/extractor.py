"""C2PA JUMBF extraction via ``c2pa-python`` (ADR-0048).

Reads JPEG/PNG/MP4/etc. that carry an embedded C2PA manifest store and
transforms the native shape into the AIP shape consumed by
``aip.c2pa.parse_manifest_json``.

Key invariants:

- ``c2pa-python`` is used **only as a parser**. AIP never accepts its
  internal verification verdict as authoritative — the X.509 signature
  re-verification (ADR-0047) is the only authoritative path.
- The dependency is **optional**. Importing this module without the
  ``c2pa`` extra installed succeeds; only ``extract_from_media()``
  raises ``AIPError`` with the install hint when actually called.
- The transformation does NOT extract raw cert chain bytes (the
  ``c2pa-python`` 0.34 API doesn't expose them reliably). When the
  caller needs ADR-0047 in-process X.509 verification, they must
  supply ``cert_chain_pem`` via a separate path. Documented limitation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from aip.errors import AIPError

_INSTALL_HINT = (
    "c2pa extraction requires the optional 'c2pa' dependency. "
    "Install with: pip install 'aip[c2pa]'"
)

# ``c2pa-python`` infers the format from the file extension via MIME types.
# We map a small set explicitly to fail loudly on unknown extensions
# rather than letting the binding return cryptic errors.
_EXT_TO_FORMAT: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
    ".heic": "image/heic",
    ".avif": "image/avif",
    ".dng":  "image/dng",
    ".mp4":  "video/mp4",
    ".m4a":  "audio/mp4",
    ".mov":  "video/quicktime",
    ".pdf":  "application/pdf",
}


def extract_from_media(media_path: Path) -> dict[str, Any]:
    """Extract the C2PA manifest chain from a media file.

    Returns a dict in the AIP shape (compatible with
    :func:`aip.c2pa.parse_manifest_json`). The returned ``manifests`` list
    is ordered with the root manifest first.

    Raises ``AIPError`` if:

    - The ``c2pa-python`` extra is not installed.
    - The file has no C2PA manifest store.
    - The file format is not recognised by the binding.
    """
    try:
        import c2pa  # noqa: PLC0415 — optional dep, deliberate lazy import
    except ImportError as exc:
        raise AIPError(_INSTALL_HINT) from exc

    if not media_path.is_file():
        raise AIPError(f"media file not found: {media_path}")

    fmt = _EXT_TO_FORMAT.get(media_path.suffix.lower())
    if fmt is None:
        raise AIPError(
            f"unsupported media extension {media_path.suffix!r} for C2PA "
            "extraction. Pass a JPEG/PNG/MP4/etc. file produced by a "
            "C2PA-compliant device or editor."
        )

    raw_json = _read_manifest_store_json(c2pa, media_path, fmt)
    if not raw_json or raw_json.strip() in ("", "{}"):
        raise AIPError(
            f"file {media_path.name!r} contains no C2PA manifest store. "
            "Use a device/editor that produces C2PA Content Credentials."
        )

    try:
        store = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AIPError(f"c2pa-python returned non-JSON output: {exc}") from exc
    if not isinstance(store, dict):
        raise AIPError("c2pa-python JSON output is not an object at the root.")

    return _transform_c2pa_to_aip(store)


# --------------------------------------------------------------- internals


def _read_manifest_store_json(c2pa_mod: Any, media_path: Path, fmt: str) -> str:
    """Open the file via c2pa.Reader and return the JSON string.

    Wraps the binding's errors so callers see ``AIPError`` regardless of
    which underlying exception fires.
    """
    try:
        with media_path.open("rb") as fh, c2pa_mod.Reader(fmt, fh) as reader:
            return reader.json()
    except (OSError, getattr(c2pa_mod, "C2paError", Exception)) as exc:
        raise AIPError(f"failed to read C2PA manifest from {media_path}: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        # The binding raises private exception types in some error paths.
        # We treat any non-IO exception as parse failure to keep the CLI
        # contract honest.
        raise AIPError(f"c2pa-python failed parsing {media_path}: {exc}") from exc


def _transform_c2pa_to_aip(store: dict[str, Any]) -> dict[str, Any]:
    """Transform the C2PA manifest store JSON into the AIP shape.

    The C2PA store is a dict ``{label: manifest}`` with an
    ``active_manifest`` pointer. AIP uses a list ordered root→leaf with
    each manifest carrying its ``parent_manifest_label`` explicitly.
    """
    raw_manifests = store.get("manifests") or {}
    if not isinstance(raw_manifests, dict) or not raw_manifests:
        raise AIPError("C2PA store has no manifests.")

    active_label = store.get("active_manifest")
    if not isinstance(active_label, str) or active_label not in raw_manifests:
        # Fall back to the first declared manifest if active is absent.
        active_label = next(iter(raw_manifests.keys()))

    # validation_status applies to the manifest store as a whole; we use
    # it to derive the operator-supplied chain_verified per manifest.
    # If the store reports any non-success status code, mark every
    # manifest's chain_verified as False with the explanation.
    failure_msg = _summarise_validation_failures(store.get("validation_status"))
    overall_ok = failure_msg is None

    # Walk the chain leaf→root via ingredients[].active_manifest.
    chain_labels = _order_chain_root_to_leaf(raw_manifests, active_label)

    aip_manifests: list[dict[str, Any]] = []
    for i, label in enumerate(chain_labels):
        manifest = raw_manifests[label]
        if not isinstance(manifest, dict):
            continue
        parent = chain_labels[i - 1] if i > 0 else None
        aip_manifests.append(
            _build_aip_manifest(
                label=label,
                parent_label=parent,
                manifest=manifest,
                chain_verified=overall_ok,
                failure_reason=failure_msg,
            )
        )

    return {"manifests": aip_manifests}


def _summarise_validation_failures(
    validation_status: Any,
) -> str | None:
    """Return ``None`` if all status codes are success; else a one-line summary.

    C2PA ``validation_status[]`` items have a ``code`` like
    ``"claim.signature.trusted"`` or ``"claim.signature.untrusted"``.
    """
    if not isinstance(validation_status, list):
        return None
    failures: list[str] = []
    for entry in validation_status:
        if not isinstance(entry, dict):
            continue
        code = entry.get("code")
        if not isinstance(code, str):
            continue
        # Heuristic: codes containing "untrusted" / "invalid" / "missing"
        # / "failed" indicate failure. C2PA's status codes follow this
        # convention in v2.x; if it ever changes, the heuristic widens.
        if any(
            keyword in code
            for keyword in ("untrusted", "invalid", "missing", "failed", "mismatch")
        ):
            explanation = entry.get("explanation") or ""
            failures.append(f"{code}: {explanation}" if explanation else code)
    return "; ".join(failures) if failures else None


def _order_chain_root_to_leaf(
    manifests: dict[str, Any], active_label: str
) -> list[str]:
    """Walk from the active (leaf) manifest backward via ingredients and
    return the labels in root→leaf order. Unknown / orphan ingredient
    pointers stop the walk gracefully."""
    seen: list[str] = []
    cursor: str | None = active_label
    while cursor is not None and cursor in manifests and cursor not in seen:
        seen.append(cursor)
        manifest = manifests[cursor]
        if not isinstance(manifest, dict):
            break
        cursor = _parent_label_of(manifest, manifests)
    seen.reverse()
    return seen


def _parent_label_of(
    manifest: dict[str, Any], manifests: dict[str, Any]
) -> str | None:
    """Find the parent manifest label by walking ``ingredients[]``.

    The C2PA spec has ingredients with ``relationship: "parentOf"``
    (current asset's edit ancestor). We look for the first such
    ingredient whose ``active_manifest`` matches a known manifest in
    the store.
    """
    ingredients = manifest.get("ingredients")
    if not isinstance(ingredients, list):
        return None
    for ing in ingredients:
        if not isinstance(ing, dict):
            continue
        if ing.get("relationship") not in (None, "parentOf"):
            continue
        candidate = ing.get("active_manifest") or ing.get("label")
        if isinstance(candidate, str) and candidate in manifests:
            return candidate
    return None


def _build_aip_manifest(
    *,
    label: str,
    parent_label: str | None,
    manifest: dict[str, Any],
    chain_verified: bool,
    failure_reason: str | None,
) -> dict[str, Any]:
    sig_raw = manifest.get("signature_info") or {}
    if not isinstance(sig_raw, dict):
        sig_raw = {}

    issuer = sig_raw.get("issuer")
    if not isinstance(issuer, str) or not issuer:
        issuer = manifest.get("claim_generator") or "unknown"

    # C2PA exposes a single ``issuer`` line — sometimes Distinguished Name.
    # Pull a CN out of it for readability; keep the full DN as the org.
    issuer_cn, issuer_org = _split_issuer(str(issuer))

    cert_serial = sig_raw.get("cert_serial_number") or sig_raw.get("serial")
    if not isinstance(cert_serial, str):
        cert_serial = "unknown"

    signing_time = sig_raw.get("time") or sig_raw.get("signing_time") or "unknown"
    # AIP wants ISO-8601 strings; C2PA already produces them.

    assertions_raw = manifest.get("assertions") or []
    assertions: list[dict[str, Any]] = []
    if isinstance(assertions_raw, list):
        for a in assertions_raw:
            if not isinstance(a, dict):
                continue
            a_label = a.get("label")
            a_data = a.get("data") or {}
            if not isinstance(a_label, str) or not a_label:
                continue
            data_dict = a_data if isinstance(a_data, dict) else {}
            assertions.append({"label": a_label, "data": data_dict})

    return {
        "label": label,
        "parent_manifest_label": parent_label,
        "signature_info": {
            "issuer_common_name": issuer_cn,
            "issuer_organization": issuer_org,
            "cert_serial": str(cert_serial),
            "not_before": str(signing_time),
            "not_after": str(signing_time),
            "chain_verified_against": "c2pa-python internal trust list",
            "chain_verified": chain_verified,
            "failure_reason": failure_reason,
            # cert_chain_pem deliberately empty: the c2pa-python 0.34 API
            # does not expose raw cert bytes reliably. ADR-0047 in-process
            # X.509 verification falls back to operator-supplied mode.
            "cert_chain_pem": [],
        },
        "assertions": assertions,
    }


_DN_KV_RE = re.compile(r"(CN|O)=([^,]+)")


def _split_issuer(dn_or_text: str) -> tuple[str, str | None]:
    """Pull CN / O out of a Distinguished Name string. If the input
    isn't a DN (which can happen with simple ``c2pa-python`` outputs),
    return the whole string as the CN and None as the organisation.
    """
    matches = dict(_DN_KV_RE.findall(dn_or_text))
    cn = matches.get("CN")
    org = matches.get("O")
    if cn is None:
        return dn_or_text, None
    return cn.strip(), org.strip() if org else None


__all__ = ["extract_from_media"]
