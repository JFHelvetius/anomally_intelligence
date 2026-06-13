# AIP JSON Schemas

Machine-readable contracts for the JSON artifacts AIP emits and consumes.
These schemas are the public interop surface: an external operator who
wants to produce an artifact that AIP accepts, or a third-party
verifier that wants to validate one without depending on the AIP CLI,
reads these files.

The schemas are written in **JSON Schema 2020-12**. They are normative
together with the corresponding ADRs — if a schema and an ADR disagree,
the ADR wins and the schema is a bug.

## Catalog

| File                                                                                       | Subject                                          | Canonical implementation                                                                          | Related ADRs    |
|--------------------------------------------------------------------------------------------|--------------------------------------------------|---------------------------------------------------------------------------------------------------|-----------------|
| [`audit-entry.v1.schema.json`](audit-entry.v1.schema.json)                                 | One line of the append-only audit log            | [`aip/audit/log.py`](../../src/aip/audit/log.py)                                                  | ADR-0019        |
| [`capture-certificate.v1.schema.json`](capture-certificate.v1.schema.json)                 | Operator-signed in-field capture declaration     | [`aip/archive.py`](../../src/aip/archive.py) (capture cert helpers)                               | Phase 2         |
| [`inference-proof.v1.schema.json`](inference-proof.v1.schema.json)                         | Machine-checkable reasoning DAG                  | [`aip/justification/logic/models.py`](../../src/aip/justification/logic/models.py)                | ADR-0040        |
| [`key-declaration.v1.schema.json`](key-declaration.v1.schema.json)                         | Operator + witness key external references       | [`aip/transparency/key_declaration.py`](../../src/aip/transparency/key_declaration.py)            | ADR-0043        |
| [`transparency-manifest.v1.schema.json`](transparency-manifest.v1.schema.json)             | Signed transparency log entry                    | [`aip/transparency/models.py`](../../src/aip/transparency/models.py)                              | ADR-0019, Phase 1A |
| [`witness-attestation.v1.schema.json`](witness-attestation.v1.schema.json)                 | Third-party witness signature over a manifest    | [`aip/transparency/witness/models.py`](../../src/aip/transparency/witness/models.py)              | Door #3         |

Remaining JSON artifact (operator attestation, ADR-0041) is not yet
schemafied here because its wire format intersects the OpenTimestamps
proof structure and a tight schema would duplicate the validation
already covered by the canonical dataclass + signed dataclass tests. It
can be added when external interop demand emerges; the pattern is the
same.

## Usage

### From any language with a JSON Schema 2020-12 validator

Validators that support Draft 2020-12 are available for most languages
(Python `jsonschema`, JavaScript `ajv`, Go `santhosh-tekuri/jsonschema`,
Rust `jsonschema`, etc.). Example with Python:

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path("docs/schemas/key-declaration.v1.schema.json").read_text())
validator = Draft202012Validator(schema)

declaration = json.loads(Path("docs/demo/demo_archive/transparency/key-declaration.json").read_text())
errors = sorted(validator.iter_errors(declaration), key=lambda e: e.path)
for err in errors:
    print(f"{list(err.path)}: {err.message}")
```

### Pin a specific schema URL

Each schema declares a stable `$id`. External producers can hard-pin to
that URI for forward compatibility:

```json
{
  "$schema": "https://aip.example/schemas/key-declaration.v1.schema.json",
  "declaration_type": "aip.transparency.key-declaration.v1",
  ...
}
```

The `$id` is currently `https://aip.example/...` because AIP does not
publish the schemas at a stable URL yet. If/when it does, update the
`$id` fields and document the migration here.

## What the schemas DO NOT enforce

Some invariants live in the canonical implementation but cannot be
expressed in JSON Schema 2020-12 without extensions:

- **Inference proofs**: schema enforces field shape, ID syntax, rule
  vocabulary, premise kinds, and arity *lower bound* via `minItems: 1`.
  It does NOT enforce per-rule arity (e.g. modus_ponens needing exactly
  2 inputs), no-cycles in the DAG, reachability of the conclusion from
  the premises, or the requirement that `inferred_by` round-trips
  correctly between `derived_claims` and `inferences`. Those are
  semantic checks done by `aip/justification/logic/verifier.py` and its
  TypeScript mirror.
- **Audit log**: schema validates a single entry. Chain linkage (entry
  N's `prev_hash` equals entry N-1's `entry_hash`) is a cross-entry
  invariant validated by `aip/audit/log.py` and the client-side
  verifier in `web/src/lib/auditChain.ts`.
- **Key declaration**: schema does not check that declared witness
  fingerprints have a corresponding `.pem` file on disk; that
  consistency check lives in `aip/transparency/key_declaration.py::check_consistency`.

Schema validation is the *first* filter. The reference verifiers in the
canonical implementation are the authoritative ones.

## Schema versioning

Each schema's filename and `$id` carry a `.v1` segment. Backwards-
incompatible changes (renamed fields, narrowed types, removed enum
values) require a new `.v2` schema file alongside the v1. The
corresponding `aip.*.v1` discriminator inside the document
(`declaration_type`, `proof_type`, etc.) refuses to accept v2 documents
under v1 readers. This pattern matches the rest of AIP (ADR-0031
§reproducibilidad).

Adding a new optional field is backwards-compatible and can be done in
place; document the change in the schema's description and bump the
canonical implementation accordingly.

## Sanity tests

`tests/unit/schemas/test_json_schema_fixtures.py` asserts that
representative fixtures in the repo validate against their schemas, and
that the schemas themselves are valid Draft 2020-12 metaschemas. If you
edit a schema, the test suite catches accidental drift between the
schema and the canonical implementation.
