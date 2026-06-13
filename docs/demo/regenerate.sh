#!/usr/bin/env bash
# Regenerate the AIP demo archive + standalone report from scratch.
#
# Run from the repo root:
#   bash docs/demo/regenerate.sh
#
# The script is fully deterministic in shape (same archive layout, same
# audit-log structure, same report sections) but NOT bit-for-bit
# reproducible because:
#   - keys are generated fresh each run (ed25519, random)
#   - signed_at + ingested_at use the wall clock
#   - manifest_hash depends on both of the above
#
# That is intentional: the demo proves the *workflow* end-to-end, not a
# canonical archive. The point of the report is that anyone can verify
# the chain in a browser without trusting the operator who produced it.

set -euo pipefail

# ── paths ─────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEMO_DIR="${REPO_ROOT}/docs/demo"
ARCHIVE="${DEMO_DIR}/demo_archive"
REPORT="${DEMO_DIR}/demo-report.html"
PDF_FIXTURE="${REPO_ROOT}/tests/data/twining-memo-1947-09-23.pdf"

# ── private key lives OUTSIDE the repo so it can never be committed ──
KEYDIR="$(mktemp -d -t aip-demo-keys-XXXX)"
PRIV="${KEYDIR}/private.pem"
PUB="${KEYDIR}/public.pem"
trap "rm -rf '${KEYDIR}'" EXIT

# ── reset target ──────────────────────────────────────────────────────
rm -rf "${ARCHIVE}" "${REPORT}"

# Pick the aip CLI: prefer venv if present.
if   [ -x "${REPO_ROOT}/.venv/Scripts/aip.exe" ]; then AIP="${REPO_ROOT}/.venv/Scripts/aip.exe"
elif [ -x "${REPO_ROOT}/.venv/bin/aip"        ]; then AIP="${REPO_ROOT}/.venv/bin/aip"
else AIP="aip"
fi

echo "▶ Generating fresh ed25519 keypair (private key stays in ${KEYDIR})"
"${AIP}" attestation keygen --output-private "${PRIV}" --output-public "${PUB}" >/dev/null

echo "▶ Ingesting fixture (twining-memo-1947-09-23.pdf, 250022 bytes)"
"${AIP}" evidence ingest "${PDF_FIXTURE}" \
  --archive-root "${ARCHIVE}" \
  --source-id nara-twining-memo-1947 \
  --source-name "NARA — Twining Memo 1947-09-23" \
  --source-kind government_archive \
  --source-authority secondary \
  --source-jurisdiction US \
  --ingested-by "@aip-demo" >/dev/null

echo "▶ Publishing first transparency manifest"
"${AIP}" transparency publish \
  --archive-root "${ARCHIVE}" \
  --private-key "${PRIV}" \
  --operator-id aip-demo-operator >/dev/null

echo "▶ Installing public key into transparency/"
cp "${PUB}" "${ARCHIVE}/transparency/public-key.pem"

echo "▶ Initializing key declaration (ADR-0043) + 2 external references"
"${AIP}" transparency declare-key init \
  --archive-root "${ARCHIVE}" \
  --operator-id aip-demo-operator \
  --first-published-at 2026-06-10T00:00:00Z >/dev/null

"${AIP}" transparency declare-key add-reference \
  --archive-root "${ARCHIVE}" \
  --kind github_user_keys \
  --uri "https://github.com/JFHelvetius.keys" \
  --note "DEMO ONLY: the operator's GitHub SSH keys. Compare fingerprint via: ssh-keygen -lf" >/dev/null

"${AIP}" transparency declare-key add-reference \
  --archive-root "${ARCHIVE}" \
  --kind https_pem \
  --uri "https://raw.githubusercontent.com/JFHelvetius/aip/main/docs/demo/demo_archive/transparency/public-key.pem" \
  --note "DEMO ONLY: this URL is the same key shipped in the report; trivially circular so it does NOT close the trust loop alone. Use github_user_keys above for a real cross-check." >/dev/null

echo "▶ Submitting manifest to OpenTimestamps calendars (Bitcoin anchor starts ~1h clock)"
# Network required. If offline, skip — the demo still works without the
# OTS anchor, the report just won't have a Bitcoin layer.
if "${AIP}" notarize submit "${ARCHIVE}/transparency/manifest-000000.json" >/dev/null 2>&1; then
  echo "    OTS submit succeeded — run docs/demo/finalize-bitcoin-anchor.sh in ~1h"
else
  echo "    OTS submit failed (offline?) — skipping. The report will still be valid"
  echo "    minus the Bitcoin anchor layer."
fi

echo "▶ Generating standalone HTML report"
"${AIP}" evidence report \
  --archive-root "${ARCHIVE}" \
  --out "${REPORT}" \
  --title "AIP Demo Report — Twining Memo 1947" \
  65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1 >/dev/null

echo "▶ Verifying archive + transparency chain"
"${AIP}" archive verify --archive-root "${ARCHIVE}" >/dev/null
"${AIP}" transparency verify --chain --archive-root "${ARCHIVE}" --public-key "${PUB}" >/dev/null

# Mirror the demo report into web/public/ so the React landing page (About)
# can link to /demo-report.html via the dev/prod server. Pure copy; the
# canonical source remains docs/demo/.
WEB_PUBLIC="${REPO_ROOT}/web/public"
if [ -d "${WEB_PUBLIC}" ]; then
  cp "${REPORT}" "${WEB_PUBLIC}/demo-report.html"
fi

echo
echo "✓ Demo regenerated:"
echo "    archive:  ${ARCHIVE}"
echo "    report:   ${REPORT}"
echo "    pubkey:   ${ARCHIVE}/transparency/public-key.pem"
echo
echo "Open ${REPORT} in any modern browser. The page recomputes every"
echo "hash and signature client-side — no backend, no trust in the operator."
