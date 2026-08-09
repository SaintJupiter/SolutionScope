(function runPrototype() {
  "use strict";

  const defaultFixture = window.SOLUTION_SCOPE_DEMO_FIXTURE;
  const payloadApi = window.SolutionScopePayload;
  const store = window.SolutionScopeState;
  const app = document.getElementById("app");
  if (!defaultFixture || !payloadApi || !store) {
    app.innerHTML = "<p>Prototype fixture, payload or state module failed to load.</p>";
    return;
  }

  let fixture = payloadApi.loadSession() || payloadApi.normalize(defaultFixture);
  let state = store.loadState(fixture);
  let selectedId = fixture.items[0].id;
  let decisionDraftChoice = store.decisionIsCurrent(state) ? state.decision.choice : null;
  let importMessage = fixture.fixtureId === defaultFixture.fixtureId
    ? "当前使用公开合成演示。"
    : `已载入 ${fixture.fixtureId}；审核包仅保留在当前浏览器会话。`;

  const DEFAULT_FIELD_LABELS = {
    requirement_object: "要求对象",
    preconditions: "前置条件",
    required_action: "要求动作",
    expected_result: "期望结果",
    quantitative_target: "量化目标",
    test_or_acceptance_method: "测试 / 验收方法",
    scope_boundary: "适用范围",
    audit_requirement: "审计要求"
  };

  const MISSING_OPTIONS = [
    "requirement_object",
    "preconditions",
    "required_action",
    "expected_result",
    "quantitative_target",
    "test_or_acceptance_method",
    "scope_boundary",
    "audit_requirement"
  ];

  function fieldLabels() {
    return {...DEFAULT_FIELD_LABELS, ...(fixture.fieldLabels || {})};
  }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[character]));
  }

  function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function pageHeader(active) {
    return `<header class="topbar">
      <div>
        <p class="eyebrow">SolutionScope / review-decision-v2 / product prototype</p>
        <h1>${esc(fixture.title)}</h1>
        <p>${esc(fixture.subtitle)}</p>
      </div>
      <nav class="topnav">
        <a href="index.html" class="${active === "review" ? "active" : ""}">01 语义审核</a>
        <a href="decision.html" class="${active === "decision" ? "active" : ""}">02 门禁与决策</a>
        <label class="import-button">导入审核包<input type="file" accept="application/json,.json" data-import-payload /></label>
        <button type="button" data-reset>重置本地审核</button>
        <button type="button" data-restore-demo>恢复合成演示</button>
      </nav>
    </header>`;
  }

  function boundaryBanner() {
    return `<aside class="boundary"><strong>使用边界</strong><span>${fixture.boundary.map(esc).join("　·　")}</span></aside>
      <aside class="import-status" aria-live="polite">${esc(importMessage)}</aside>`;
  }

  function statusLabel(status) {
    return ({
      unreviewed: "待审核",
      accepted: "已接受",
      modified: "已修改",
      unable: "无法判断"
    })[status] || status;
  }

  function completenessLabel(value) {
    return ({complete: "完整", partial: "部分完整", incomplete: "不完整", unknown: "未知"})[value] || value;
  }

  function summaryStrip() {
    const summary = store.summarize(fixture, state);
    return `<section class="summary-strip">
      <div><strong>${summary.reviewed}/${summary.total}</strong><span>已完成人工审核</span></div>
      <div><strong>${summary.modified}</strong><span>人工修改</span></div>
      <div><strong>${summary.unable}</strong><span>无法判断</span></div>
      <div><strong>${summary.unresolved}</strong><span>非完整 / 待澄清</span></div>
      <div><strong>${summary.suspiciousComplete}</strong><span>高风险仍标 complete</span></div>
    </section>`;
  }

  function queue(item) {
    return `<aside class="panel queue">
      <div class="panel-head"><div><p class="eyebrow muted">Review queue</p><h2>审核队列</h2></div><span class="badge ${item.risk}">${item.risk === "high" ? "高风险" : "常规"}</span></div>
      <div class="queue-list">${fixture.items.map((entry) => {
        const review = state.reviews[entry.id];
        return `<button type="button" class="queue-item ${entry.id === item.id ? "selected" : ""}" data-select="${entry.id}">
          <span class="id">${entry.id.replace("DEMO-", "")}</span>
          <span class="topic">${esc(entry.topic)}</span>
          <small>${statusLabel(review.status)} · ${completenessLabel(review.completeness)}</small>
        </button>`;
      }).join("")}</div>
    </aside>`;
  }

  function sourcePanel(item) {
    return `<section class="panel source-card">
      <div class="panel-head"><div><p class="eyebrow muted">Source & provenance</p><h2>来源短摘录</h2></div><span class="badge ${item.evidence.status === "missing" ? "unable" : "normal"}">${item.evidence.status === "missing" ? "缺少锚点" : fixture.fixtureType === "sanitized_synthetic_public_demo" ? "合成演示" : "来源已绑定"}</span></div>
      <div class="panel-body">
        <div class="metadata">
          <div><span>来源 ID</span><strong>${esc(item.evidence.sourceId)}</strong></div>
          <div><span>定位</span><strong>${esc(item.evidence.locator)}</strong></div>
          <div><span>来源性质</span><strong>${esc(item.evidence.origin)}</strong></div>
        </div>
        <blockquote>${esc(item.evidence.excerpt)}</blockquote>
        <p class="muted small">${item.evidence.relatedLocators && item.evidence.relatedLocators.length > 1 ? `该回答共关联 ${item.evidence.relatedLocators.length} 个来源锚点，页面展示首个。` : "页面展示当前回答的首个来源锚点。"} 任何来源绑定都不等于人工金标。</p>
      </div>
    </section>`;
  }

  function aiDraftPanel(item) {
    const fields = [
      "requirement_object",
      "preconditions",
      "required_action",
      "expected_result",
      "quantitative_target",
      "test_or_acceptance_method"
    ];
    return `<section class="panel">
      <div class="panel-head"><div><p class="eyebrow muted">AI draft / read-only</p><h2>AI 结构化字段</h2></div><span class="pill pending">初始 ${esc(item.aiCompleteness)}</span></div>
      <div class="panel-body">
        <dl class="field-grid">${fields.map((field) => {
          const value = item.aiDraft[field];
          return `<div class="field ${["expected_result", "test_or_acceptance_method"].includes(field) ? "wide" : ""}">
            <dt>${esc(fieldLabels()[field])}</dt>
            <dd class="${value == null ? "null" : ""}">${value == null ? "— 未提供 —" : esc(value)}</dd>
          </div>`;
        }).join("")}</dl>
      </div>
    </section>`;
  }

  function reviewPanel(item) {
    const review = state.reviews[item.id];
    return `<section class="panel review-form">
      <div class="panel-head"><div><p class="eyebrow muted">Human review</p><h2>人工完整性审核</h2></div><span class="badge ${review.status}">${statusLabel(review.status)}</span></div>
      <div class="panel-body">
        <div class="hints">
          <strong>审查提示（演示规则，不是金标）</strong>
          <ul>${item.reviewHints.length ? item.reviewHints.map((hint) => `<li>${esc(hint)}</li>`).join("") : "<li>暂无预置风险提示，请独立核对。</li>"}</ul>
        </div>

        <label class="title" for="completeness">人工完整性判断</label>
        <select id="completeness">
          ${store.COMPLETENESS_VALUES.map((value) => `<option value="${value}" ${review.completeness === value ? "selected" : ""}>${value} · ${completenessLabel(value)}</option>`).join("")}
        </select>

        <label class="title">缺失字段</label>
        <div class="check-grid">${MISSING_OPTIONS.map((field) => `<label>
          <input type="checkbox" data-missing="${field}" ${review.missingFields.includes(field) ? "checked" : ""} />
          <span>${esc(fieldLabels()[field])}${item.suggestedMissingFields.includes(field) ? " · 建议关注" : ""}</span>
        </label>`).join("")}</div>

        <label class="title" for="questions">待澄清问题（每行一条）</label>
        <textarea id="questions" rows="5" placeholder="信息不足时写出需要向谁确认什么。">${esc(review.clarificationQuestions.join("\n"))}</textarea>

        <label class="title" for="note">审核说明</label>
        <textarea id="note" rows="3" placeholder="说明接受、修改或无法判断的依据。">${esc(review.note)}</textarea>

        <div class="actions">
          <button type="button" data-review-status="accepted" class="${review.status === "accepted" ? "active" : ""}">接受当前判断</button>
          <button type="button" data-review-status="modified" class="primary ${review.status === "modified" ? "active" : ""}">保存人工修改</button>
          <button type="button" data-review-status="unable" class="warn ${review.status === "unable" ? "active" : ""}">无法判断</button>
        </div>
        <p class="saved" id="save-message">${review.updatedAt ? `已在本地保存 · ${esc(new Date(review.updatedAt).toLocaleString("zh-CN"))}` : "修改会保存到当前浏览器 localStorage。"}</p>
      </div>
    </section>`;
  }

  function renderReview() {
    const item = fixture.items.find((entry) => entry.id === selectedId) || fixture.items[0];
    app.innerHTML = `<main class="shell">
      ${pageHeader("review")}${boundaryBanner()}${summaryStrip()}
      <section class="review-layout">
        ${queue(item)}
        <main class="stack">${sourcePanel(item)}${aiDraftPanel(item)}</main>
        <aside class="stack">${reviewPanel(item)}
          <section class="panel"><div class="panel-body">
            <strong>下一步</strong><p class="muted">完成全部审核后进入三层门禁页。人工“接受”不等于专家金标，也不自动放行。</p>
            <div class="footer-actions"><a class="button primary" href="decision.html">查看门禁与决策</a><button class="button" type="button" data-export-review>导出审核 JSON</button></div>
          </div></section>
        </aside>
      </section>
    </main>`;
    bindCommon();
    bindReview(item);
  }

  function gateCard(gate) {
    const statusText = ({pass: "通过", pending: "待完成", blocked: "阻断"})[gate.status];
    return `<article class="gate ${gate.status}"><span class="pill ${gate.status}">${statusText}</span><h3>${esc(gate.title)}</h3><p>${esc(gate.detail)}</p></article>`;
  }

  function historicalPanel() {
    const history = fixture.historicalDevelopmentObservation;
    if (!history) return "";
    return `<section class="panel">
      <div class="panel-head"><div><p class="eyebrow muted">Historical development observation</p><h2>历史开发实验边界</h2></div><span class="badge high">非正式评测</span></div>
      <div class="panel-body">
        <div class="history-flow">
          <div class="history-card"><span class="muted small">A0 严格合同错误</span><strong>${history.a0StrictContractErrors}</strong><span class="small">共享 Schema / 空模板</span></div>
          <div class="history-arrow">→</div>
          <div class="history-card"><span class="muted small">B1 严格合同错误</span><strong>${history.b1StrictContractErrorsAfterOneMachineRetry}</strong><span class="small">一次纯机器反馈重试后</span></div>
          <div class="history-arrow">≠</div>
          <div class="history-card risk-card"><span class="muted small">B1 过度 complete 风险</span><strong>${history.b1OverCompleteRiskCount}/${history.b1ComparedItemCount}</strong><span class="small">结构通过不等于语义正确</span></div>
        </div>
        <ul class="boundary-list"><li>${esc(history.scope)}</li><li>${esc(history.interpretation)}</li><li>本页不展示历史受限原文、原始输出或准确率。</li></ul>
      </div>
    </section>`;
  }

  function currentSummaryPanel(summary) {
    return `<section class="panel">
      <div class="panel-head"><div><p class="eyebrow muted">Current review</p><h2>当前审核汇总</h2></div><span class="badge normal">浏览器本地</span></div>
      <div class="panel-body"><div class="metric-list">
        <div><strong>${summary.reviewed}/${summary.total}</strong><span>已审核</span></div>
        <div><strong>${summary.modified}</strong><span>人工修改</span></div>
        <div><strong>${summary.unresolved}</strong><span>非完整判断</span></div>
        <div><strong>${summary.suspiciousComplete}</strong><span>高风险仍标 complete</span></div>
      </div></div>
    </section>`;
  }

  function decisionForm(gates) {
    const decision = state.decision;
    const autoBlocked = Object.values(gates).some((gate) => gate.status === "blocked");
    const decisionCurrent = store.decisionIsCurrent(state);
    return `<section class="panel review-form">
      <div class="panel-head"><div><p class="eyebrow muted">Human stage decision</p><h2>阶段决策</h2></div>${decisionCurrent ? `<span class="badge ${decision.choice === "block" ? "unable" : "modified"}">${decision.choice === "block" ? "阻断" : "有限放行"}</span>` : decision.updatedAt ? `<span class="badge high">已失效</span>` : ""}</div>
      <div class="panel-body">
        <p class="warning">“放行”仅指进入下一轮人工评测，不代表上线、部署、质量达标或生产批准。人工选择也不会改写上方自动门禁状态。</p>
        ${decision.updatedAt && !decisionCurrent ? `<p class="warning"><strong>原决定已失效。</strong> 审核内容已变化，需基于当前门禁重新确认。</p>` : ""}
        ${autoBlocked ? `<p class="warning"><strong>当前存在阻断门禁。</strong> 如选择有限放行，请在说明中记录例外理由。</p>` : ""}
        <div class="decision-choice">
          <label><input type="radio" name="decision" value="block" ${decisionDraftChoice === "block" ? "checked" : ""} /><span><strong>阻断</strong><br /><span class="muted small">修正问题并完成回归后再进入下一阶段。</span></span></label>
          <label><input type="radio" name="decision" value="release_to_human_evaluation" ${decisionDraftChoice === "release_to_human_evaluation" ? "checked" : ""} /><span><strong>有限放行至人工评测</strong><br /><span class="muted small">只允许进入受控人工审核，不代表语义质量达标。</span></span></label>
        </div>
        <label class="title" for="decision-note">决策说明</label>
        <textarea id="decision-note" rows="4" placeholder="记录阻断项、残余风险或例外理由。">${esc(decision.note)}</textarea>
        <label class="title" for="next-action">下一步行动</label>
        <textarea id="next-action" rows="4">${esc(decision.nextAction)}</textarea>
        <div class="footer-actions"><button type="button" class="button primary" data-save-decision>保存决定</button><button type="button" class="button" data-export-decision>导出决策卡</button><a class="button" href="index.html">返回审核页</a></div>
        <p class="saved" id="decision-message">${decisionCurrent ? `已在本地保存 · ${esc(new Date(decision.updatedAt).toLocaleString("zh-CN"))}` : decision.updatedAt ? "原阶段决定已因审核变化而失效。" : "尚未形成阶段决定。"}</p>
      </div>
    </section>`;
  }

  function renderDecision() {
    const summary = store.summarize(fixture, state);
    const gates = store.computeGates(fixture, state);
    app.innerHTML = `<main class="shell">
      ${pageHeader("decision")}${boundaryBanner()}
      <section class="decision-grid">
        <main class="stack">
          <section class="panel"><div class="panel-head"><div><p class="eyebrow muted">Layered quality gates</p><h2>结构、证据、语义三层门禁</h2></div></div><div class="panel-body"><div class="gate-grid">${Object.values(gates).map(gateCard).join("")}</div></div></section>
          ${historicalPanel()}
        </main>
        <aside class="stack">${currentSummaryPanel(summary)}${decisionForm(gates)}</aside>
      </section>
    </main>`;
    bindCommon();
    bindDecision();
  }

  function bindCommon() {
    document.querySelectorAll("[data-reset]").forEach((button) => button.addEventListener("click", () => {
      if (!window.confirm("清空当前审核包在本浏览器中的审核与决策状态？")) return;
      state = store.resetState(fixture);
      decisionDraftChoice = null;
      importMessage = `已清空 ${fixture.fixtureId} 的本地审核状态。`;
      document.body.dataset.page === "review" ? renderReview() : renderDecision();
    }));

    document.querySelectorAll("[data-restore-demo]").forEach((button) => button.addEventListener("click", () => {
      payloadApi.clearSession();
      fixture = payloadApi.normalize(defaultFixture);
      state = store.loadState(fixture);
      selectedId = fixture.items[0].id;
      decisionDraftChoice = store.decisionIsCurrent(state) ? state.decision.choice : null;
      importMessage = "已恢复公开合成演示。";
      document.body.dataset.page === "review" ? renderReview() : renderDecision();
    }));

    document.querySelectorAll("[data-import-payload]").forEach((input) => input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      try {
        const imported = payloadApi.normalize(JSON.parse(await file.text()));
        payloadApi.saveSession(imported);
        fixture = imported;
        state = store.loadState(fixture);
        selectedId = fixture.items[0].id;
        decisionDraftChoice = store.decisionIsCurrent(state) ? state.decision.choice : null;
        importMessage = `已载入 ${file.name}（${fixture.items.length} 项）；文件未上传，仅保留在当前浏览器会话。`;
      } catch (error) {
        importMessage = `导入失败：${error && error.message ? error.message : "无法解析审核包"}`;
      }
      document.body.dataset.page === "review" ? renderReview() : renderDecision();
    }));
  }

  function bindReview(item) {
    document.querySelectorAll("[data-select]").forEach((button) => button.addEventListener("click", () => {
      selectedId = button.dataset.select;
      renderReview();
    }));

    const review = state.reviews[item.id];
    document.getElementById("completeness").addEventListener("change", (event) => {
      review.completeness = event.target.value;
      review.updatedAt = new Date().toISOString();
      store.saveState(state);
      renderReview();
    });

    document.querySelectorAll("[data-missing]").forEach((checkbox) => checkbox.addEventListener("change", () => {
      review.missingFields = Array.from(document.querySelectorAll("[data-missing]:checked")).map((input) => input.dataset.missing);
      review.updatedAt = new Date().toISOString();
      store.saveState(state);
      document.getElementById("save-message").textContent = "缺失字段已在本地保存。";
    }));

    document.getElementById("questions").addEventListener("change", (event) => {
      review.clarificationQuestions = event.target.value.split("\n").map((line) => line.trim()).filter(Boolean);
      review.updatedAt = new Date().toISOString();
      store.saveState(state);
    });

    document.getElementById("note").addEventListener("change", (event) => {
      review.note = event.target.value.trim();
      review.updatedAt = new Date().toISOString();
      store.saveState(state);
    });

    document.querySelectorAll("[data-review-status]").forEach((button) => button.addEventListener("click", () => {
      const requestedStatus = button.dataset.reviewStatus;
      const candidate = {
        ...review,
        status: requestedStatus,
        completeness: requestedStatus === "unable" ? "unknown" : document.getElementById("completeness").value,
        clarificationQuestions: document.getElementById("questions").value.split("\n").map((line) => line.trim()).filter(Boolean),
        note: document.getElementById("note").value.trim(),
        missingFields: Array.from(document.querySelectorAll("[data-missing]:checked")).map((input) => input.dataset.missing)
      };
      if (requestedStatus === "modified" && !store.reviewHasMaterialChange(item, candidate)) {
        document.getElementById("save-message").textContent = "未检测到实质修改；请先调整完整性、缺失字段、追问或审核说明。";
        return;
      }
      Object.assign(review, candidate);
      review.updatedAt = new Date().toISOString();
      store.saveState(state);
      renderReview();
    }));

    document.querySelector("[data-export-review]").addEventListener("click", () => {
      downloadJson(`solutionscope-${fixture.fixtureId}-review.json`, store.publicReviewExport(fixture, state));
    });
  }

  function bindDecision() {
    document.querySelectorAll('input[name="decision"]').forEach((input) => input.addEventListener("change", () => {
      decisionDraftChoice = input.value;
      document.getElementById("decision-message").textContent = "已选择草案；点击“保存决定”后才会写入本地审计记录。";
    }));

    document.querySelector("[data-save-decision]").addEventListener("click", () => {
      const note = document.getElementById("decision-note").value.trim();
      const nextAction = document.getElementById("next-action").value.trim();
      const result = store.validateDecision(store.computeGates(fixture, state), decisionDraftChoice, note, nextAction);
      if (!result.ok) {
        document.getElementById("decision-message").textContent = result.message;
        return;
      }
      state.decision.choice = decisionDraftChoice;
      state.decision.note = note;
      state.decision.nextAction = nextAction;
      state.decision.reviewFingerprint = store.reviewFingerprint(state);
      state.decision.updatedAt = new Date().toISOString();
      store.saveState(state);
      renderDecision();
    });

    document.querySelector("[data-export-decision]").addEventListener("click", () => {
      if (!store.decisionIsCurrent(state)) {
        document.getElementById("decision-message").textContent = "当前没有与最新审核状态匹配的已保存决定；请重新保存后导出。";
        return;
      }
      downloadJson(`solutionscope-${fixture.fixtureId}-decision-card.json`, store.decisionExport(fixture, state));
    });
  }

  if (document.body.dataset.page === "decision") renderDecision();
  else renderReview();
})();
