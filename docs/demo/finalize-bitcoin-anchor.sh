#!/usr/bin/env bash
# Finalize the Bitcoin anchor of the demo report.
#
# Run from the repo root, *at least 1h after* `aip notarize submit` was
# executed on docs/demo/demo_archive/transparency/manifest-000000.json:
#
#     bash docs/demo/finalize-bitcoin-anchor.sh
#
# What this does:
#
#   1. `aip notarize upgrade` — asks each OTS calendar for the upgraded
#      proof. After the next Bitcoin block batch lands (typically 1–2h
#      after submit), the proof carries a real BitcoinBlockHeader
#      attestation with the block height and the merkle root.
#   2. `aip notarize verify` — confirms the proof is well-formed and
#      enumerates the Bitcoin claims.
#   3. `aip notarize fetch-header --verify-against` — pulls the actual
#      block header from mempool.space + blockstream.info (must agree),
#      cross-checks the extracted merkle root against the OTS claim,
#      and emits the 160-char hex ready to embed in the report.
#   4. Regenerates `demo-report.html` with `--bitcoin-header HEIGHT:HEX`
#      so the receptor's browser verifies the anchor client-side.
#
# Exit codes:
#   0 — anchor finalized and embedded.
#   2 — still pending (try again in ~30 min).
#   1 — any other failure (network, malformed proof, header mismatch).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCHIVE="${REPO_ROOT}/docs/demo/demo_archive"
MANIFEST="${ARCHIVE}/transparency/manifest-000000.json"
OTS_FILE="${MANIFEST}.ots"
REPORT="${REPO_ROOT}/docs/demo/demo-report.html"
EVIDENCE_HASH="65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1"

if   [ -x "${REPO_ROOT}/.venv/Scripts/aip.exe" ]; then
  AIP="${REPO_ROOT}/.venv/Scripts/aip.exe"
  PY="${REPO_ROOT}/.venv/Scripts/python.exe"
elif [ -x "${REPO_ROOT}/.venv/bin/aip" ]; then
  AIP="${REPO_ROOT}/.venv/bin/aip"
  PY="${REPO_ROOT}/.venv/bin/python"
else
  AIP="aip"
  # Resolve a usable python. python3 is preferred (POSIX); 'python' may be
  # a Microsoft Store stub on Windows that exits with usage info.
  if command -v python3 >/dev/null 2>&1; then PY=python3
  else PY=python
  fi
fi

if [ ! -f "${OTS_FILE}" ]; then
  echo "✗ No .ots file at ${OTS_FILE}" >&2
  echo "  Run 'aip notarize submit ${MANIFEST}' first, then wait ≥1h." >&2
  exit 1
fi

# Verify the python launcher works before relying on it inside $(...)
# (set -e doesn't catch failures inside command substitution).
if ! "${PY}" -c "import json" >/dev/null 2>&1; then
  echo "✗ Python launcher '${PY}' is not usable." >&2
  echo "  Activate the AIP venv or set PY=... to a working python." >&2
  exit 1
fi

# Cross-platform tmp file. git-bash on Windows mangles bare /tmp paths
# when passed to native Windows executables (the .venv python.exe sees
# the literal string), so we use mktemp which yields a path the host OS
# accepts natively.
TMPDIR_RUN="$(mktemp -d)"
trap "rm -rf '${TMPDIR_RUN}'" EXIT
UPGRADE_JSON_PATH="${TMPDIR_RUN}/aip-upgrade.json"

echo "▶ Upgrading OTS proof against calendars"
"${AIP}" notarize upgrade "${OTS_FILE}" > "${UPGRADE_JSON_PATH}"
cat "${UPGRADE_JSON_PATH}"

STILL_PENDING=$("${PY}" -c "import json,sys; print(json.load(open(sys.argv[1]))['still_pending'])" "${UPGRADE_JSON_PATH}")
if [ "${STILL_PENDING}" != "0" ]; then
  echo
  echo "⚠ ${STILL_PENDING} calendars still pending. Bitcoin has not processed"
  echo "  the OTS batch for our submit yet. Try again in ~30 minutes."
  exit 2
fi

echo
echo "▶ Verifying OTS proof (offline)"
VERIFY_JSON_PATH="${TMPDIR_RUN}/aip-verify.json"
"${AIP}" notarize verify "${MANIFEST}" "${OTS_FILE}" --json > "${VERIFY_JSON_PATH}"
cat "${VERIFY_JSON_PATH}"

# Extract the first claimed block height. If multiple calendars batched into
# the same block, they all carry the same height; we use the first.
HEIGHT=$("${PY}" -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['bitcoin_claims'][0]['height'] if d.get('bitcoin_claims') else '')" "${VERIFY_JSON_PATH}")

if [ -z "${HEIGHT}" ] || [ "${HEIGHT}" = "None" ]; then
  echo "✗ OTS proof has no Bitcoin claim yet. Re-run later." >&2
  exit 2
fi

echo
echo "▶ Fetching block ${HEIGHT} header from mempool.space + blockstream.info"
FETCH_JSON_PATH="${TMPDIR_RUN}/aip-fetch.json"
"${AIP}" notarize fetch-header "${HEIGHT}" --verify-against "${OTS_FILE}" > "${FETCH_JSON_PATH}"
cat "${FETCH_JSON_PATH}"
HEADER_HEX=$("${PY}" -c "import json,sys; print(json.load(open(sys.argv[1]))['header_hex'])" "${FETCH_JSON_PATH}")

echo
echo "▶ Regenerating demo-report.html with embedded Bitcoin header"
"${AIP}" evidence report \
  --archive-root "${ARCHIVE}" \
  --out "${REPORT}" \
  --title "AIP Demo Report — Twining Memo 1947 (Bitcoin-anchored)" \
  --bitcoin-header "${HEIGHT}:${HEADER_HEX}" \
  "${EVIDENCE_HASH}" >/dev/null

# Mirror the freshly regenerated report into web/public/ so the React
# landing keeps pointing at the latest version.
WEB_PUBLIC="${REPO_ROOT}/web/public"
if [ -d "${WEB_PUBLIC}" ]; then
  cp "${REPORT}" "${WEB_PUBLIC}/demo-report.html"
fi

echo
echo "✓ Bitcoin anchor finalized."
echo "    block height:  ${HEIGHT}"
echo "    report:        ${REPORT}"
echo
echo "Open the report in a browser. The 'Bitcoin anchors' badge in the"
echo "Coverage manifests section should now show 'verified' instead of"
echo "'header not embedded'."
