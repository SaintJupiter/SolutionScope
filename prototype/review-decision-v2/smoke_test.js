"use strict";

const fs = require("fs");
const path = require("path");
const fixture = require("./fixture.js");
const payloadApi = require("./payload.js");
const store = require("./state.js");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(fixture.fixtureType === "sanitized_synthetic_public_demo", "fixture must be explicitly synthetic/public demo data");
assert(payloadApi.validate(fixture), "fixture must satisfy the import payload contract");
assert(fixture.items.length === 6, "fixture must contain six review items");
assert(new Set(fixture.items.map((item) => item.id)).size === fixture.items.length, "fixture IDs must be unique");

const requiredFields = [
  "requirement_object",
  "preconditions",
  "required_action",
  "expected_result",
  "quantitative_target",
  "test_or_acceptance_method",
  "clarification_questions"
];

fixture.items.forEach((item) => {
  assert(item.evidence && item.evidence.sourceId && item.evidence.locator && item.evidence.excerpt, `${item.id}: evidence is incomplete`);
  assert(item.evidence.status === "bound", `${item.id}: synthetic evidence must be explicitly bound`);
  assert(item.evidence.origin.includes("合成"), `${item.id}: evidence origin must disclose synthetic status`);
  requiredFields.forEach((field) => assert(Object.hasOwn(item.aiDraft, field), `${item.id}: missing contract field ${field}`));
});

let state = store.createInitialState(fixture);
let summary = store.summarize(fixture, state);
let gates = store.computeGates(fixture, state);

assert(summary.reviewed === 0 && summary.total === 6, "initial review summary is wrong");
assert(summary.suspiciousComplete === 3, "initial fixture should expose three high-risk complete items");
assert(gates.structure.status === "pass", "structure gate should pass for the fixture contract");
assert(gates.evidence.status === "pending" && gates.semantics.status === "pending", "human-dependent gates should initially be pending");

fixture.items.forEach((item) => {
  const review = state.reviews[item.id];
  review.status = item.suggestedMissingFields.length ? "modified" : "accepted";
  if (item.suggestedMissingFields.length) {
    review.completeness = "partial";
    review.missingFields = [...item.suggestedMissingFields];
  }
  review.updatedAt = new Date().toISOString();
});

summary = store.summarize(fixture, state);
gates = store.computeGates(fixture, state);
assert(summary.reviewed === 6 && summary.suspiciousComplete === 0, "review corrections should clear suspicious complete items");
assert(gates.evidence.status === "pass", "evidence gate should pass after all fixture items are reviewed");
assert(gates.semantics.status === "blocked", "non-complete human findings should block the semantic gate");

fixture.items.forEach((item) => {
  const review = state.reviews[item.id];
  review.status = item.suggestedMissingFields.length ? "modified" : "accepted";
  review.completeness = "complete";
  review.missingFields = [];
  review.clarificationQuestions = [];
  review.note = item.suggestedMissingFields.length ? "已回到原文核对并确认不影响本条结论。" : "";
});
summary = store.summarize(fixture, state);
gates = store.computeGates(fixture, state);
assert(summary.unresolved === 0 && summary.suspiciousComplete === 0, "explicit resolutions should clear semantic risks");
assert(gates.semantics.status === "pass", "semantic pass must be reachable after explicit human resolution");

assert(!store.reviewHasMaterialChange(fixture.items[1], store.defaultReview ? store.defaultReview(fixture.items[1]) : {
  completeness: fixture.items[1].aiCompleteness,
  missingFields: [],
  clarificationQuestions: fixture.items[1].aiDraft.clarification_questions,
  note: ""
}), "unchanged review must not count as a modification");
assert(!store.validateDecision(gates, "release_to_human_evaluation", "", "进入人工评测").ok, "decision note must be required");
assert(store.validateDecision(gates, "release_to_human_evaluation", "已记录评审依据。", "进入人工评测").ok, "complete decision should pass validation");

state.decision.choice = "block";
state.decision.note = "Fixture smoke test decision";
state.decision.updatedAt = new Date().toISOString();
state.decision.reviewFingerprint = store.reviewFingerprint(state);
assert(store.decisionIsCurrent(state), "saved decision must match the reviewed state");
state.reviews[fixture.items[0].id].note += "changed";
assert(!store.decisionIsCurrent(state), "review changes must invalidate the saved decision");
state.reviews[fixture.items[0].id].note = state.reviews[fixture.items[0].id].note.replace("changed", "");
const reviewExport = store.publicReviewExport(fixture, state);
const decisionExport = store.decisionExport(fixture, state);
assert(reviewExport.claimBoundary.includes("no accuracy"), "review export must retain claim boundary");
assert(decisionExport.manualDecision.choice === "block", "decision export must include manual decision");
assert(decisionExport.historicalDevelopmentObservation.b1OverCompleteRiskCount === 18, "historical aggregate boundary is missing");

const base = __dirname;
const index = fs.readFileSync(path.join(base, "index.html"), "utf8");
const decision = fs.readFileSync(path.join(base, "decision.html"), "utf8");
for (const html of [index, decision]) {
  assert(html.includes("fixture.js") && html.includes("payload.js") && html.includes("state.js") && html.includes("app.js"), "HTML must load fixture, payload, state and app scripts");
}

const imported = payloadApi.normalize({...fixture, fixtureId: "IMPORTED-001"});
assert(imported.fixtureId === "IMPORTED-001", "valid imported payload must normalize");
assert(store.createInitialState(imported).fixtureId === "IMPORTED-001", "imported payload must initialize isolated review state");
assert(store.computeGates({...imported, items: imported.items.map((item, index) => index === 0 ? {...item, evidence: {...item.evidence, status: "missing"}} : item)}, store.createInitialState(imported)).evidence.status === "blocked", "missing evidence status must block evidence gate");
let invalidRejected = false;
try {
  payloadApi.validate({...fixture, contract: "wrong"});
} catch (error) {
  invalidRejected = String(error.message).includes("contract");
}
assert(invalidRejected, "invalid payload contract must be rejected");

console.log("SolutionScope review-decision-v2 smoke test: PASS");
