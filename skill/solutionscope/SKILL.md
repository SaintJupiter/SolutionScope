---
name: solutionscope
description: Extract capabilities, requirements, evidence, lifecycle states, gaps, and conflicts from permitted technical materials, then produce review-ready answers with deterministic source binding. Use for technical proposals, product specifications, acceptance documents, PoC planning, or other long-form materials where current, planned, candidate, normative, unknown, and conflicted statements must remain traceable across answers.
---

# SolutionScope

Use `scripts/ledger_constrained_workflow.py`. Read
`references/semantic-contract.md` before changing the output contract.

1. Confirm that the input document is permitted for local and model processing.
2. Initialize a new run with a Markdown document. Supply a custom questions JSON
   when the default review questions do not match the task.
3. Prepare the capability-ledger request. Send only that request to the selected
   model and save the raw JSON result at the declared output path.
4. Register and validate the ledger. Do not continue when the structural gate
   fails; keep lifecycle conflicts for human confirmation.
5. Prepare small question groups. The model may select only known
   `capability_id` values and must not generate source locators or lifecycle
   states.
6. Register and validate every group, then assemble the final review draft.
   The assembler injects exact evidence and lifecycle state from the ledger.
7. Run the final gate and export the review payload. Treat a structural pass as
   review readiness only, never as semantic correctness or expert approval.

Keep source documents and run artifacts out of public repositories by default.
Never use a reference answer, prior review, or historic model output during
generation unless the user explicitly requests an evaluation workflow.
