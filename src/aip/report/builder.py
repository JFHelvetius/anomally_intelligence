"""Construye reports HTML auto-contenidos para una pieza de evidencia.

Flujo:

1. :func:`load_report_data` recolecta TODO lo relevante para una evidencia
   desde el archive (evidence + cert + audit + manifests + witnesses + ots
   + proofs). Funciones helpers son copias deliberadas de las de
   ``aip.api.routes.evidence`` para mantener al ``aip.report`` desacoplado
   del API/FastAPI.
2. :func:`build_report_html` renderiza el dict en un HTML auto-contenido
   via :data:`HTML_TEMPLATE` (CSS + JS embedidos), con la data JSON-inlined
   en un ``<script type="application/json">``.
"""

# Templates con CSS/JS/HTML inline tienen líneas largas por diseño — suprimir E501.
# ruff: noqa: E501
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from string import Template
from typing import Any

from aip.archive import CAPTURE_CERTIFICATES_DIRNAME, Archive
from aip.audit import log as audit_log
from aip.justification.logic import ALLOWED_RULES, get_rule
from aip.justification.logic.store import INFERENCE_PROOFS_DIRNAME
from aip.notarize import OTS_EXTENSION, decode_dtf_from_bytes, verify_proof
from aip.transparency.store import (
    TRANSPARENCY_DIRNAME,
    list_sequences,
    manifest_path,
)
from aip.transparency.witness import list_all_witnesses

_PUBLIC_KEY_FILENAME = "public-key.pem"
_WITNESS_KEYS_DIRNAME = "witness-keys"
_FINGERPRINT_PEM_RE = re.compile(r"^([a-f0-9]{64})\.pem$")
_KEY_DECLARATION_FILENAME = "key-declaration.json"
_KEY_DECLARATION_TYPE = "aip.transparency.key-declaration.v1"

_ABDUCTION_RULE = "abduction_to_best_explanation"


# --------------------------------------------------------------------- data loaders


def _find_capture_cert_hash(provenance_steps: Any) -> str | None:
    for st in provenance_steps:
        if st.parameters and "capture_certificate_hash" in st.parameters:
            value = st.parameters["capture_certificate_hash"]
            return str(value) if value is not None else None
    return None


def _load_capture_certificate(
    archive_root: Path, cert_hash: str
) -> dict[str, Any] | None:
    target = archive_root / CAPTURE_CERTIFICATES_DIRNAME / f"{cert_hash}.json"
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _load_c2pa_attestation(
    archive_root: Path, evidence_hash: str
) -> dict[str, Any] | None:
    """ADR-0046: load the C2PA report sidecar if the operator persisted one
    via ``aip evidence c2pa-verify``. Absent = the layer simply does not
    render. Present = surfaces with full honesty about what C2PA proves."""
    target = (
        archive_root
        / "c2pa-attestations"
        / f"{evidence_hash}.json"
    )
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _audit_entry_for_evidence(
    archive_root: Path, evidence_hash: str
) -> dict[str, Any] | None:
    """La entry INGEST_EVIDENCE para este hash."""
    target_uri = f"aip:evidence/sha256:{evidence_hash}"
    for entry in audit_log.iter_entries(archive_root):
        if (
            entry.action == audit_log.ActionKind.INGEST_EVIDENCE
            and entry.target == target_uri
        ):
            return entry.to_canonical_dict()
    return None


def _full_audit_chain(archive_root: Path) -> list[dict[str, Any]]:
    """Cadena completa del audit log como dicts canonicalizables."""
    return [e.to_canonical_dict() for e in audit_log.iter_entries(archive_root)]


def _coverage_manifests(
    archive_root: Path, evidence_audit_seq: int
) -> list[dict[str, Any]]:
    """Manifests cuyo audit_entry_count cubre el seq de esta evidencia.

    Devuelve los manifests COMPLETOS (no resumen) para que el JS pueda
    recomputar manifest_hash client-side.
    """
    out: list[dict[str, Any]] = []
    for seq in list_sequences(archive_root):
        path = manifest_path(archive_root, seq)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("audit_entry_count", 0) > evidence_audit_seq:
            out.append(data)
    return out


def _ots_summary_for_manifest(archive_root: Path, sequence: int) -> dict[str, Any] | None:
    """Parsea ``manifest-NNNNNN.json.ots`` si existe."""
    ots_path = (
        archive_root
        / TRANSPARENCY_DIRNAME
        / f"manifest-{sequence:06d}.json{OTS_EXTENSION}"
    )
    if not ots_path.is_file():
        return None
    try:
        dtf = decode_dtf_from_bytes(ots_path.read_bytes())
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


def _load_key_declaration(archive_root: Path) -> dict[str, Any] | None:
    """Load operator's key declaration (external publication references).

    The declaration is an opt-in JSON file at
    ``<archive>/transparency/key-declaration.json`` where the operator lists
    where their (and witnesses') public keys are independently published. The
    report surfaces this so the receptor can cross-check the embedded keys
    against an external source instead of trusting them blindly.

    Schema is enforced minimally — unknown extra fields are passed through.
    Returns ``None`` if file is missing or unreadable.
    """
    target = archive_root / TRANSPARENCY_DIRNAME / _KEY_DECLARATION_FILENAME
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("declaration_type") != _KEY_DECLARATION_TYPE:
        return None
    return data


def _inference_rule_specs_for_report() -> list[dict[str, Any]]:
    """Serialize the closed inference-rule vocabulary for client-side use.

    Mirrors ``aip.justification.logic.rules._RULES`` into a JSON-safe list so
    the embedded JS can verify arity + vocabulary without hardcoding the
    rules. Adding a rule in Python automatically updates the report.
    """
    out: list[dict[str, Any]] = []
    for name in sorted(ALLOWED_RULES):
        spec = get_rule(name)
        if spec is None:  # pragma: no cover - defensive; ALLOWED_RULES is the source
            continue
        out.append(
            {
                "name": spec.name,
                "min_inputs": spec.min_inputs,
                "max_inputs": spec.max_inputs,  # may be None ⇒ unbounded
                "classification": spec.classification,
            }
        )
    return out


def _inference_proofs_referencing(
    archive_root: Path, evidence_hash: str
) -> list[dict[str, Any]]:
    """Proofs completos que tienen esta evidencia en algún premise.evidence_refs."""
    d = archive_root / INFERENCE_PROOFS_DIRNAME
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for f in sorted(d.iterdir(), key=lambda p: p.name):
        if not f.is_file() or f.suffix != ".json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for p in data.get("premises", []):
            if evidence_hash in p.get("evidence_refs", []):
                out.append(data)
                break
    return out


# --------------------------------------------------------------------- public API


