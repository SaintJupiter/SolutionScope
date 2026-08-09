---
name: solutionscope
description: Prepare, validate, assemble, and report a traceable offline review workflow for permitted technical Markdown. Use when requirements, capabilities, gaps, conflicts, lifecycle states, PoC choices, or acceptance questions must stay bound to exact source anchors and when model outputs must be imported without calling an external model.
---

# SolutionScope v1.5 (current)

Use `scripts/solutionscope_workflow.py`. Read
`references/contract-and-boundaries.md` before changing schemas, lifecycle rules,
or claim boundaries.

1. Choose a reviewed workflow configuration. Start with
   `references/default-workflow.json`; copy and edit it for a new task rather
   than changing Python. Keep questions, groups, lifecycle phrases, and focus
   terms in configuration.
2. Run `prepare` to import permitted Markdown and create a ledger request,
   output schemas, fixed questions, and an auditable run record. This command
   never calls a model.
3. Generate the ledger in an isolated model context using only the request
   package. Run `advance` to register the immutable raw ledger, validate JSON
   Schema and exact anchors, and create grouped fragment requests.
4. Generate each fragment using only its request package. Run `complete` to
   register raw fragments, validate capability IDs and instruction coverage,
   inject ledger states and anchors deterministically, and write JSON and
   Markdown reports. A successful final structural gate also writes
   `final/ui_review_payload.json`, a deterministic browser view model for the
   local review workbench. It does not alter or replace `review_draft.json`.
5. When compatible raw outputs already exist, use `run-offline` to execute the
   same prepare, register, validate, assemble, and report path in one command.
6. Treat structural passes and deterministic source-risk flags as review
   controls, not accuracy, expert correctness, generalization, or business
   impact. Retain conflicts and unresolved questions for a person. Read the
   final `review_gate`: `blocked_pending_human_review` means the artifact may be
   inspected but must not be treated as released or approved. A zero process
   exit code means artifact generation succeeded, not that the human gate passed.
7. To review interactively, serve `prototype/review-decision-v2/` over local
   HTTP and import `final/ui_review_payload.json`. The page stores the imported
   payload only in the current browser session, does not call a model, and does
   not upload the file. Do not publish a payload containing restricted source
   excerpts.

## Commands

```bash
python3 scripts/solutionscope_workflow.py prepare \
  --input <permitted.md> --config references/default-workflow.json \
  --run-dir <new-run-dir> --run-id <id>

python3 scripts/solutionscope_workflow.py advance \
  --run-dir <run-dir> --ledger-output <ledger.json>

python3 scripts/solutionscope_workflow.py complete \
  --run-dir <run-dir> \
  --fragment-output G1=<g1.json> --fragment-output G2=<g2.json>

python3 scripts/solutionscope_workflow.py run-offline \
  --input <permitted.md> --config <config.json> \
  --run-dir <new-run-dir> --run-id <id> \
  --ledger-output <ledger.json> \
  --fragment-output G1=<g1.json> --fragment-output G2=<g2.json>
```

Pass `--call-metadata <json>` when provider duration, token, or cost data is
available. Missing values remain the literal string `unavailable`; never infer
them. Do not edit raw model artifacts after registration.
