# AIP Demo — End-to-End Verifiable Report

This directory contains a complete, self-contained AIP demonstration:
ingest a public-domain document, publish a transparency manifest, declare
external key references, and emit a standalone HTML report that any
recipient can verify in their browser without trusting the operator who
produced it.

Open [`demo-report.html`](demo-report.html) in any modern browser
(Chrome 137+, Firefox 130+, Safari 17+) to see the full verification.

---

## What's in here

```
docs/demo/
├── README.md                            (this file)
├── demo-report.html                     (open in browser → all checks recompute client-side)
├── regenerate.sh                        (bash script: rebuild everything from scratch)
├── finalize-bitcoin-anchor.sh           (≥1h after submit: upgrade OTS + embed block header)
└── demo_archive/                        (the AIP archive that backs the report)
    ├── audit.log
    ├── manifest.json
    ├── objects/                         (content-addressed blobs)
    ├── tables/                          (source/evidence/provenance JSON tables)
    └── transparency/
        ├── public-key.pem               (ed25519 SubjectPublicKeyInfo)
        ├── manifest-000000.json         (signed transparency manifest)
        ├── manifest-000000.json.ots     (OpenTimestamps proof — Bitcoin-anchored after ~1h)
        ├── latest.json
        └── key-declaration.json         (ADR-0043: external pubkey references)
```

No private key is committed. The keypair is generated inside `regenerate.sh`
in a temporary directory and discarded at the end of the run.

## What the demo proves

The recipient of `demo-report.html` can independently confirm, **offline,
in their browser**, every one of the following:

1. **Audit chain integrity** — each audit entry's hash is SHA-256(JCS(entry
   minus self)); each entry's `prev_hash` equals the previous entry's
   `entry_hash`. Tampering with any entry invalidates the chain.
2. **Manifest integrity** — the transparency manifest's `manifest_hash` is
   SHA-256(JCS(manifest minus self_hash + signature)). Tampering invalidates it.
3. **Manifest signature** — the manifest's ed25519 signature verifies
   against the embedded operator public key, AND the embedded key's
   SHA-256(DER SPKI) fingerprint matches the one inside the manifest.
4. **Inference DAG structure** (none in this demo — no inference proofs
   were produced — the verifier still loads and reports zero proofs).
5. **Trust footprint** — the report displays the operator's key fingerprint
   alongside the external references the operator declared, so the
   recipient can fetch the key from an independent source and compare.

## What the demo does NOT prove

Honesty matters more than completeness here. The report cannot prove:

- **The identity of the operator.** The operator declared two external
  references where their key is published. The recipient *must manually
  fetch the key from one of those sources and compare its SHA-256 DER SPKI
  fingerprint* against the one in the report. AIP does not do this
  comparison for the recipient.
- **Bitcoin anchoring is a two-stage process.** The `.ots` file shipped
  here contains *pending* attestations: the three public OpenTimestamps
  calendars accepted our submit, but the Bitcoin batch they participate
  in has not been processed yet. To finalize the anchor (~1–2 h after
  the original submit), run:

  ```bash
  bash docs/demo/finalize-bitcoin-anchor.sh
  ```

  That script asks each calendar for the upgraded proof, fetches the
  real block header from two independent block explorers, cross-checks
  that the OTS-claimed merkle root matches the header, and regenerates
  `demo-report.html` with `--bitcoin-header HEIGHT:HEX` embedded.
  Exit codes:
    - `0` — anchor finalized and embedded in the regenerated report.
    - `2` — still pending; try again in ~30 minutes.
    - `1` — network failure, header mismatch, or other hard error.
- **The truth or significance of the document's contents.** The Twining
  memo is a historical artifact; AIP guarantees its integrity since the
  moment it was ingested into this archive, nothing more. Authentication
  of the document predates AIP and is not in scope.

## How to verify this demo

### Step 1 — Open the report

Open [`demo-report.html`](demo-report.html) in a modern browser. The
header banner shows a global verification state:

> ✓ All N hashes verify · M of M signatures verify ed25519. Recomputed in
> this browser via WebCrypto — no backend trust required.

If anything in the demo archive has been tampered with, the banner will
turn red and name the failing check.

### Step 2 — Compare the operator pubkey against an external source

This is the only step you cannot do inside the browser. The report's
"Signer trust footprint" section lists external references for the
operator's key. To close the trust loop, pick one:

- **`github_user_keys`**: visit `https://github.com/JFHelvetius.keys`,
  paste each line into `ssh-keygen -lf /dev/stdin`, find the ed25519 entry,
  and compare its base64 → SHA-256 against the operator fingerprint shown
  in the report's "Signer trust footprint" section (a 64-char hex string
  labelled "Fingerprint (SHA-256 of DER SPKI)").
- **`https_pem`**: visit the URL listed; the file is the same PEM shipped
  in this repo. **This reference is trivially circular** — a hostile
  operator can publish anything on their own URL. It does NOT close the
  trust loop alone. Use the GitHub reference (or any independent channel)
  for a real cross-check.

### Step 3 — Optional CLI re-verification

If you have the AIP CLI installed:

```bash
# Recompute every hash, walk the audit chain, verify ed25519 signatures.
aip archive verify --archive-root docs/demo/demo_archive
aip transparency verify --chain \
    --archive-root docs/demo/demo_archive \
    --public-key docs/demo/demo_archive/transparency/public-key.pem
```

Both should print `ok: true` / `Archive integrity verified.`

### Step 4 — Regenerate from scratch

```bash
bash docs/demo/regenerate.sh
```

The script:

1. Generates a fresh ed25519 keypair in a temporary directory.
2. Ingests `tests/data/twining-memo-1947-09-23.pdf` into a new
   `docs/demo/demo_archive/`.
3. Publishes a signed transparency manifest.
4. Initializes the key declaration with two external references.
5. Submits the manifest to OpenTimestamps calendars (network required;
   skipped silently if offline).
6. Emits the standalone HTML report.
7. Verifies the archive and the chain.

The result is a freshly built demo whose archive **layout** matches what
ships in the repo (same files, same sections in the report) but whose
**bytes** differ because keys, timestamps, and signatures are regenerated.
That is by design: the demo proves the workflow is reproducible, not that
this specific archive is canonical.

### Step 5 — Finalize the Bitcoin anchor

After ~1–2 hours have passed since the original `aip notarize submit`
(or since you ran `regenerate.sh`):

```bash
bash docs/demo/finalize-bitcoin-anchor.sh
```

This upgrades the OTS proof to point at a concrete Bitcoin block, cross-
checks the merkle root against two independent block explorers, and
regenerates `demo-report.html` with the block header embedded. The
report's "Bitcoin anchors" badge then verifies client-side, completing
the trust chain from a single PDF blob to a Bitcoin block.

## Source document

`tests/data/twining-memo-1947-09-23.pdf` — Memorandum from Lt. Gen.
Nathan F. Twining, Air Force Commanding General, dated 1947-09-23, on
"Air Force concerning the AMC opinion on flying discs". Released by NARA;
public domain (US government work).

SHA-256: `65539d95ca5fe1a2270e7eeea3931cf9dc01055f6c27fafe94f627e6ebcfade1`
Size: 250,022 bytes

## What this is not

This demo is **not** a claim about UAP. AIP preserves and verifies
evidence; it makes no statement about the document's authenticity,
provenance prior to ingestion, or interpretation of its contents. Anyone
producing a report like this is asserting only "I ingested these exact
bytes at this time and nothing has been altered since" — not "this is
real" or "this is significant".