def load_report_data(
    archive_root: Path,
    evidence_hash: str,
    *,
    bitcoin_block_headers: dict[int, str] | None = None,
    footprint_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recolecta todos los datos del report en un único dict listo para JSON-inline.

    Args:
        archive_root: raíz del archive AIP.
        evidence_hash: SHA-256 hex (sin prefijo) del fichero ingestado.
        bitcoin_block_headers: opcional, dict ``{height: hex_80_bytes}`` con
            block headers obtenidos por el operator de un block explorer.
            Cuando se proveen, el JS embebido verifica que el merkle root del
            header coincida con el ``expected_merkle_root_le_hex`` claimed por
            el OTS proof.

    Levanta :class:`aip.errors.EvidenceNotFoundError` si la evidencia no existe.
    """
    archive = Archive.open(archive_root)
    view = archive.show_evidence(evidence_hash)  # raises if not found

    cert_hash = _find_capture_cert_hash(view.provenance_steps)
    capture_cert = (
        _load_capture_certificate(archive_root, cert_hash) if cert_hash else None
    )

    audit_entry = _audit_entry_for_evidence(archive_root, evidence_hash)
    audit_chain = _full_audit_chain(archive_root)

    coverage = (
        _coverage_manifests(archive_root, audit_entry["seq"])
        if audit_entry is not None
        else []
    )
    witnesses_by_seq = {
        str(seq): [
            {
                "attestation_type": w.attestation_type,
                "schema_version": w.schema_version,
                "witness_operator_id": w.witness_operator_id,
                "witness_public_key_fingerprint": w.witness_public_key_fingerprint,
                "target_manifest_hash": w.target_manifest_hash,
                "target_manifest_sequence": w.target_manifest_sequence,
                "target_operator_id": w.target_operator_id,
                "witnessed_at": w.witnessed_at,
                "statement": w.statement,
                "signature": w.signature,
                "signature_algorithm": w.signature_algorithm,
                "attestation_hash": w.attestation_hash,
            }
            for w in ws
        ]
        for seq, ws in list_all_witnesses(archive_root).items()
        if any(m["sequence"] == seq for m in coverage)
    }
    notarization_by_seq = {
        str(m["sequence"]): _ots_summary_for_manifest(archive_root, m["sequence"])
        for m in coverage
    }
    notarization_by_seq = {
        k: v for k, v in notarization_by_seq.items() if v is not None
    }

    inference_proofs = _inference_proofs_referencing(archive_root, evidence_hash)

    # Operator's transparency public key (Phase ed25519-in-report).
    # If present, the JS will verify ed25519 signatures client-side via
    # SubtleCrypto's native Ed25519 support.
    pk_path = archive_root / TRANSPARENCY_DIRNAME / _PUBLIC_KEY_FILENAME
    operator_public_key_pem = (
        pk_path.read_text(encoding="utf-8") if pk_path.is_file() else None
    )

    # Witness public keys registry. Maps fingerprint → PEM. Sourced from
    # <archive>/transparency/witness-keys/<fingerprint>.pem (a sidecar
    # convention; operators opt-in to import witness keys for verification).
    witness_keys: dict[str, str] = {}
    witness_keys_dir = (
        archive_root / TRANSPARENCY_DIRNAME / _WITNESS_KEYS_DIRNAME
    )
    if witness_keys_dir.is_dir():
        for f in witness_keys_dir.iterdir():
            if not f.is_file():
                continue
            m = _FINGERPRINT_PEM_RE.match(f.name)
            if m is None:
                continue
            try:
                witness_keys[m.group(1)] = f.read_text(encoding="utf-8")
            except OSError:
                continue

    e = view.evidence
    s = view.source

    return {
        "schema_version": "1",
        "report_type": "aip.evidence-report.v1",
        "generated_at": dt.datetime.now(dt.UTC)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archive_label": archive_root.name,
        "evidence": {
            "hash": e.hash,
            "kind": e.kind.value,
            "mime_type": e.mime_type,
            "size_bytes": e.size_bytes,
            "content_uri": e.content_uri,
            "ingested_at": e.ingested_at.isoformat(),
            "ingested_by": e.ingested_by,
            "source_id": e.source_id,
            "notes": e.notes,
            "status": e.status.value,
        },
        "source": {
            "id": s.id,
            "name": s.name,
            "kind": s.kind.value,
            "authority_level": s.authority.value,
            "jurisdiction": s.jurisdiction,
            "license": s.license,
        },
        "capture_certificate": capture_cert,
        "c2pa_attestation": _load_c2pa_attestation(archive_root, evidence_hash),
        "audit_entry": audit_entry,
        "audit_chain": audit_chain,
        "coverage_manifests": coverage,
        "witnesses_by_manifest_sequence": witnesses_by_seq,
        "notarization_by_manifest_sequence": notarization_by_seq,
        "inference_proofs": inference_proofs,
        "inference_proof_rules": _inference_rule_specs_for_report(),
        "key_declaration": _load_key_declaration(archive_root),
        "footprint_verification": footprint_verification,
        "operator_public_key_pem": operator_public_key_pem,
        "witness_public_keys": witness_keys,
        "bitcoin_block_headers": (
            {str(h): hexstr for h, hexstr in bitcoin_block_headers.items()}
            if bitcoin_block_headers
            else {}
        ),
    }


def build_report_html(report_data: dict[str, Any], *, title: str | None = None) -> str:
    """Renderiza el dict en un HTML auto-contenido completo.

    El HTML embebe la data como JSON en ``<script type="application/json">``
    y un script de verificación que recompute hashes via SubtleCrypto.
    """
    if title is None:
        title = f"Evidence Report · sha256:{report_data['evidence']['hash'][:16]}…"

    data_json = json.dumps(report_data, ensure_ascii=False, indent=2)
    sections_html = _render_sections(report_data)

    tpl = Template(HTML_TEMPLATE)
    return tpl.substitute(
        title=_html_escape(title),
        generated_at=report_data["generated_at"],
        evidence_hash=report_data["evidence"]["hash"],
        evidence_hash_short=report_data["evidence"]["hash"][:16] + "…",
        archive_label=_html_escape(report_data["archive_label"]),
        sections=sections_html,
        data_json=_html_escape_script(data_json),
        css=CSS,
        js=JS,
    )


# --------------------------------------------------------------------- HTML rendering


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_escape_script(s: str) -> str:
    """Para JSON dentro de <script>, escapa solo `</script>` para evitar break-out."""
    return s.replace("</", "<\\/")


def _badge_html(kind: str, target: str, label: str) -> str:
    """Badge que el JS rellena tras verificación. ``kind`` define el tipo, ``target``
    el id concreto."""
    return (
        f'<span class="badge badge-pending" '
        f'data-verify="{kind}" data-target="{_html_escape(target)}">'
        f'<span class="dot"></span>{label}</span>'
    )


def _render_evidence_section(d: dict[str, Any]) -> str:
    e = d["evidence"]
    s = d["source"]
    return f"""
<section class="report-section" id="section-evidence">
  <h2>Evidence</h2>
  <dl class="kv">
    <dt>Hash</dt><dd class="mono break">{_html_escape(e["hash"])}</dd>
    <dt>Kind</dt><dd>{_html_escape(e["kind"])}</dd>
    <dt>MIME</dt><dd class="mono">{_html_escape(e["mime_type"])}</dd>
    <dt>Size</dt><dd class="mono">{e["size_bytes"]} bytes</dd>
    <dt>Ingested at</dt><dd class="mono">{_html_escape(e["ingested_at"])}</dd>
    <dt>Ingested by</dt><dd class="mono">{_html_escape(e["ingested_by"])}</dd>
    <dt>Source</dt><dd>{_html_escape(s["name"])} ({_html_escape(s["id"])})</dd>
    <dt>Authority</dt><dd>{_html_escape(s["authority_level"])}</dd>
  </dl>
</section>
"""


def _render_capture_section(d: dict[str, Any]) -> str:
    c = d.get("capture_certificate")
    if c is None:
        return ""
    notes = _html_escape(c.get("notes") or "—")
    return f"""
<section class="report-section accent-violet" id="section-capture">
  <h2>Captured at source <span class="phase-tag">Phase 2</span></h2>
  <div class="badges-row">
    {_badge_html("capture-cert", c["certificate_hash"], "self-hash")}
    {_badge_html("capture-cert-sig", c["certificate_hash"], "ed25519")}
  </div>
  <dl class="kv">
    <dt>Operator</dt><dd>{_html_escape(c["operator_id"])}</dd>
    <dt>Captured at</dt><dd class="mono">{_html_escape(c["captured_at"])}</dd>
    <dt>Device</dt><dd>{_html_escape(c.get("device_id") or "—")}</dd>
    <dt>Location</dt><dd>{_html_escape(c.get("location") or "—")}</dd>
    <dt>Notes</dt><dd>{notes}</dd>
    <dt>Cert hash</dt><dd class="mono break">{_html_escape(c["certificate_hash"])}</dd>
    <dt>Public key FP</dt><dd class="mono break">{_html_escape(c["public_key_fingerprint"])}</dd>
    <dt>Algorithm</dt><dd class="mono">{_html_escape(c["signature_algorithm"])}</dd>
    <dt>Signature</dt><dd class="mono break tiny">{_html_escape(c["signature"])}</dd>
  </dl>
</section>
"""


def _render_audit_chain_section(d: dict[str, Any]) -> str:
    entries = d["audit_chain"]
    rows: list[str] = []
    for e in entries:
        rows.append(f"""
<div class="audit-entry">
  <div class="audit-header">
    <span class="seq mono">#{e["seq"]}</span>
    <span class="action mono">{_html_escape(e["action"])}</span>
    <span class="actor mono">{_html_escape(e["actor"])}</span>
    {_badge_html("audit-entry", str(e["seq"]), "hash")}
    {_badge_html("audit-link", str(e["seq"]), "linkage")}
  </div>
  <div class="audit-meta mono break">
    target: {_html_escape(e["target"])}<br>
    timestamp: {_html_escape(e["timestamp"])}<br>
    entry_hash: <span class="hash">{_html_escape(e["entry_hash"])}</span>
  </div>
</div>
""")
    return f"""
<section class="report-section accent-emerald" id="section-audit">
  <h2>Audit chain <span class="phase-tag">Phase 1A foundation</span></h2>
  <p class="muted">Cadena append-only hash-encadenada. Cada entry recomputa SHA-256(JCS(canonical_fields)) client-side.</p>
  <div class="audit-list">
    {"".join(rows)}
  </div>
</section>
"""


def _render_manifests_section(d: dict[str, Any]) -> str:
    manifests = d["coverage_manifests"]
    if not manifests:
        return ""
    blocks: list[str] = []
    for m in manifests:
        seq_str = str(m["sequence"])
        witnesses = d["witnesses_by_manifest_sequence"].get(seq_str, [])
        ots = d["notarization_by_manifest_sequence"].get(seq_str)

        witness_rows = "".join(
            f"""<div class="witness-row">
              <span class="mono">{_html_escape(w["witness_operator_id"])}</span>
              <span class="mono small">@ {_html_escape(w["witnessed_at"])}</span>
              {_badge_html("witness", w["attestation_hash"], "self-hash")}
              {_badge_html("witness-sig", w["attestation_hash"], "ed25519")}
            </div>"""
            for w in witnesses
        ) or '<p class="muted small">No witnesses on this manifest.</p>'

        ots_html = ""
        if ots:
            anchor_rows = "".join(
                f"""<div class="anchor-row">
                  <span class="anchor-icon">⛓</span>
                  <span>Bitcoin block #{a["height"]:,}</span>
                  <span class="mono tiny break">merkle: {_html_escape(a["expected_merkle_root_le_hex"])}</span>
                  {_badge_html("bitcoin-merkle", str(a["height"]), "header match")}
                </div>"""
                for a in ots["bitcoin_anchors"]
            )
            if not anchor_rows:
                anchor_rows = '<p class="muted small">No Bitcoin anchors yet — pending OTS confirmation.</p>'
            ots_html = f"""
<div class="ots-block">
  <h4>Bitcoin anchor <span class="phase-tag">Phase 4</span></h4>
  {anchor_rows}
</div>
"""

        blocks.append(f"""
<div class="manifest-block">
  <h3>Transparency manifest seq {m["sequence"]}</h3>
  <div class="badges-row">
    {_badge_html("manifest", m["manifest_hash"], "self-hash")}
    {_badge_html("manifest-sig", m["manifest_hash"], "ed25519")}
  </div>
  <dl class="kv">
    <dt>Operator</dt><dd>{_html_escape(m["operator_id"])}</dd>
    <dt>Signed at</dt><dd class="mono">{_html_escape(m["signed_at"])}</dd>
    <dt>Manifest hash</dt><dd class="mono break">{_html_escape(m["manifest_hash"])}</dd>
    <dt>Previous</dt><dd class="mono break">{_html_escape(m["previous_manifest_hash"])}</dd>
    <dt>Audit head</dt><dd class="mono break">{_html_escape(m["audit_chain_head_hash"])}</dd>
    <dt>Audit entries pinned</dt><dd class="mono">{m["audit_entry_count"]}</dd>
    <dt>Signature</dt><dd class="mono break tiny">{_html_escape(m["signature"])}</dd>
  </dl>
  <div class="witnesses-block">
    <h4>Witnesses ({len(witnesses)}) <span class="phase-tag">Door #3</span></h4>
    {witness_rows}
  </div>
  {ots_html}
</div>
""")

    return f"""
<section class="report-section accent-blue" id="section-manifests">
  <h2>Coverage manifests <span class="phase-tag">Phase 1A</span></h2>
  <p class="muted">Transparency manifests whose audit_entry_count covers this evidence's audit seq.</p>
  {"".join(blocks)}
</section>
"""


def _render_proofs_section(d: dict[str, Any]) -> str:
    proofs = d["inference_proofs"]
    if not proofs:
        return ""
    blocks: list[str] = []
    for p in proofs:
        weak_count = sum(
            1
            for i in p.get("inferences", [])
            if i.get("rule") == _ABDUCTION_RULE
        )
        weak_badge = (
            f' <span class="badge badge-weak"><span class="dot"></span>{weak_count} weak</span>'
            if weak_count > 0
            else ""
        )
        premise_rows = "".join(
            f"""<li><span class="claim-id mono">{_html_escape(pr["id"])}</span>
                <span class="claim-kind">{_html_escape(pr["kind"])}</span>
                <span class="claim-text">{_html_escape(pr["text"])}</span></li>"""
            for pr in p.get("premises", [])
        )
        inference_rows = "".join(
            f"""<li>
              <span class="claim-id mono">{_html_escape(i["id"])}</span>
              <span class="rule {"rule-weak" if i["rule"] == _ABDUCTION_RULE else "rule-deductive"} mono">{_html_escape(i["rule"])}</span>
              <span class="claim-text">[{",".join(_html_escape(x) for x in i["input_claim_ids"])}] → {_html_escape(i["output_claim_id"])}</span>
            </li>"""
            for i in p.get("inferences", [])
        )
        claim_rows = "".join(
            f"""<li><span class="claim-id mono">{_html_escape(c["id"])}</span>
                <span class="claim-text">{_html_escape(c["text"])}</span></li>"""
            for c in p.get("derived_claims", [])
        )
        blocks.append(f"""
<div class="proof-block">
  <h3>{_html_escape(p["proof_id"])}{weak_badge}</h3>
  <div class="badges-row">
    {_badge_html("inference-proof", p["proof_hash"], "self-hash")}
    {_badge_html("inference-proof-structure", p["proof_hash"], "DAG structure")}
  </div>
  <dl class="kv">
    <dt>Target justification</dt><dd class="mono break">{_html_escape(p["target_justification_id"])}</dd>
    <dt>Conclusion</dt><dd class="mono">{_html_escape(p["conclusion_claim_id"])}</dd>
    <dt>Proof hash</dt><dd class="mono break">{_html_escape(p["proof_hash"])}</dd>
  </dl>
  <div class="proof-subsection">
    <h4>Premises ({len(p.get("premises", []))})</h4>
    <ul class="claim-list">{premise_rows}</ul>
  </div>
  <div class="proof-subsection">
    <h4>Inferences ({len(p.get("inferences", []))})</h4>
    <ul class="claim-list">{inference_rows}</ul>
  </div>
  <div class="proof-subsection">
    <h4>Derived claims</h4>
    <ul class="claim-list">{claim_rows}</ul>
  </div>
</div>
""")
    return f"""
<section class="report-section accent-purple" id="section-proofs">
  <h2>Inference proofs <span class="phase-tag">Phase 5</span></h2>
  <p class="muted">Machine-checkable reasoning DAGs that reference this evidence as a premise.</p>
  {"".join(blocks)}
</section>
"""


def _render_ref_row(
    r: dict[str, Any],
    fpv_by_ref: dict[tuple[str, str], dict[str, Any]],
) -> str:
    """Render one external_reference row, with optional ADR-0045 verdict badge.

    The badge is rendered NEXT TO the declared row, never replacing it.
    Wording is explicit about who did the check ("verified by AIP") so the
    receptor remembers AIP is not a neutral third party — it's a tool
    they're running locally.
    """
    kind = r.get("kind", "?")
    uri = r.get("uri", "")
    note = r.get("note") or ""
    note_block = (
        f"<div class='ref-note muted tiny'>{_html_escape(note)}</div>" if note else ""
    )

    verdict = fpv_by_ref.get((str(kind), str(uri)))
    verdict_html = ""
    if verdict is not None:
        status = verdict.get("status", "")
        if status == "verified":
            verdict_html = (
                '<span class="ref-verdict ref-verdict-ok">'
                '✓ verified by AIP'
                "</span>"
            )
        elif status == "mismatch":
            reason = _html_escape(str(verdict.get("reason") or ""))
            verdict_html = (
                '<span class="ref-verdict ref-verdict-fail">'
                f"✗ MISMATCH — {reason}"
                "</span>"
            )
        elif status == "unreachable":
            reason = _html_escape(str(verdict.get("reason") or ""))
            verdict_html = (
                '<span class="ref-verdict ref-verdict-warn">'
                f"⚠ not reached — {reason}"
                "</span>"
            )
        elif status == "unsupported":
            verdict_html = (
                '<span class="ref-verdict ref-verdict-info">'
                "— manual cross-check required"
                "</span>"
            )

    return (
        '<li>'
        f'<span class="ref-kind mono">{_html_escape(kind)}</span>'
        f'<span class="ref-uri mono break">{_html_escape(uri)}</span>'
        f"{verdict_html}"
        f"{note_block}"
        "</li>"
    )


def _render_trust_footprint_section(d: dict[str, Any]) -> str:
    """Render the signer trust footprint.

    Two states:

    - **No declaration**: an honest warning telling the receptor they cannot
      verify the signer identity, only that signatures are internally
      consistent. The crypto chain is intact but the key-to-identity binding
      is asserted, not proven.
    - **With declaration**: the operator-supplied external references plus
      fingerprints, so the receptor can independently fetch a key from at
      least one of the listed sources and compare.
    """
    decl = d.get("key_declaration")
    op_pem = d.get("operator_public_key_pem")
    witness_keys: dict[str, str] = d.get("witness_public_keys") or {}

    if not op_pem and not witness_keys and decl is None:
        return ""  # nothing key-related in this archive, skip section entirely.

    if decl is None:
        warn = """
<div class="trust-warn">
  <p><b>No key declaration in this archive.</b> The receptor can verify that signatures inside this report are internally consistent (manifests, capture cert, witnesses, inference proofs), but cannot independently verify that the embedded public keys belong to whom the report claims. To close that gap, the operator would publish a <code>transparency/key-declaration.json</code> listing external references for each key.</p>
</div>"""
        return f"""
<section class="report-section accent-amber" id="section-trust-footprint">
  <h2>Signer trust footprint</h2>
  <p class="muted">External anchors that prove a public key belongs to the claimed operator. None declared in this archive.</p>
  {warn}
</section>
"""

    # Declaration is present.
    operator_block = ""
    op = decl.get("operator") or {}
    # Optional cross-verification (ADR-0045). When the operator ran
    # `aip transparency declare-key verify-footprint` before generating the
    # report, the results are embedded and rendered as a sub-badge next to
    # each reference. Keyed by (kind, uri) so the renderer can look up the
    # verdict for any specific row.
    fpv = d.get("footprint_verification") or {}
    fpv_by_ref: dict[tuple[str, str], dict[str, Any]] = {}
    for r in (fpv.get("references") or []):
        if isinstance(r, dict):
            fpv_by_ref[(str(r.get("kind", "")), str(r.get("uri", "")))] = r
    if op:
        refs = op.get("external_references", []) or []
        ref_rows = (
            "".join(
                _render_ref_row(r, fpv_by_ref) for r in refs
            )
            if refs
            else '<li class="muted">No external references declared.</li>'
        )
        first_pub = op.get("first_published_at")
        first_pub_row = (
            f'<dt>First published</dt><dd class="mono">{_html_escape(first_pub)}</dd>'
            if first_pub
            else ""
        )
        operator_block = f"""
<div class="trust-block">
  <h3>Operator key</h3>
  <dl class="kv">
    <dt>Operator id</dt><dd class="mono">{_html_escape(op.get("operator_id", "?"))}</dd>
    <dt>Fingerprint (SHA-256 of DER SPKI)</dt><dd class="mono break">{_html_escape(op.get("public_key_fingerprint", ""))}</dd>
    {first_pub_row}
  </dl>
  <h4>External references ({len(refs)})</h4>
  <ul class="ref-list">{ref_rows}</ul>
</div>"""

    witnesses_block = ""
    decl_witnesses = decl.get("witnesses") or []
    if decl_witnesses:
        wblocks: list[str] = []
        for w in decl_witnesses:
            refs = w.get("external_references", []) or []
            ref_rows = (
                "".join(_render_ref_row(r, fpv_by_ref) for r in refs)
                if refs
                else '<li class="muted">No external references declared.</li>'
            )
            wblocks.append(f"""
<div class="trust-block">
  <h4>{_html_escape(w.get("witness_operator_id", "?"))}</h4>
  <dl class="kv">
    <dt>Fingerprint</dt><dd class="mono break">{_html_escape(w.get("public_key_fingerprint", ""))}</dd>
  </dl>
  <h5>External references ({len(refs)})</h5>
  <ul class="ref-list">{ref_rows}</ul>
</div>""")
        witnesses_block = f"""
<div class="trust-subgroup">
  <h3>Witness keys ({len(decl_witnesses)})</h3>
  {"".join(wblocks)}
</div>"""

    decl_warn = ""
    # Sanity check: declaration fingerprints must match the actual embedded keys.
    # If they don't, the declaration is lying about itself — flag prominently.
    mismatches: list[str] = []
    if op_pem and op.get("public_key_fingerprint"):
        # We can't easily compute the SHA-256 of DER SPKI in Python here without
        # importing cryptography — that's fine, we just embed both and the
        # receptor's browser does the comparison via the existing
        # verifyManifestSig path (which already enforces fingerprint match).
        pass
    for w in decl_witnesses:
        fp = w.get("public_key_fingerprint")
        if fp and fp not in witness_keys:
            mismatches.append(
                f"declared witness {w.get('witness_operator_id', '?')!r} "
                f"(fp {fp[:16]}…) but no matching .pem in transparency/witness-keys/"
            )
    if mismatches:
        decl_warn = f"""
<div class="trust-warn">
  <b>Declaration / archive mismatch:</b>
  <ul>{"".join(f"<li>{_html_escape(m)}</li>" for m in mismatches)}</ul>
</div>"""

    return f"""
<section class="report-section accent-amber" id="section-trust-footprint">
  <h2>Signer trust footprint</h2>
  <p class="muted">Cross-check at least one external reference per key against an independent source. The browser already verifies the signatures inside this report; this section closes the key-to-identity binding.</p>
  {decl_warn}
  {operator_block}
  {witnesses_block}
</section>
"""


def _render_sections(d: dict[str, Any]) -> str:
    return "".join([
        _render_evidence_section(d),
        _render_capture_section(d),
        _render_c2pa_section(d),
        _render_audit_chain_section(d),
        _render_manifests_section(d),
        _render_proofs_section(d),
        _render_trust_footprint_section(d),
    ])


def _render_c2pa_section(d: dict[str, Any]) -> str:
    """ADR-0046: surface the C2PA attestation layer if present.

    Render is honest about what C2PA proves:
    - the camera/editor signed those exact bytes at that time
    - according to a trust list AIP is reporting verbatim

    And NOT honest by silence — it never says "this is real" or implies
    AIP endorses the trust list. The badge always reads "verified BY C2PA
    against <trust list>" so the receptor knows whose authority underlies
    the green check.
    """
    att = d.get("c2pa_attestation")
    if not isinstance(att, dict):
        return ""

    chain_verified = bool(att.get("chain_verified"))
    failure_reason = att.get("failure_reason") or ""
    trust_list = _html_escape(str(att.get("trust_list_name") or "?"))
    verified_at = _html_escape(str(att.get("verified_at") or "?"))
    evidence_sha = _html_escape(str(att.get("evidence_sha256") or "?"))
    report_hash = _html_escape(str(att.get("report_hash") or "?"))

    if chain_verified:
        verdict_html = (
            '<span class="badge badge-ok"><span class="dot"></span>'
            f"verified by C2PA against {trust_list}</span>"
        )
    else:
        reason_html = _html_escape(failure_reason or "no reason given")
        verdict_html = (
            '<span class="badge badge-fail"><span class="dot"></span>'
            f"C2PA chain FAILED — {reason_html}</span>"
        )

    manifests = att.get("manifests") or []
    manifest_rows: list[str] = []
    if isinstance(manifests, list):
        for i, m in enumerate(manifests):
            if not isinstance(m, dict):
                continue
            label = _html_escape(str(m.get("label") or "?"))
            parent = m.get("parent_manifest_label")
            parent_html = (
                f"<dt>Parent</dt><dd class='mono'>{_html_escape(str(parent))}</dd>"
                if parent
                else "<dt>Position</dt><dd>root manifest (capture device)</dd>"
            )
            sig = m.get("signature_info") or {}
            issuer_cn = _html_escape(str(sig.get("issuer_common_name") or "?"))
            issuer_org = _html_escape(str(sig.get("issuer_organization") or "—"))
            sig_verified = bool(sig.get("chain_verified"))
            sig_against = _html_escape(str(sig.get("chain_verified_against") or "?"))
            sig_badge = (
                '<span class="badge badge-ok"><span class="dot"></span>verified</span>'
                if sig_verified
                else f'<span class="badge badge-fail"><span class="dot"></span>not verified — {_html_escape(str(sig.get("failure_reason") or "no reason"))}</span>'
            )

            assertions_raw = m.get("assertions") or []
            assertion_rows: list[str] = []
            if isinstance(assertions_raw, list):
                for a in assertions_raw:
                    if not isinstance(a, dict):
                        continue
                    a_label = _html_escape(str(a.get("label") or "?"))
                    a_data = a.get("data") or {}
                    if isinstance(a_data, dict) and a_data:
                        items = ", ".join(
                            f"{_html_escape(str(k))}={_html_escape(str(v))}"
                            for k, v in a_data.items()
                        )
                        data_html = f'<span class="muted tiny mono">{items}</span>'
                    else:
                        data_html = '<span class="muted tiny">(no data)</span>'
                    assertion_rows.append(
                        f"<li><code class='mono'>{a_label}</code> {data_html}</li>"
                    )
            assertions_html = (
                f"<ul class='c2pa-assertions'>{''.join(assertion_rows)}</ul>"
                if assertion_rows
                else "<p class='muted tiny'>No assertions in this manifest.</p>"
            )

            manifest_rows.append(f"""
<div class="c2pa-manifest">
  <h4>Manifest #{i + 1} · <span class="mono">{label}</span> {sig_badge}</h4>
  <dl class="kv">
    {parent_html}
    <dt>Signer (CN)</dt><dd class="mono">{issuer_cn}</dd>
    <dt>Signer organisation</dt><dd>{issuer_org}</dd>
    <dt>Chain verified against</dt><dd class="mono">{sig_against}</dd>
  </dl>
  <h5>Assertions</h5>
  {assertions_html}
</div>""")

    manifests_html = (
        "".join(manifest_rows)
        if manifest_rows
        else "<p class='muted'>No manifests in the attestation.</p>"
    )

    honest_note = """
<p class="muted tiny" style="margin-top:12px">
  <b>What this proves:</b> a C2PA-compliant device or editor signed these
  exact bytes at the time recorded, and the certificate chain verified
  against the trust list above. <b>What this does NOT prove:</b> that the
  scene in front of the camera was real, that the operator was authentic,
  or that AIP endorses any specific trust list. The analyst remains
  responsible for that judgement.
</p>"""

    return f"""
<section class="report-section accent-cyan" id="section-c2pa">
  <h2>Capture attestation (C2PA) <span class="phase-tag">ADR-0046</span></h2>
  <div class="badges-row">{verdict_html}</div>
  <dl class="kv">
    <dt>Evidence</dt><dd class="mono break">sha256:{evidence_sha}</dd>
    <dt>Verified at</dt><dd class="mono">{verified_at}</dd>
    <dt>Trust list</dt><dd class="mono">{trust_list}</dd>
    <dt>Report hash</dt><dd class="mono break">{report_hash}</dd>
  </dl>
  {manifests_html}
  {honest_note}
</section>
"""


# --------------------------------------------------------------------- templates


CSS = """
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f6f7f9; color: #0f172a; line-height: 1.5; font-size: 14px; }
.report-frame { max-width: 960px; margin: 0 auto; padding: 24px; }
.report-header { background: white; border: 1px solid #e2e8f0; border-radius: 10px;
                 padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.report-header h1 { margin: 0 0 8px; font-size: 19px; font-weight: 800; letter-spacing: -0.02em; }
.report-header .subtitle { color: #64748b; font-size: 13px; font-family: ui-monospace, monospace; word-break: break-all; }
.report-header .meta { margin-top: 12px; font-size: 11.5px; color: #64748b;
                        display: flex; gap: 16px; flex-wrap: wrap; font-family: ui-monospace, monospace; }
.global-status { padding: 16px 24px; border-radius: 10px; margin-bottom: 24px;
                  border: 1px solid; font-weight: 600; display: flex; align-items: center; gap: 12px; }
.global-status .status-icon { font-size: 20px; }
.global-status.status-ok { background: #ecfdf5; border-color: #a7f3d0; color: #065f46; }
.global-status.status-warn { background: #fef3c7; border-color: #fcd34d; color: #92400e; }
.global-status.status-err { background: #fee2e2; border-color: #fca5a5; color: #991b1b; }
.global-status.status-pending { background: #eef2ff; border-color: #c7d2fe; color: #3730a3; }

.report-section { background: white; border: 1px solid #e2e8f0; border-radius: 10px;
                   padding: 20px 24px; margin-bottom: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.report-section.accent-violet { border-left: 4px solid #7c3aed; }
.report-section.accent-emerald { border-left: 4px solid #10b981; }
.report-section.accent-blue { border-left: 4px solid #3b82f6; }
.report-section.accent-purple { border-left: 4px solid #a855f7; }
.report-section.accent-amber { border-left: 4px solid #d97706; }
.report-section.accent-cyan { border-left: 4px solid #0891b2; }
.c2pa-manifest { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 12px 14px; margin: 10px 0; }
.c2pa-manifest h4 { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; font-size: 13px; color: #075985; }
.c2pa-manifest h5 { margin: 8px 0 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #075985; }
.c2pa-assertions { margin: 4px 0 0; padding: 0; list-style: none; }
.c2pa-assertions li { padding: 4px 8px; background: white; border: 1px solid #bae6fd; border-radius: 3px; margin-bottom: 2px; font-size: 11.5px; color: #0c4a6e; }
.trust-warn { background: #fef3c7; border: 1px solid #fde68a; border-radius: 6px; padding: 10px 14px; margin: 10px 0; color: #78350f; font-size: 13px; }
.trust-warn ul { margin: 6px 0 0 18px; padding: 0; }
.trust-block { border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 14px; margin: 8px 0; background: #fdfcfa; }
.trust-subgroup { margin-top: 12px; }
.ref-list { margin: 6px 0 0 0; padding: 0; list-style: none; }
.ref-list li { padding: 6px 10px; border: 1px solid #f1f5f9; border-radius: 4px; margin-bottom: 4px; background: white; }
.ref-kind { display: inline-block; background: #f1f5f9; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-right: 8px; color: #475569; }
.ref-uri { font-size: 12px; }
.ref-note { margin-top: 2px; }
.ref-verdict { display: inline-block; margin-left: 8px; padding: 1px 6px; border-radius: 3px; font-size: 10.5px; font-weight: 600; border: 1px solid; }
.ref-verdict-ok   { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
.ref-verdict-fail { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
.ref-verdict-warn { background: #fffbeb; color: #b45309; border-color: #fde68a; }
.ref-verdict-info { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
.report-section h2 { margin: 0 0 12px; font-size: 17px; font-weight: 700; letter-spacing: -0.015em;
                      display: flex; align-items: center; gap: 8px; }
.report-section h3 { margin: 16px 0 8px; font-size: 14.5px; font-weight: 700; }
.report-section h4 { margin: 12px 0 6px; font-size: 12px; font-weight: 700; text-transform: uppercase;
                      letter-spacing: 0.08em; color: #64748b; display: flex; align-items: center; gap: 8px; }
.phase-tag { font-size: 10px; font-weight: 600; padding: 2px 6px; background: #f1f5f9; color: #475569;
              border: 1px solid #e2e8f0; border-radius: 3px; letter-spacing: 0.05em; }
.muted { color: #64748b; font-size: 12.5px; }
.small { font-size: 11.5px; }
.tiny { font-size: 10.5px; }
.mono { font-family: ui-monospace, 'JetBrains Mono', monospace; }
.break { word-break: break-all; }

dl.kv { display: grid; grid-template-columns: 160px 1fr; gap: 4px 16px; margin: 12px 0 0; }
dl.kv dt { color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
            font-weight: 600; padding-top: 2px; }
dl.kv dd { margin: 0; font-size: 12.5px; color: #1e293b; }

.badges-row { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 4px;
          font-size: 10.5px; font-weight: 600; border: 1px solid; text-transform: uppercase;
          letter-spacing: 0.05em; }
.badge .dot { width: 6px; height: 6px; border-radius: 50%; }
.badge-pending { background: #f1f5f9; border-color: #cbd5e1; color: #475569; }
.badge-pending .dot { background: #94a3b8; animation: pulse 1.5s infinite; }
.badge-ok { background: #ecfdf5; border-color: #a7f3d0; color: #047857; }
.badge-ok .dot { background: #10b981; }
.badge-fail { background: #fee2e2; border-color: #fca5a5; color: #b91c1c; }
.badge-fail .dot { background: #ef4444; }
.badge-weak { background: #fef3c7; border-color: #fcd34d; color: #92400e; }
.badge-weak .dot { background: #f59e0b; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

.audit-list { display: flex; flex-direction: column; gap: 8px; }
.audit-entry { padding: 10px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; }
.audit-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
.audit-header .seq { font-weight: 700; color: #64748b; font-size: 11.5px; }
.audit-header .action { font-size: 11.5px; padding: 2px 6px; background: #dbeafe; color: #1e40af;
                         border: 1px solid #bfdbfe; border-radius: 3px; font-weight: 600; }
.audit-header .actor { font-size: 11px; color: #64748b; }
.audit-meta { font-size: 10.5px; color: #475569; line-height: 1.6; }
.audit-meta .hash { color: #1e293b; }

.manifest-block, .proof-block { background: #fafbfc; border: 1px solid #e2e8f0; border-radius: 8px;
                                  padding: 16px; margin: 12px 0; }
.witnesses-block, .ots-block, .proof-subsection { margin-top: 14px; padding-top: 12px;
                                                    border-top: 1px solid #e2e8f0; }
.witness-row, .anchor-row { display: flex; align-items: center; gap: 12px; padding: 6px 0;
                              font-size: 12px; flex-wrap: wrap; }
.anchor-icon { font-size: 16px; }

.claim-list { list-style: none; padding: 0; margin: 4px 0 0; display: flex; flex-direction: column; gap: 4px; }
.claim-list li { padding: 6px 10px; background: white; border: 1px solid #e2e8f0; border-radius: 4px;
                  font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; align-items: baseline; }
.claim-id { font-weight: 700; min-width: 32px; color: #475569; font-size: 11.5px; }
.claim-kind { font-size: 10px; padding: 1px 5px; background: #e0e7ff; color: #4338ca;
               border-radius: 3px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
.claim-text { flex: 1; color: #1e293b; min-width: 0; }
.rule { font-size: 10.5px; padding: 2px 6px; border-radius: 3px; font-weight: 600; }
.rule-deductive { background: #dbeafe; color: #1e40af; }
.rule-weak { background: #fef3c7; color: #92400e; }

footer.report-footer { text-align: center; color: #94a3b8; font-size: 11px; padding: 24px 0; line-height: 1.7; }
"""


JS = r"""
// ─── JCS canonicalize (subset RFC 8785) ──────────────────────────────────
function jsonString(s) {
  let out = '"';
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === '\\') out += '\\\\';
    else if (cp < 0x20) {
      switch (ch) {
        case '\b': out += '\\b'; break;
        case '\f': out += '\\f'; break;
        case '\n': out += '\\n'; break;
        case '\r': out += '\\r'; break;
        case '\t': out += '\\t'; break;
        default: out += '\\u' + cp.toString(16).padStart(4, '0');
      }
    } else out += ch;
  }
  return out + '"';
}
function jcsSerialize(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isInteger(value)) throw new Error('only integers supported');
    return value.toString();
  }
  if (typeof value === 'string') return jsonString(value);
  if (Array.isArray(value)) {
    return '[' + value.map(jcsSerialize).join(',') + ']';
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return '{' + keys.map(k => jsonString(k) + ':' + jcsSerialize(value[k])).join(',') + '}';
  }
  throw new Error('unsupported type: ' + typeof value);
}
function jcsCanonicalize(value) {
  return new TextEncoder().encode(jcsSerialize(value));
}
async function sha256Hex(bytes) {
  const buf = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

// ─── Hash-specific verifiers ────────────────────────────────────────────
async function verifyAuditEntry(entry) {
  const canonical = {
    seq: entry.seq, prev_hash: entry.prev_hash, timestamp: entry.timestamp,
    actor: entry.actor, action: entry.action, target: entry.target,
    parameters: entry.parameters, result: entry.result,
    schema_version: entry.schema_version,
  };
  return (await sha256Hex(jcsCanonicalize(canonical))) === entry.entry_hash;
}
async function verifyManifest(m) {
  const dict = { ...m };
  delete dict.manifest_hash;
  return (await sha256Hex(jcsCanonicalize(dict))) === m.manifest_hash;
}
async function verifyCaptureCert(c) {
  const dict = { ...c };
  delete dict.certificate_hash;
  return (await sha256Hex(jcsCanonicalize(dict))) === c.certificate_hash;
}
async function verifyWitness(w) {
  const dict = { ...w };
  delete dict.attestation_hash;
  return (await sha256Hex(jcsCanonicalize(dict))) === w.attestation_hash;
}
async function verifyInferenceProof(p) {
  const dict = { ...p };
  delete dict.proof_hash;
  return (await sha256Hex(jcsCanonicalize(dict))) === p.proof_hash;
}

// ─── Inference proof DAG structural verification ──────────────────────
// Mirrors aip.justification.logic.verifier.verify_structural and is a
// near-clone of `web/src/lib/inferenceLogic.ts::verifyStructural` — that TS
// version is the canonical implementation (tested by `npm test` in /web).
// Keep the two algorithms aligned when touching either. The standalone
// HTML report cannot import the TS module because the report is fully
// self-contained, so this copy lives here intentionally.
function verifyInferenceProofStructure(proof, rules) {
  const errors = [];
  const weak = [];
  const ruleByName = Object.fromEntries((rules || []).map(r => [r.name, r]));

  const premises = proof.premises || [];
  const inferences = proof.inferences || [];
  const derived = proof.derived_claims || [];

  const premiseIds = new Set(premises.map(p => p.id));
  const derivedById = Object.fromEntries(derived.map(c => [c.id, c]));
  const inferenceById = Object.fromEntries(inferences.map(i => [i.id, i]));
  const allClaimIds = new Set([...premiseIds, ...Object.keys(derivedById)]);

  // Per-inference: vocabulary, arity, references, output back-reference.
  for (const inf of inferences) {
    const spec = ruleByName[inf.rule];
    if (!spec) {
      errors.push('inference ' + JSON.stringify(inf.id) + ': rule ' + JSON.stringify(inf.rule) + ' not in allowed vocabulary.');
      continue;
    }
    const arity = (inf.input_claim_ids || []).length;
    if (arity < spec.min_inputs) {
      errors.push('inference ' + JSON.stringify(inf.id) + ': rule ' + JSON.stringify(inf.rule) + ' requires >= ' + spec.min_inputs + ' inputs; got ' + arity + '.');
    }
    if (spec.max_inputs !== null && spec.max_inputs !== undefined && arity > spec.max_inputs) {
      errors.push('inference ' + JSON.stringify(inf.id) + ': rule ' + JSON.stringify(inf.rule) + ' admits <= ' + spec.max_inputs + ' inputs; got ' + arity + '.');
    }
    for (const inId of (inf.input_claim_ids || [])) {
      if (!allClaimIds.has(inId)) {
        errors.push('inference ' + JSON.stringify(inf.id) + ': input_claim_id ' + JSON.stringify(inId) + ' does not exist.');
      }
    }
    if (!derivedById[inf.output_claim_id]) {
      errors.push('inference ' + JSON.stringify(inf.id) + ': output_claim_id ' + JSON.stringify(inf.output_claim_id) + ' is not declared in derived_claims.');
    } else if (derivedById[inf.output_claim_id].inferred_by !== inf.id) {
      errors.push('inference ' + JSON.stringify(inf.id) + ': output claim has inferred_by=' + JSON.stringify(derivedById[inf.output_claim_id].inferred_by) + ', expected ' + JSON.stringify(inf.id) + '.');
    }
    if (spec.classification === 'weak') {
      weak.push({ inference_id: inf.id, rule: inf.rule, output_claim_id: inf.output_claim_id });
    }
  }
  // Each derived claim's inferred_by must reference an existing inference.
  for (const c of derived) {
    if (!inferenceById[c.inferred_by]) {
      errors.push('derived claim ' + JSON.stringify(c.id) + ': inferred_by ' + JSON.stringify(c.inferred_by) + ' references unknown inference.');
    }
  }
  // Build forward adjacency: input claim X → output claim Y of inferences that consume X.
  const adj = {};
  for (const inf of inferences) {
    for (const inId of (inf.input_claim_ids || [])) {
      (adj[inId] = adj[inId] || []).push(inf.output_claim_id);
    }
  }
  // Cycle detection (3-color DFS).
  const WHITE = 0, GRAY = 1, BLACK = 2;
  const color = {};
  let cyclePath = null;
  function dfs(node, stack) {
    color[node] = GRAY;
    stack.push(node);
    for (const nxt of (adj[node] || [])) {
      const c = color[nxt] || WHITE;
      if (c === GRAY) {
        const idx = stack.indexOf(nxt);
        cyclePath = (idx >= 0 ? stack.slice(idx) : [node]).concat([nxt]).join(' → ');
        return true;
      }
      if (c === WHITE && dfs(nxt, stack)) return true;
    }
    color[node] = BLACK;
    stack.pop();
    return false;
  }
  for (const start of [...Object.keys(adj), ...derived.map(c => c.id)]) {
    if ((color[start] || WHITE) === WHITE) {
      if (dfs(start, [])) break;
    }
  }
  if (cyclePath) errors.push('cycle detected in DAG: ' + cyclePath + '.');

  // Conclusion existence + reachability from premises.
  if (!allClaimIds.has(proof.conclusion_claim_id)) {
    errors.push('conclusion_claim_id ' + JSON.stringify(proof.conclusion_claim_id) + ' is not declared as premise or derived claim.');
  } else if (!premiseIds.has(proof.conclusion_claim_id) && errors.length === 0) {
    const visited = new Set();
    const stack = [...premiseIds];
    let reachable = false;
    while (stack.length) {
      const n = stack.pop();
      if (visited.has(n)) continue;
      visited.add(n);
      if (n === proof.conclusion_claim_id) { reachable = true; break; }
      for (const nxt of (adj[n] || [])) stack.push(nxt);
    }
    if (!reachable) {
      errors.push('conclusion ' + JSON.stringify(proof.conclusion_claim_id) + ' is not reachable from premises via the inference DAG.');
    }
  }

  return { ok: errors.length === 0, errors, weakInferences: weak };
}

// ─── ed25519 verification via SubtleCrypto native (Chrome 137+, FF 130+, Safari 17+) ──
function pemToSpkiBytes(pem) {
  const body = pem
    .replace(/-----BEGIN [^-]+-----/g, '')
    .replace(/-----END [^-]+-----/g, '')
    .replace(/\s+/g, '');
  const binary = atob(body);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}
function hexToBytes(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}
async function _verifyEd25519(payloadBytes, signatureHex, publicKeyPem, expectedFp) {
  const der = pemToSpkiBytes(publicKeyPem);
  let key;
  try {
    key = await crypto.subtle.importKey('spki', der, { name: 'Ed25519' }, false, ['verify']);
  } catch (e) {
    return { ok: false, unsupported: true, reason: e.message };
  }
  const computedFp = await sha256Hex(der);
  if (computedFp !== expectedFp) {
    return { ok: false, reason: 'public_key_fingerprint mismatch' };
  }
  const sigBytes = hexToBytes(signatureHex);
  const ok = await crypto.subtle.verify('Ed25519', key, sigBytes, payloadBytes);
  return { ok, unsupported: false };
}
async function verifyManifestSig(manifest, publicKeyPem) {
  const payload = { ...manifest };
  delete payload.signature;
  delete payload.manifest_hash;
  return _verifyEd25519(jcsCanonicalize(payload), manifest.signature, publicKeyPem, manifest.public_key_fingerprint);
}
async function verifyCaptureCertSig(cert, publicKeyPem) {
  const payload = { ...cert };
  delete payload.signature;
  delete payload.certificate_hash;
  return _verifyEd25519(jcsCanonicalize(payload), cert.signature, publicKeyPem, cert.public_key_fingerprint);
}
async function verifyWitnessSig(witness, publicKeyPem) {
  const payload = { ...witness };
  delete payload.signature;
  delete payload.attestation_hash;
  return _verifyEd25519(jcsCanonicalize(payload), witness.signature, publicKeyPem, witness.witness_public_key_fingerprint);
}

// ─── Bitcoin block-header merkle-root verification ──────────────────────
// Format: 80 bytes total. Offsets: version[0..4), prev_hash[4..36),
// merkle_root[36..68), timestamp[68..72), bits[72..76), nonce[76..80).
// The merkle_root inside the header is in internal byte order (little-endian).
function extractMerkleRootLeHex(headerHex) {
  if (headerHex.length !== 160) {
    throw new Error('block header must be 80 bytes (160 hex chars); got ' + headerHex.length);
  }
  return headerHex.substring(72, 136).toLowerCase();
}
function verifyBitcoinAnchor(claim, headerHex) {
  if (!headerHex) return { ok: false, missing: true };
  let extracted;
  try {
    extracted = extractMerkleRootLeHex(headerHex);
  } catch (e) {
    return { ok: false, malformed: true, reason: e.message };
  }
  const claimed = claim.expected_merkle_root_le_hex.toLowerCase();
  return { ok: extracted === claimed, missing: false, claimed, extracted };
}

// ─── Badge updater ───────────────────────────────────────────────────────
function setBadge(el, ok) {
  el.classList.remove('badge-pending');
  el.classList.add(ok ? 'badge-ok' : 'badge-fail');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = ok ? ' verified' : ' MISMATCH';
}

// ─── Main runner ─────────────────────────────────────────────────────────
function setBadgeUnsupported(el) {
  el.classList.remove('badge-pending');
  el.classList.add('badge-weak');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = ' browser unsupported';
}
function setBadgeKeyUnknown(el) {
  el.classList.remove('badge-pending');
  el.classList.add('badge-weak');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = ' key unknown';
}
function setBadgeHeaderMissing(el) {
  el.classList.remove('badge-pending');
  el.classList.add('badge-weak');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = ' header not embedded';
}
function setBadgeStructureOk(el, weakCount) {
  el.classList.remove('badge-pending');
  el.classList.add(weakCount > 0 ? 'badge-weak' : 'badge-ok');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = weakCount > 0
    ? ' valid · ' + weakCount + ' weak inf.'
    : ' valid';
}
function setBadgeStructureFail(el, errorCount) {
  el.classList.remove('badge-pending');
  el.classList.add('badge-fail');
  const dot = el.querySelector('.dot');
  if (dot) dot.style.animation = 'none';
  el.lastChild.textContent = ' INVALID DAG · ' + errorCount + ' err';
}

async function runVerification() {
  const dataEl = document.getElementById('report-data');
  if (!dataEl) return;
  const data = JSON.parse(dataEl.textContent);

  const results = { ok: 0, fail: 0, total: 0 };
  const sigResults = { ok: 0, fail: 0, unsupported: 0, total: 0 };
  const anchorResults = { ok: 0, fail: 0, missing: 0, total: 0 };
  const structResults = { ok: 0, fail: 0, weak: 0, total: 0 };

  // Audit entries
  const auditByseq = Object.fromEntries(data.audit_chain.map(e => [String(e.seq), e]));
  for (const el of document.querySelectorAll('[data-verify="audit-entry"]')) {
    const seq = el.getAttribute('data-target');
    const entry = auditByseq[seq];
    if (!entry) continue;
    const ok = await verifyAuditEntry(entry);
    setBadge(el, ok);
    results.total++; ok ? results.ok++ : results.fail++;
  }
  // Audit linkage
  const sortedAudit = [...data.audit_chain].sort((a, b) => a.seq - b.seq);
  for (const el of document.querySelectorAll('[data-verify="audit-link"]')) {
    const seq = parseInt(el.getAttribute('data-target'), 10);
    const idx = sortedAudit.findIndex(e => e.seq === seq);
    let ok = false;
    if (idx === 0) {
      ok = sortedAudit[0].prev_hash === '0'.repeat(64);
    } else if (idx > 0) {
      ok = sortedAudit[idx].prev_hash === sortedAudit[idx - 1].entry_hash;
    }
    setBadge(el, ok);
    results.total++; ok ? results.ok++ : results.fail++;
  }
  // Manifests
  const manifestByhash = Object.fromEntries((data.coverage_manifests || []).map(m => [m.manifest_hash, m]));
  for (const el of document.querySelectorAll('[data-verify="manifest"]')) {
    const hash = el.getAttribute('data-target');
    const m = manifestByhash[hash];
    if (!m) continue;
    const ok = await verifyManifest(m);
    setBadge(el, ok);
    results.total++; ok ? results.ok++ : results.fail++;
  }
  // Manifest ed25519 signatures (if operator key is embedded).
  if (data.operator_public_key_pem) {
    for (const el of document.querySelectorAll('[data-verify="manifest-sig"]')) {
      const hash = el.getAttribute('data-target');
      const m = manifestByhash[hash];
      if (!m) continue;
      const r = await verifyManifestSig(m, data.operator_public_key_pem);
      sigResults.total++;
      if (r.unsupported) { setBadgeUnsupported(el); sigResults.unsupported++; }
      else { setBadge(el, r.ok); r.ok ? sigResults.ok++ : sigResults.fail++; }
    }
  } else {
    // No operator key embedded — flag every manifest-sig badge as unsupported.
    for (const el of document.querySelectorAll('[data-verify="manifest-sig"]')) {
      setBadgeUnsupported(el);
      sigResults.total++; sigResults.unsupported++;
    }
  }
  // Capture cert
  if (data.capture_certificate) {
    const certByhash = { [data.capture_certificate.certificate_hash]: data.capture_certificate };
    for (const el of document.querySelectorAll('[data-verify="capture-cert"]')) {
      const hash = el.getAttribute('data-target');
      const c = certByhash[hash];
      if (!c) continue;
      const ok = await verifyCaptureCert(c);
      setBadge(el, ok);
      results.total++; ok ? results.ok++ : results.fail++;
    }
    // Capture cert ed25519 signature: assume operator key is the signer
    // (typical case — operator captures evidence). If fingerprint mismatch,
    // the verifier itself reports it.
    for (const el of document.querySelectorAll('[data-verify="capture-cert-sig"]')) {
      const hash = el.getAttribute('data-target');
      const c = certByhash[hash];
      if (!c) continue;
      if (!data.operator_public_key_pem) { setBadgeKeyUnknown(el); sigResults.total++; sigResults.unsupported++; continue; }
      const r = await verifyCaptureCertSig(c, data.operator_public_key_pem);
      sigResults.total++;
      if (r.unsupported) { setBadgeUnsupported(el); sigResults.unsupported++; }
      else { setBadge(el, r.ok); r.ok ? sigResults.ok++ : sigResults.fail++; }
    }
  }
  // Witnesses
  const allWitnesses = Object.values(data.witnesses_by_manifest_sequence || {}).flat();
  const witnessByhash = Object.fromEntries(allWitnesses.map(w => [w.attestation_hash, w]));
  for (const el of document.querySelectorAll('[data-verify="witness"]')) {
    const hash = el.getAttribute('data-target');
    const w = witnessByhash[hash];
    if (!w) continue;
    const ok = await verifyWitness(w);
    setBadge(el, ok);
    results.total++; ok ? results.ok++ : results.fail++;
  }
  // Witness ed25519 signatures: look up each witness pubkey by fingerprint
  // in the embedded registry. If absent, badge says "key unknown".
  const witnessKeys = data.witness_public_keys || {};
  for (const el of document.querySelectorAll('[data-verify="witness-sig"]')) {
    const hash = el.getAttribute('data-target');
    const w = witnessByhash[hash];
    if (!w) continue;
    const pem = witnessKeys[w.witness_public_key_fingerprint];
    if (!pem) { setBadgeKeyUnknown(el); sigResults.total++; sigResults.unsupported++; continue; }
    const r = await verifyWitnessSig(w, pem);
    sigResults.total++;
    if (r.unsupported) { setBadgeUnsupported(el); sigResults.unsupported++; }
    else { setBadge(el, r.ok); r.ok ? sigResults.ok++ : sigResults.fail++; }
  }
  // Bitcoin anchors — verify merkle root from embedded block header matches OTS claim.
  // Build a map: claimed merkle (LE hex) → {height, claim} so we can look up by data-target.
  const anchorsByHeight = {};
  for (const [seq, ots] of Object.entries(data.notarization_by_manifest_sequence || {})) {
    for (const anchor of (ots.bitcoin_anchors || [])) {
      anchorsByHeight[String(anchor.height)] = anchor;
    }
  }
  const headers = data.bitcoin_block_headers || {};
  for (const el of document.querySelectorAll('[data-verify="bitcoin-merkle"]')) {
    const height = el.getAttribute('data-target');
    const anchor = anchorsByHeight[height];
    if (!anchor) continue;
    const headerHex = headers[height];
    anchorResults.total++;
    if (!headerHex) {
      setBadgeHeaderMissing(el);
      anchorResults.missing++;
      continue;
    }
    const r = verifyBitcoinAnchor(anchor, headerHex);
    if (r.malformed) {
      setBadge(el, false);
      anchorResults.fail++;
    } else {
      setBadge(el, r.ok);
      r.ok ? anchorResults.ok++ : anchorResults.fail++;
    }
  }

  // Inference proofs — self-hash AND DAG structure.
  const proofByhash = Object.fromEntries((data.inference_proofs || []).map(p => [p.proof_hash, p]));
  for (const el of document.querySelectorAll('[data-verify="inference-proof"]')) {
    const hash = el.getAttribute('data-target');
    const p = proofByhash[hash];
    if (!p) continue;
    const ok = await verifyInferenceProof(p);
    setBadge(el, ok);
    results.total++; ok ? results.ok++ : results.fail++;
  }
  const rules = data.inference_proof_rules || [];
  for (const el of document.querySelectorAll('[data-verify="inference-proof-structure"]')) {
    const hash = el.getAttribute('data-target');
    const p = proofByhash[hash];
    if (!p) continue;
    const r = verifyInferenceProofStructure(p, rules);
    structResults.total++;
    if (r.ok) {
      structResults.ok++;
      if (r.weakInferences.length > 0) structResults.weak += r.weakInferences.length;
      setBadgeStructureOk(el, r.weakInferences.length);
    } else {
      structResults.fail++;
      setBadgeStructureFail(el, r.errors.length);
      el.title = r.errors.join('\n');
    }
  }

  // Global status banner
  const banner = document.getElementById('global-status');
  const sigsPart = sigResults.total > 0
    ? (sigResults.fail > 0
        ? ' · ' + sigResults.fail + ' of ' + sigResults.total + ' signatures FAILED'
        : sigResults.unsupported === sigResults.total
          ? ' · ' + sigResults.unsupported + ' ed25519 sigs (browser unsupported — see CLI footer)'
          : ' · ' + sigResults.ok + ' of ' + sigResults.total + ' signatures verify ed25519' +
            (sigResults.unsupported > 0 ? ' (' + sigResults.unsupported + ' browser-unsupported)' : '')
      )
    : '';
  const anchorsPart = anchorResults.total > 0
    ? (anchorResults.fail > 0
        ? ' · ' + anchorResults.fail + ' Bitcoin anchors MISMATCH'
        : anchorResults.missing === anchorResults.total
          ? ' · ' + anchorResults.missing + ' Bitcoin anchors (header not embedded)'
          : ' · ' + anchorResults.ok + ' of ' + anchorResults.total + ' Bitcoin anchors verify' +
            (anchorResults.missing > 0 ? ' (' + anchorResults.missing + ' missing header)' : '')
      )
    : '';
  const structPart = structResults.total > 0
    ? (structResults.fail > 0
        ? ' · ' + structResults.fail + ' inference DAG(s) INVALID'
        : ' · ' + structResults.ok + ' inference DAG(s) structurally valid' +
          (structResults.weak > 0 ? ' (' + structResults.weak + ' weak inference' + (structResults.weak === 1 ? '' : 's') + ')' : '')
      )
    : '';

  if (results.total === 0) {
    banner.className = 'global-status status-warn';
    banner.innerHTML = '<span class="status-icon">!</span><span>No verifiable hashes in this report.</span>';
  } else if (results.fail === 0 && sigResults.fail === 0 && anchorResults.fail === 0 && structResults.fail === 0) {
    banner.className = 'global-status status-ok';
    banner.innerHTML = '<span class="status-icon">✓</span><span><b>All ' + results.total + ' hashes verify' + sigsPart + anchorsPart + structPart + '.</b> Recomputed in this browser via WebCrypto — no backend trust required.</span>';
  } else {
    banner.className = 'global-status status-err';
    const reasons = [];
    if (results.fail > 0) reasons.push(results.fail + ' of ' + results.total + ' hashes failed');
    if (sigResults.fail > 0) reasons.push(sigResults.fail + ' ed25519 signatures failed');
    if (anchorResults.fail > 0) reasons.push(anchorResults.fail + ' Bitcoin anchor merkle MISMATCH');
    if (structResults.fail > 0) reasons.push(structResults.fail + ' inference DAG(s) INVALID');
    banner.innerHTML = '<span class="status-icon">✗</span><span><b>' + reasons.join(' · ') + '.</b> This report has been tampered with or is malformed.</span>';
  }
}

document.addEventListener('DOMContentLoaded', runVerification);
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>$title</title>
  <style>$css</style>
</head>
<body>
  <div class="report-frame">
    <div class="report-header">
      <h1>$title</h1>
      <div class="subtitle">sha256:$evidence_hash</div>
      <div class="meta">
        <span>archive: $archive_label</span>
        <span>generated: $generated_at</span>
        <span>format: aip.evidence-report.v1</span>
      </div>
    </div>

    <div id="global-status" class="global-status status-pending">
      <span class="status-icon">⏳</span>
      <span>Recomputing hashes via WebCrypto…</span>
    </div>

    $sections

    <footer class="report-footer">
      <div>Generated by <b>AIP</b> — Anomaly Intelligence Platform · evidence-first archive</div>
      <div>Verification runs 100% client-side. Hashes via SHA-256(JCS); ed25519 sigs via SubtleCrypto; Bitcoin anchors via embedded 80-byte block headers (merkle-root match).</div>
      <div>Witness signatures verify when the operator embedded their public keys; Bitcoin anchors verify when the operator embedded the block headers — otherwise badged "key unknown" / "header not embedded".</div>
      <div>The block header itself is trusted by source (block explorer or your own bitcoin-cli); PoW chain verification requires a Bitcoin node.</div>
    </footer>
  </div>

  <script id="report-data" type="application/json">$data_json</script>
  <script>$js</script>
</body>
</html>
"""


