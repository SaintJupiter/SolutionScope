# Semantic contract

The capability ledger is the only source of lifecycle state and evidence used
by downstream answers. Every entry must include:

- a stable `capability_id`;
- a normalized capability name and module;
- one lifecycle state;
- one or more exact source anchors;
- optional dependencies, metrics, acceptance method, and information gaps.

Allowed lifecycle states are `current`, `planned`, `candidate`, `normative`,
`unknown`, and `conflicted`.

Classify the proposition supported by the cited text. Do not infer lifecycle
state from an isolated modal word when the surrounding proposition says
something different. Use `conflicted` when the source describes the same
capability as both current and future or candidate. Preserve the conflict for
human review.

Fragment models may cite only known `capability_id` values. They must not emit
lifecycle states, page numbers, paragraph identifiers, or locator quotes.
Deterministic assembly injects these fields from the ledger so that the same
capability has the same state and evidence in every answer.

Structural and source-binding gates are diagnostics. They do not establish
semantic correctness, expert agreement, accuracy, or generalization.
