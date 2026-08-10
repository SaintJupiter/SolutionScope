(function attachRuntime(root) {
  "use strict";

  const payloadApi = root.SolutionScopePayload;
  const store = root.SolutionScopeState;
  const demoFixture = root.SOLUTION_SCOPE_DEMO_FIXTURE;

  if (!payloadApi || !store || !demoFixture) {
    console.error("SolutionScope runtime dependencies are missing.");
    return;
  }

  const labels = {
    requirement_object: "要求对象",
    preconditions: "前提条件",
    required_action: "要求动作",
    expected_result: "预期结果",
    quantitative_target: "量化指标",
    test_or_acceptance_method: "验收方法"
  };

  let fixture = payloadApi.loadSession() || payloadApi.normalize(demoFixture);
  let reviewState = store.loadState(fixture);
  let activeItemId = fixture.items[0].id;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function display(value, fallback = "原文未定义") {
    if (Array.isArray(value)) return value.length ? value.map(escapeHtml).join("；") : fallback;
    return value == null || String(value).trim() === "" ? fallback : escapeHtml(value);
  }

  function activeItem() {
    return fixture.items.find((item) => item.id === activeItemId) || fixture.items[0];
  }

  function reviewFor(item) {
    return reviewState.reviews[item.id];
  }

  function statusText(status) {
    return {
      unreviewed: "待审核",
      accepted: "已接受",
      modified: "已修改",
      unable: "无法判断"
    }[status] || "待审核";
  }

  function completenessText(value) {
    return {
      complete: "完整",
      partial: "部分完整",
      incomplete: "不完整",
      unknown: "待判断"
    }[value] || "待判断";
  }

  function queueState(review, active) {
    if (active) return "active";
    if (review.status === "accepted") return "done";
    if (review.status === "modified") return "review";
    if (review.status === "unable") return "unable";
    return "idle";
  }

  function renderQueue() {
    const rail = document.querySelector(".chapter-rail");
    if (!rail) return;
    const summary = store.summarize(fixture, reviewState);
    rail.innerHTML = `
      <div class="rail-heading"><span>审核队列</span><div><em>点击查看</em><b>${summary.reviewed}/${summary.total}</b></div></div>
      ${fixture.items.map((item, index) => {
        const review = reviewFor(item);
        const active = item.id === activeItemId;
        return `
          <button class="chapter-item ${active ? "active" : ""}" data-review-item="${escapeHtml(item.id)}">
            <span class="chapter-id">${String(index + 1).padStart(2, "0")}</span>
            <span><b>${escapeHtml(item.topic)}</b><small>${statusText(review.status)} · ${completenessText(review.completeness)}</small></span>
            <i class="chapter-state ${queueState(review, active)}"></i>
          </button>`;
      }).join("")}
      <button class="add-material js-import-runtime">${icon("upload")} 导入 Skill 审核包</button>
      <input class="runtime-file-input" type="file" accept="application/json,.json" hidden />`;
  }

  function renderDocument(item) {
    const toolbar = document.querySelector(".panel-toolbar");
    const page = document.querySelector(".document-page");
    if (!toolbar || !page) return;
    toolbar.querySelector(".file-label").innerHTML = `${icon("file")} ${escapeHtml(item.evidence.sourceId)}`;
    page.innerHTML = `
      <div class="page-meta"><span>${escapeHtml(item.evidence.locator)}</span><b>${escapeHtml(item.id)}</b></div>
      <h3>${escapeHtml(item.topic)}</h3>
      <p class="source-origin">${escapeHtml(item.evidence.origin)}</p>
      <p class="highlight mint-highlight">${escapeHtml(item.evidence.excerpt)}<span>PRIMARY</span></p>
      ${(item.evidence.relatedLocators || []).slice(1, 3).map((locator) => `
        <p class="related-locator">关联证据 · ${escapeHtml(locator.display || locator.locator || "已绑定")}</p>`).join("")}
      <div class="document-boundary">本页仅展示审核包内的最小证据摘录，不读取或上传原始材料。</div>`;
  }

  function fieldRows(item) {
    return Object.entries(labels).map(([key, label]) => {
      const value = item.aiDraft[key];
      const missing = value == null || String(value).trim() === "";
      return `<div><dt>${label}</dt><dd class="${missing ? "missing" : ""}">${display(value)}</dd></div>`;
    }).join("");
  }

  function renderReview(item) {
    const panel = document.querySelector(".review-panel");
    if (!panel) return;
    const review = reviewFor(item);
    const questions = review.clarificationQuestions || [];
    const hints = item.reviewHints || [];
    const issueCount = questions.length + hints.length;
    const itemIndex = fixture.items.findIndex((candidate) => candidate.id === item.id);
    panel.innerHTML = `
      <div class="review-heading">
        <div><span>AI 审核草稿 · ${itemIndex + 1}/${fixture.items.length}</span><strong>${escapeHtml(item.id)}</strong></div>
        <span class="review-score ${review.status}">${statusText(review.status)}</span>
      </div>
      <div class="status-strip ${issueCount ? "" : "clear"}">
        <i></i><span>${issueCount ? `存在 ${issueCount} 项审核提示` : "未发现显式待澄清项"}</span><small>${completenessText(review.completeness)}</small>
      </div>
      <dl class="field-list">${fieldRows(item)}</dl>
      <div class="clarification-box">
        <span>${icon("shield")} 人工复核重点</span>
        ${(hints.length ? hints : ["逐项核对字段是否被原文支持"]).map((hint) => `<p>• ${escapeHtml(hint)}</p>`).join("")}
        ${questions.map((question) => `<p>？${escapeHtml(question)}</p>`).join("")}
        ${review.note ? `<small class="review-note">修改记录：${escapeHtml(review.note)}</small>` : ""}
      </div>
      <div class="review-actions runtime-actions">
        <button class="button button-light js-runtime-modify">局部修改</button>
        <button class="button button-light js-runtime-unable">无法判断</button>
        <button class="button button-mint js-runtime-accept">接受并继续 ${icon("arrow")}</button>
      </div>`;
  }

  function gateStatus(gate) {
    return gate.status === "pass" ? "已通过" : gate.status === "blocked" ? "需处理" : "等待中";
  }

  function renderWorkflow() {
    const stage = document.querySelector(".workflow-stage");
    const log = document.querySelector(".workflow-log");
    if (!stage || !log) return;
    const summary = store.summarize(fixture, reviewState);
    const gates = store.computeGates(fixture, reviewState);
    const allReviewed = summary.reviewed === summary.total;
    const steps = [
      ["01", "审核包导入", `${fixture.items.length} 条结构化候选已载入`, "coral", "file", "已完成"],
      ["02", "合同校验", `${payloadApi.CONTRACT} 校验通过`, "violet", "route", "已完成"],
      ["03", "证据绑定", gateStatus(gates.evidence), "cyan", "search", gates.evidence.status === "blocked" ? "需处理" : "已完成"],
      ["04", "审核状态", `${summary.reviewed}/${summary.total} 条已处理`, "lime", "spark", allReviewed ? "已完成" : "进行中"],
      ["05", "风险门禁", gateStatus(gates.semantics), "yellow", "shield", gateStatus(gates.semantics)],
      ["06", "人工决定", allReviewed ? "可形成审核结论" : "等待完成全部审核", "white", "human", allReviewed ? "可决策" : "等待确认"]
    ];
    stage.innerHTML = steps.map((step, index) => `
      <article class="workflow-step ${step[3]}" style="--step-delay:${index * .08}s">
        <div><span>${step[0]}</span><i>${icon(step[4])}</i></div><h4>${step[1]}</h4><p>${escapeHtml(step[2])}</p><small>${step[5]}</small>
      </article>`).join("");
    log.innerHTML = `
      <div><i></i><span>LOCAL</span><p>已载入 ${escapeHtml(fixture.fixtureId)}，审核包仅保留在当前浏览器会话。</p></div>
      <div><i></i><span>REVIEW</span><p>${summary.reviewed} 条已处理；${summary.unreviewed} 条待审核；${summary.unresolved} 条仍含缺口或追问。</p></div>
      <div><i></i><span>GATE</span><p>${escapeHtml(gates.semantics.detail)}</p></div>`;
  }

  function renderReport() {
    const grid = document.querySelector(".report-grid");
    const status = document.querySelector(".report-status");
    if (!grid || !status) return;
    const summary = store.summarize(fixture, reviewState);
    const gates = store.computeGates(fixture, reviewState);
    status.innerHTML = `当前审核状态<br/><b>${summary.reviewed}/${summary.total} 条已处理</b>`;
    grid.innerHTML = `
      <article class="metric-card coral-card"><span>人工审核进度</span><strong>${summary.reviewed}/${summary.total}</strong><small>接受、修改或无法判断均计入已处理</small><div class="metric-track"><i style="width:${Math.round(summary.reviewed / summary.total * 100)}%"></i><b></b></div></article>
      <article class="metric-card violet-card"><span>结构合同门禁</span><strong>${gates.structure.status === "pass" ? "PASS" : "BLOCK"}</strong><small>${escapeHtml(gates.structure.detail)}</small><div class="zero-orbit">${icon(gates.structure.status === "pass" ? "check" : "shield")}</div></article>
      <article class="metric-card mint-card"><span>仍需人工处理</span><strong>${summary.unresolved}</strong><small>含非完整判断、缺失字段或澄清问题</small><div class="people-dots"><i>AI</i><b>人</b><span></span></div></article>
      <article class="comparison-card">
        <div><span>高风险 complete</span><b>${summary.suspiciousComplete}</b><small>不自动视为正确</small></div>
        <div class="comparison-divider">+</div>
        <div><span>无法判断</span><b>${summary.unable}</b><small>明确转人工处理</small></div>
        <footer>本页反映当前浏览器审核状态，不代表准确率、专家结论或泛化能力。 <button class="inline-export js-runtime-export">导出审核结果</button></footer>
      </article>`;
  }

  function renderWindowMeta() {
    const path = document.querySelector(".window-bar > span");
    const badge = document.querySelector(".window-bar > b");
    if (path) path.textContent = `app.solutionscope.local / ${fixture.fixtureId}`;
    if (badge) badge.textContent = fixture.fixtureType.includes("synthetic") ? "DEMO DATA" : "LOCAL PAYLOAD";
  }

  function switchActiveItem(itemId) {
    if (!itemId || itemId === activeItemId) return;
    activeItemId = itemId;
    renderRuntime();
  }

  function saveAndRefresh(message, advance = false) {
    store.saveState(reviewState);
    if (advance) {
      const index = fixture.items.findIndex((item) => item.id === activeItemId);
      const next = fixture.items.slice(index + 1).find((item) => reviewFor(item).status === "unreviewed")
        || fixture.items.find((item) => reviewFor(item).status === "unreviewed");
      if (next) activeItemId = next.id;
    }
    renderRuntime();
    toast(message);
  }

  function downloadJson(filename, value) {
    const blob = new Blob([JSON.stringify(value, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function bindRuntime() {
    document.querySelectorAll("[data-review-item]").forEach((button) => button.addEventListener("click", () => {
      switchActiveItem(button.dataset.reviewItem, "manual");
    }));

    const input = document.querySelector(".runtime-file-input");
    document.querySelector(".js-import-runtime")?.addEventListener("click", () => input?.click());
    input?.addEventListener("change", async () => {
      try {
        const file = input.files && input.files[0];
        if (!file) return;
        const imported = payloadApi.normalize(JSON.parse(await file.text()));
        payloadApi.saveSession(imported);
        fixture = imported;
        reviewState = store.loadState(fixture);
        activeItemId = fixture.items[0].id;
        renderRuntime();
        toast(`已载入 ${fixture.fixtureId}；文件未上传`);
      } catch (error) {
        toast(`导入失败：${error.message}`);
      }
    });

    document.querySelector(".js-runtime-accept")?.addEventListener("click", () => {
      const item = activeItem();
      const review = reviewFor(item);
      review.status = "accepted";
      review.updatedAt = new Date().toISOString();
      saveAndRefresh(`已接受「${item.topic}」`, true);
    });

    document.querySelector(".js-runtime-modify")?.addEventListener("click", () => {
      const item = activeItem();
      const review = reviewFor(item);
      const note = root.prompt("记录本次局部修改或判断依据：", review.note || "补充缺口并保留人工确认");
      if (note == null) return;
      review.status = "modified";
      review.completeness = item.suggestedMissingFields.length ? "partial" : review.completeness;
      review.missingFields = [...item.suggestedMissingFields];
      review.note = note.trim();
      review.updatedAt = new Date().toISOString();
      saveAndRefresh(`已记录「${item.topic}」的局部修改`);
    });

    document.querySelector(".js-runtime-unable")?.addEventListener("click", () => {
      const item = activeItem();
      const review = reviewFor(item);
      review.status = "unable";
      review.completeness = "unknown";
      review.note = "现有证据不足，转人工进一步确认";
      review.updatedAt = new Date().toISOString();
      saveAndRefresh(`「${item.topic}」已标记为无法判断`, true);
    });

    document.querySelector(".js-runtime-export")?.addEventListener("click", () => {
      downloadJson(`solutionscope-${fixture.fixtureId}-review.json`, store.publicReviewExport(fixture, reviewState));
      toast("审核结果已导出为本地 JSON");
    });
  }

  function ensureImportButton() {
    const actions = document.querySelector(".nav-actions");
    if (!actions || actions.querySelector(".js-nav-import")) return;
    const button = document.createElement("button");
    button.className = "button button-light js-nav-import";
    button.textContent = "导入审核包";
    button.addEventListener("click", () => {
      document.getElementById("product")?.scrollIntoView({behavior: "smooth"});
      setTimeout(() => document.querySelector(".runtime-file-input")?.click(), 350);
    });
    actions.insertBefore(button, actions.querySelector(".button-dark"));
  }

  function renderRuntime() {
    renderQueue();
    renderDocument(activeItem());
    renderReview(activeItem());
    renderWorkflow();
    renderReport();
    renderWindowMeta();
    bindRuntime();
    ensureImportButton();
  }

  renderRuntime();
})(window);
