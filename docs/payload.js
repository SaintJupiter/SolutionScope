(function attachPayload(root) {
  "use strict";

  const CONTRACT = "SolutionScope-ui-review-payload-v1";
  const SESSION_KEY = "solutionscope.reviewDecisionV2.importedPayload.v1";
  const REQUIRED_DRAFT_FIELDS = [
    "requirement_object",
    "preconditions",
    "required_action",
    "expected_result",
    "quantitative_target",
    "test_or_acceptance_method",
    "clarification_questions"
  ];

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function requireString(value, path, allowEmpty = false) {
    if (typeof value !== "string" || (!allowEmpty && !value.trim())) {
      throw new Error(`${path} 必须是${allowEmpty ? "" : "非空"}字符串。`);
    }
    return value;
  }

  function validate(payload) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("审核包必须是 JSON 对象。");
    }
    if (payload.contract !== CONTRACT) {
      throw new Error(`不支持的 contract：${String(payload.contract || "缺失")}。`);
    }
    requireString(payload.fixtureId, "fixtureId");
    requireString(payload.fixtureType, "fixtureType");
    requireString(payload.title, "title");
    requireString(payload.subtitle, "subtitle", true);
    if (!Array.isArray(payload.boundary) || payload.boundary.length === 0) {
      throw new Error("boundary 至少需要一条使用边界。");
    }
    if (!Array.isArray(payload.items) || payload.items.length === 0 || payload.items.length > 100) {
      throw new Error("items 数量必须在 1—100 之间。");
    }
    const ids = new Set();
    payload.items.forEach((item, index) => {
      const base = `items[${index}]`;
      requireString(item.id, `${base}.id`);
      if (ids.has(item.id)) throw new Error(`${base}.id 重复：${item.id}。`);
      ids.add(item.id);
      requireString(item.topic, `${base}.topic`);
      if (!["high", "normal"].includes(item.risk)) throw new Error(`${base}.risk 无效。`);
      if (!item.evidence || typeof item.evidence !== "object") throw new Error(`${base}.evidence 缺失。`);
      if (!["bound", "missing"].includes(item.evidence.status)) throw new Error(`${base}.evidence.status 无效。`);
      requireString(item.evidence.sourceId, `${base}.evidence.sourceId`);
      requireString(item.evidence.locator, `${base}.evidence.locator`);
      requireString(item.evidence.origin, `${base}.evidence.origin`);
      requireString(item.evidence.excerpt, `${base}.evidence.excerpt`);
      if (!item.aiDraft || typeof item.aiDraft !== "object") throw new Error(`${base}.aiDraft 缺失。`);
      REQUIRED_DRAFT_FIELDS.forEach((field) => {
        if (!Object.hasOwn(item.aiDraft, field)) throw new Error(`${base}.aiDraft.${field} 缺失。`);
      });
      if (!Array.isArray(item.aiDraft.clarification_questions)) throw new Error(`${base}.aiDraft.clarification_questions 必须是数组。`);
      if (!["complete", "partial", "incomplete", "unknown"].includes(item.aiCompleteness)) {
        throw new Error(`${base}.aiCompleteness 无效。`);
      }
      if (!Array.isArray(item.reviewHints) || !Array.isArray(item.suggestedMissingFields)) {
        throw new Error(`${base} 的审核提示字段必须是数组。`);
      }
    });
    return true;
  }

  function normalize(payload) {
    validate(payload);
    const result = clone(payload);
    result.boundary = result.boundary.map(String);
    result.fieldLabels = result.fieldLabels && typeof result.fieldLabels === "object" ? result.fieldLabels : {};
    result.historicalDevelopmentObservation = result.historicalDevelopmentObservation || null;
    result.items.forEach((item) => {
      item.evidence.relatedLocators = Array.isArray(item.evidence.relatedLocators) ? item.evidence.relatedLocators : [];
    });
    return result;
  }

  function saveSession(payload) {
    root.sessionStorage.setItem(SESSION_KEY, JSON.stringify(normalize(payload)));
  }

  function loadSession() {
    try {
      const raw = root.sessionStorage && root.sessionStorage.getItem(SESSION_KEY);
      return raw ? normalize(JSON.parse(raw)) : null;
    } catch (_) {
      return null;
    }
  }

  function clearSession() {
    try {
      if (root.sessionStorage) root.sessionStorage.removeItem(SESSION_KEY);
    } catch (_) {}
  }

  const api = {CONTRACT, SESSION_KEY, REQUIRED_DRAFT_FIELDS, validate, normalize, saveSession, loadSession, clearSession};
  root.SolutionScopePayload = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
