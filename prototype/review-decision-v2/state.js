(function attachState(root) {
  "use strict";

  const STORAGE_KEY = "solutionscope.reviewDecisionV2.v1";
  const WINDOW_NAME_PREFIX = "solutionscope.reviewDecisionV2.windowName:";
  const COMPLETENESS_VALUES = ["complete", "partial", "incomplete", "unknown"];
  const REVIEW_STATUSES = ["unreviewed", "accepted", "modified", "unable"];

  function copy(value) {
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function storageKey(fixtureId) {
    return `${STORAGE_KEY}:${fixtureId}`;
  }

  function defaultReview(item) {
    return {
      itemId: item.id,
      status: "unreviewed",
      completeness: item.aiCompleteness,
      missingFields: [],
      clarificationQuestions: copy(item.aiDraft.clarification_questions || []),
      note: "",
      updatedAt: null
    };
  }

  function createInitialState(fixture) {
    return {
      contract: "SolutionScope-review-decision-v2-local-state",
      fixtureId: fixture.fixtureId,
      reviews: Object.fromEntries(fixture.items.map((item) => [item.id, defaultReview(item)])),
      decision: {
        choice: null,
        note: "",
        nextAction: "修正完整性判定与缺口追问规则后，使用同一审核队列回归。",
        reviewFingerprint: null,
        updatedAt: null
      }
    };
  }

  function normalizeState(fixture, candidate) {
    const fresh = createInitialState(fixture);
    if (!candidate || candidate.fixtureId !== fixture.fixtureId) return fresh;

    fixture.items.forEach((item) => {
      const incoming = candidate.reviews && candidate.reviews[item.id];
      if (!incoming) return;
      const status = REVIEW_STATUSES.includes(incoming.status) ? incoming.status : "unreviewed";
      const completeness = COMPLETENESS_VALUES.includes(incoming.completeness)
        ? incoming.completeness
        : item.aiCompleteness;
      fresh.reviews[item.id] = {
        ...fresh.reviews[item.id],
        ...incoming,
        status,
        completeness,
        missingFields: Array.isArray(incoming.missingFields) ? incoming.missingFields : [],
        clarificationQuestions: Array.isArray(incoming.clarificationQuestions)
          ? incoming.clarificationQuestions
          : fresh.reviews[item.id].clarificationQuestions
      };
    });

    if (candidate.decision) fresh.decision = {...fresh.decision, ...candidate.decision};
    return fresh;
  }

  function loadState(fixture) {
    try {
      const raw = root.localStorage && root.localStorage.getItem(storageKey(fixture.fixtureId));
      if (raw) return normalizeState(fixture, JSON.parse(raw));
    } catch (_) {
      // `file://` localStorage behavior differs by browser. The same-tab
      // window.name fallback below keeps the two-page demo usable.
    }
    try {
      if (typeof root.name === "string" && root.name.startsWith(WINDOW_NAME_PREFIX)) {
        return normalizeState(fixture, JSON.parse(root.name.slice(WINDOW_NAME_PREFIX.length)));
      }
    } catch (_) {}
    return createInitialState(fixture);
  }

  function saveState(state) {
    const serialized = JSON.stringify(state);
    try {
      if (root.localStorage) root.localStorage.setItem(storageKey(state.fixtureId), serialized);
    } catch (_) {}
    try {
      if (typeof root.name === "string") root.name = `${WINDOW_NAME_PREFIX}${serialized}`;
    } catch (_) {}
  }

  function resetState(fixture) {
    try {
      if (root.localStorage) root.localStorage.removeItem(storageKey(fixture.fixtureId));
    } catch (_) {}
    try {
      if (typeof root.name === "string" && root.name.startsWith(WINDOW_NAME_PREFIX)) root.name = "";
    } catch (_) {}
    return createInitialState(fixture);
  }

  function summarize(fixture, state) {
    const reviews = fixture.items.map((item) => state.reviews[item.id]);
    const countBy = (key, value) => reviews.filter((review) => review[key] === value).length;
    const reviewed = reviews.filter((review) => review.status !== "unreviewed").length;
    const unable = countBy("status", "unable");
    const modified = countBy("status", "modified");
    const unresolved = reviews.filter((review) =>
      ["partial", "incomplete", "unknown"].includes(review.completeness)
      || review.missingFields.length > 0
      || review.clarificationQuestions.length > 0
    ).length;
    const suspiciousComplete = fixture.items.filter((item) => {
      const review = state.reviews[item.id];
      const explicitlyResolved = review.status === "modified"
        && review.note.trim().length > 0
        && review.missingFields.length === 0
        && review.clarificationQuestions.length === 0;
      return item.risk === "high"
        && item.suggestedMissingFields.length > 0
        && review.completeness === "complete"
        && !explicitlyResolved;
    }).length;

    return {
      total: reviews.length,
      reviewed,
      unreviewed: reviews.length - reviewed,
      accepted: countBy("status", "accepted"),
      modified,
      unable,
      complete: countBy("completeness", "complete"),
      partial: countBy("completeness", "partial"),
      incomplete: countBy("completeness", "incomplete"),
      unknown: countBy("completeness", "unknown"),
      unresolved,
      suspiciousComplete
    };
  }

  function reviewHasMaterialChange(item, review) {
    const originalQuestions = item.aiDraft.clarification_questions || [];
    return review.completeness !== item.aiCompleteness
      || review.missingFields.length > 0
      || JSON.stringify(review.clarificationQuestions) !== JSON.stringify(originalQuestions)
      || review.note.trim().length > 0;
  }

  function validateDecision(gates, choice, note, nextAction) {
    if (!["block", "release_to_human_evaluation"].includes(choice)) {
      return {ok: false, message: "请先选择阻断或有限放行。"};
    }
    if (!String(note || "").trim()) {
      return {ok: false, message: "请记录决策依据或残余风险。"};
    }
    if (!String(nextAction || "").trim()) {
      return {ok: false, message: "请记录下一步行动。"};
    }
    const blocked = Object.values(gates).some((gate) => gate.status === "blocked");
    if (blocked && choice === "release_to_human_evaluation" && String(note).trim().length < 8) {
      return {ok: false, message: "存在阻断门禁时，有限放行需写明具体例外理由。"};
    }
    return {ok: true, message: ""};
  }

  function reviewFingerprint(state) {
    const normalized = Object.keys(state.reviews).sort().map((itemId) => {
      const review = state.reviews[itemId];
      return {
        itemId,
        status: review.status,
        completeness: review.completeness,
        missingFields: [...review.missingFields].sort(),
        clarificationQuestions: [...review.clarificationQuestions],
        note: review.note
      };
    });
    const text = JSON.stringify(normalized);
    let hash = 2166136261;
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return `fnv1a32:${(hash >>> 0).toString(16).padStart(8, "0")}`;
  }

  function decisionIsCurrent(state) {
    return Boolean(
      state.decision
      && state.decision.updatedAt
      && state.decision.reviewFingerprint
      && state.decision.reviewFingerprint === reviewFingerprint(state)
    );
  }

  function computeGates(fixture, state) {
    const summary = summarize(fixture, state);
    const requiredFields = [
      "requirement_object",
      "preconditions",
      "required_action",
      "expected_result",
      "quantitative_target",
      "test_or_acceptance_method",
      "clarification_questions"
    ];
    const contractReady = fixture.items.every((item) => requiredFields.every((field) => Object.hasOwn(item.aiDraft, field)));
    const locatorsPresent = fixture.items.every((item) => item.evidence
      && item.evidence.status !== "missing"
      && item.evidence.sourceId
      && item.evidence.locator);
    const allReviewed = summary.reviewed === summary.total;

    return {
      structure: {
        status: contractReady ? "pass" : "blocked",
        title: "结构门禁",
        detail: contractReady
          ? `${summary.total}/${summary.total} 条审核候选符合页面合同；不代表内容正确。`
          : "审核候选缺少合同字段。"
      },
      evidence: {
        status: !locatorsPresent ? "blocked" : allReviewed ? "pass" : "pending",
        title: "证据门禁",
        detail: !locatorsPresent
          ? "存在缺少来源定位的项目。"
          : allReviewed
            ? "全部审核项已完成人工审核；仅表示审核流程走通。"
            : `${summary.unreviewed} 条尚未完成人工来源与字段审核。`
      },
      semantics: {
        status: !allReviewed ? "pending" : (summary.unable > 0 || summary.unresolved > 0 || summary.suspiciousComplete > 0) ? "blocked" : "pass",
        title: "语义门禁",
        detail: !allReviewed
          ? "需完成全部人工审核后才能形成语义门禁结论。"
          : (summary.unable > 0 || summary.unresolved > 0 || summary.suspiciousComplete > 0)
            ? `存在 ${summary.unresolved} 条非完整判断、${summary.unable} 条无法判断、${summary.suspiciousComplete} 条高风险 complete。`
            : "演示审核未留下待澄清项；这仍不是正式准确率或专家结论。"
      }
    };
  }

  function publicReviewExport(fixture, state) {
    return {
      contract: "SolutionScope-review-decision-v2-review-export",
      fixtureId: fixture.fixtureId,
      fixtureType: fixture.fixtureType,
      exportedAt: new Date().toISOString(),
      boundary: fixture.boundary,
      reviews: fixture.items.map((item) => ({
        itemId: item.id,
        sourceId: item.evidence.sourceId,
        sourceLocator: item.evidence.locator,
        aiCompleteness: item.aiCompleteness,
        humanReview: copy(state.reviews[item.id])
      })),
      summary: summarize(fixture, state),
      gates: computeGates(fixture, state),
      claimBoundary: "Sanitized synthetic interaction evidence only; no accuracy, efficiency, user-validation or generalization claim."
    };
  }

  function decisionExport(fixture, state) {
    return {
      contract: "SolutionScope-review-decision-v2-decision-card",
      fixtureId: fixture.fixtureId,
      exportedAt: new Date().toISOString(),
      reviewSummary: summarize(fixture, state),
      gates: computeGates(fixture, state),
      manualDecision: copy(state.decision),
      historicalDevelopmentObservation: copy(fixture.historicalDevelopmentObservation),
      claimBoundary: "Manual demo decision only. Release means entry to the next human evaluation stage, not deployment or production approval."
    };
  }

  const api = {
    STORAGE_KEY,
    COMPLETENESS_VALUES,
    REVIEW_STATUSES,
    createInitialState,
    normalizeState,
    loadState,
    saveState,
    resetState,
    summarize,
    computeGates,
    reviewHasMaterialChange,
    validateDecision,
    reviewFingerprint,
    decisionIsCurrent,
    publicReviewExport,
    decisionExport
  };

  root.SolutionScopeState = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
