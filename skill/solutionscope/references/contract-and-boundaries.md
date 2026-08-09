# Contract and boundaries

## Artifact roles

- The imported Markdown is the only source text.
- The workflow configuration is the only source of questions, groups,
  lifecycle phrases, focus terms, and required instruction components.
- The capability ledger is the only generated source of capability IDs and
  declared lifecycle states.
- Fragment outputs may select ledger capability IDs and write judgments, gaps,
  assumptions, recommendations, and conflicts. They must not create source
  locators or lifecycle states.
- The assembler injects ledger states and exact locators deterministically.
- Raw model outputs are immutable after registration.

## Gates

JSON Schema failures, invalid source anchors, duplicate IDs, unknown capability
references, missing fragment groups, and injection mismatches are structural
failures. Lifecycle promotion, unresolved source drift, missing instruction
components, or lost conflicts are deterministic source-risk findings that
require human review.

The final review artifact must carry a top-level `review_gate`. Any retained
deterministic source risk sets it to `blocked_pending_human_review`; downstream
consumers must not infer approval from a zero process exit code. Exit code zero
only means the workflow produced an auditable artifact. The source configuration
byte hash and the normalized runtime configuration hash are recorded separately.

Generated JSON Schema files are validated by the bundled deterministic Schema
subset implementation. Supported keywords are `$ref`, `$defs`, `type`,
`required`, `properties`, `additionalProperties`, `items`, `enum`, `const`,
`minItems`, `maxItems`, `uniqueItems`, `minLength`, and `pattern`. Schemas in
this Skill must stay within that declared subset.

## Claim boundary

A structural pass means the artifact is parseable, source-bound, and internally
consistent with the declared contract. A source-risk count is a deterministic
review signal. Neither establishes expert correctness, accuracy, generalization,
production readiness, user value, or ROI. Preserve `unavailable` for provider
telemetry that was not supplied.
