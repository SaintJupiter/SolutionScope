---
name: solutionscope-v2-2
description: Source-bound requirements coverage, deterministic metric consistency, acceptance-readiness, and requirement-change impact workflow for paginated technical documents. Use when Codex must compare requirements against a proposed solution and verification plan, normalize units and verify quantitative commitments, produce an auditable requirement-to-solution-to-test matrix, preserve lifecycle state, trace requirement changes into re-review work, and block unsupported release decisions instead of answering like a normal RAG system.
---

# SolutionScope v2.2

Read [references/coverage-model.md](references/coverage-model.md) before changing statuses, release gates, or evidence rules.

## Workflow

1. Prepare three paginated Markdown inputs with `scripts/coverage_workflow.py prepare`: requirements, solution response, and verification plan. Declare `--review-stage proposal_review` or `--review-stage acceptance_review`.
2. Send only the generated requirement-atomization request and schema to a model. The model decomposes source requirements; it does not assess the solution.
3. Register the immutable atomization output with `register-requirements`. Hybrid retrieval combines lexical relevance, exact metrics, lifecycle signals, phrase overlap, and adjacent context while keeping solution and verification evidence separate.
4. Send only the generated coverage request and schema to a model. It must judge every action, condition, quantitative criterion, verification method, and acceptance criterion using the supplied role-specific evidence. For quantitative components it must copy the actually observed metric, operator, threshold, and unit instead of repeating the expected requirement.
5. Run `complete`. The deterministic gate normalizes supported units, compares threshold strength, checks lifecycle state, and derives aggregate coverage and release decisions. A model-level `covered` judgement cannot override a weaker numeric commitment or incompatible unit.
6. When requirements change, use `prepare-change-impact` and `complete-change-impact` to align old/new atoms and generate a solution/test re-review worklist. A changed obligation automatically holds release until its impact is confirmed.

## Fair comparison

Use `prepare-baseline` to generate a one-pass direct-RAG comparator over the same three source registries. Freeze the documents, questions, model, and scoring rules before running either group. Compare atomic-requirement recall, unsupported pass rate, verification-readiness agreement, reviewer edits, and review time separately; never treat citation count as end-to-end quality.

## Boundaries

- Treat retrieval as candidate discovery, not the final product decision.
- Bind every source fact to an immutable evidence ID and locator. Never invent, repair, or silently rebind model citations.
- Keep requirements, solution claims, and verification evidence separate. A requirement source cannot prove that a proposed solution implements it.
- Preserve the lifecycle state of solution claims. In `acceptance_review`, planned, candidate, or unknown claims cannot satisfy a current-capability gate.
- Treat numeric commitments as data, not prose. For supported units, normalize values before comparing them; for unknown or incompatible units, block the decision instead of guessing.
- A solution or verification criterion must be at least as strong as the requirement. A cited but weaker value is an invariant failure, not partial evidence of compliance.
- Mark `full` coverage only when every required solution component is supported. Mark verification `executable` only when method, acceptance criterion, and applicable test conditions are all supported.
- Block release for missing solution response, missing verification, source conflict, or unverifiable acceptance. Route ambiguity and partial coverage to human review.
- Preserve raw model outputs and derived artifacts separately.
- A structural pass, exact citation, or complete matrix is not expert approval, semantic correctness, production readiness, or generalization.

## Commands

Run `python3 scripts/coverage_workflow.py --help` for full arguments. Use `self-test` after any contract or gate change.
