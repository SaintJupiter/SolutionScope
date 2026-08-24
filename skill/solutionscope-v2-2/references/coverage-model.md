# Coverage model v2.2

## Deterministic quantitative invariants

The model extracts the metric, operator, threshold, and unit actually present in solution and verification evidence. Deterministic code then checks each observed commitment against the atomic requirement.

- Supported time and distance units are normalized before comparison, such as `0.6 s = 600 ms` and `4 km = 4000 m`.
- For lower-bound requirements, an observed lower bound must be equal or stronger. For upper-bound requirements, an observed upper bound must be equal or tighter.
- Unknown units, incompatible metric names, missing observed values, or weaker thresholds are invariant failures.
- An invariant failure blocks release even when the model labels the component covered or supported.
- The failure code, component ID, human-readable explanation, and required recheck action remain in the final matrix and UI payload.

## Core distinction

Ordinary RAG answers what retrieved documents say. SolutionScope v2 decides whether a proposed solution and verification plan provide sufficient, traceable coverage for each source requirement.

The workflow adds three review objects that retrieval alone does not provide:

1. an atomic obligation with normative strength, lifecycle state, conditions, and criteria;
2. separate solution-response and verification-readiness judgements for every component;
3. a deterministic release gate and a requirement-change impact worklist.

Hybrid retrieval is still candidate discovery. Metric matching, phrase overlap, lifecycle terms, and adjacent context improve candidate quality but never decide coverage.

## Evidence roles

- `requirement`: authoritative requirement, constraint, condition, metric, or normative statement.
- `solution`: proposed or implemented capability that claims to satisfy a requirement.
- `verification`: test method, dataset, environment, threshold, repetition rule, or acceptance decision procedure.

Evidence is not interchangeable across roles.

## Review stage

- `proposal_review`: asks whether a proposed design responds to the requirements and provides a usable verification plan. Planned solution claims may contribute to design coverage.
- `acceptance_review`: asks whether current capability is ready for acceptance. Planned, candidate, or unknown claims cannot be treated as implemented coverage.

The same sentence can therefore receive a different gate outcome without changing its evidence.

## Requirement atom

Each atom contains one auditable obligation:

- object and required action;
- normative strength: `must`, `should`, `may`, or `informational`;
- lifecycle state: `current`, `planned`, `candidate`, or `unknown`;
- conditions and quantitative criteria;
- expected verification information;
- exact requirement evidence IDs;
- unresolved ambiguities.

Split compound clauses when their coverage can differ. Keep shared conditions on every affected atom.

## Coverage decisions

The model does not directly decide whether a requirement passes. It judges the smallest reviewable components; the deterministic gate derives aggregate status and release outcome.

### Component decisions

Solution evidence is checked separately against:

- the required action;
- every stated condition;
- every quantitative criterion.

Verification evidence is checked separately for:

- an executable method;
- an explicit acceptance criterion;
- coverage of the requirement's applicable conditions.

Each solution component is marked `covered`, `partial`, `absent`, `conflicting`, or `unverifiable`, carries a claim lifecycle state, and must cite role-correct evidence when it claims anything beyond `absent`.

### Solution coverage

- `full`: the supplied solution evidence addresses the complete atom.
- `partial`: some actions, conditions, or criteria are absent.
- `absent`: no supplied solution evidence addresses it.
- `conflicting`: the solution contradicts the requirement or itself.
- `unverifiable`: evidence is related but cannot support a dependable judgement.
- `not_applicable`: justified exclusion requiring a rationale and human review.

### Verification readiness

- `executable`: supported method and supported acceptance criterion are both present.
- `partial`: method or criterion exists, but not both or not all conditions are defined.
- `missing`: no usable verification evidence exists.
- `conflicting`: verification statements disagree.
- `not_applicable`: verification is not required and the exclusion is justified.

## Release gate

- `pass_with_evidence`: only for `full` + `executable`, without unresolved ambiguity.
- `block_missing_solution`: solution coverage is `absent`.
- `block_missing_verification`: verification is `missing`, or coverage is full but verification is not executable.
- `block_conflict`: any source-bound conflict affects the requirement.
- `human_review`: partial, unverifiable, not-applicable, or ambiguous cases.

The deterministic gate calculates these statuses from the component decisions. It rejects missing components, duplicate component IDs, cross-role citations, out-of-scope evidence, and inconsistent status/evidence combinations rather than asking the model to rewrite them.

## Evaluation

Compare against a simple RAG baseline on unseen documents. Report separately:

1. atomic critical-requirement recall;
2. solution-coverage classification agreement;
3. unsupported pass rate;
4. executable-verification classification agreement;
5. contradiction/gap detection recall;
6. reviewer edits and review time.

Do not describe retrieval recall as end-to-end correctness.

## Requirement changes

Align old and new requirement atoms by meaning. Classify each alignment as `unchanged`, `modified`, `added`, `removed`, `split`, or `merged`. Any type other than `unchanged` holds release and produces three explicit follow-up actions: recheck the solution response, recheck the verification plan, and obtain human confirmation. Prior evidence is carried only as review context, never as proof that the new requirement is covered.
