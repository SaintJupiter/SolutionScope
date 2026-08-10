const chapters = [
  { id: "01", title: "项目背景", count: 3, state: "done" },
  { id: "02", title: "总体架构", count: 5, state: "done" },
  { id: "03", title: "数据接入", count: 8, state: "active" },
  { id: "04", title: "训练评估", count: 6, state: "review" },
  { id: "05", title: "安全边界", count: 4, state: "idle" },
];

const icons = {
  arrow: '<path d="M5 12h14M14 7l5 5-5 5"/>',
  upload: '<path d="M12 16V3M7 8l5-5 5 5"/><path d="M4 15v5h16v-5"/>',
  file: '<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5"/><path d="M9 12h6M9 16h6"/>',
  route: '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10M6 8l5 8M18 8l-5 8"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  shield: '<path d="M12 2 20 6v6c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 2.6 2.6L16.5 9"/>',
  spark: '<path d="m12 2 1.6 5.2L19 9l-5.4 1.8L12 16l-1.6-5.2L5 9l5.4-1.8z"/><path d="m19 15 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7z"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20V7"/>',
  human: '<circle cx="12" cy="8" r="4"/><path d="M4 22c.8-5 3.5-7 8-7s7.2 2 8 7"/>',
};

function icon(name) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;
}

function nav() {
  return `
    <header class="topbar">
      <a class="logo" href="#top" aria-label="SolutionScope 首页">
        <span class="logo-mark">S</span><span>Solution<em>Scope</em></span>
      </a>
      <nav class="nav-links" aria-label="主导航">
        <a href="#product">产品体验</a><a href="#workflow">工作流</a><a href="#evaluation">评测结果</a>
      </nav>
      <div class="nav-actions">
        <span class="prototype-badge">VISUAL PROTOTYPE</span>
        <button class="button button-dark js-scroll-workbench">打开工作台 ${icon("arrow")}</button>
      </div>
    </header>`;
}

function hero() {
  return `
    <section class="hero" id="top">
      <div class="hero-blob blob-coral"></div><div class="hero-blob blob-violet"></div><div class="hero-blob blob-mint"></div>
      <div class="sticker sticker-left">不是更长的 Prompt</div>
      <div class="sticker sticker-right">是更清楚的边界 ✦</div>
      <div class="hero-content reveal">
        <span class="eyebrow">AI PRODUCT LAB · CONTROLLED WORKFLOW</span>
        <h1>复杂材料，<span class="purple-block">拆开看。</span><br/>关键判断，<span class="mint-block">有据可查。</span></h1>
        <p>把可研报告、技术方案和测试材料中的要求，整理成可以逐项追溯、逐项确认的审核结果。</p>
        <div class="hero-actions">
          <button class="button button-dark js-scroll-workbench">进入产品演示 ${icon("arrow")}</button>
          <a class="text-link" href="#workflow">先看它如何工作 <span>↓</span></a>
        </div>
      </div>
      <div class="hero-ribbon" aria-label="产品能力">
        <span>REQUIREMENT EXTRACTION</span><i>✦</i><span>EVIDENCE TRACEABILITY</span><i>✦</i><span>GAP DISCOVERY</span><i>✦</i><span>HUMAN REVIEW</span>
      </div>
    </section>`;
}

function scenarioIntro() {
  return `
    <div class="scenario-intro reveal">
      <div class="scenario-copy">
        <span class="eyebrow">APPLICATION SCENARIO</span>
        <h2>技术材料进入评审后，<br/>常见问题集中在四个方面。</h2>
        <p>评审需要同时核对状态、条件、证据与验收口径；任何一项缺失，结论都需要人工复核。</p>
      </div>
      <div class="scenario-risk-grid" aria-label="技术材料评审中的四类问题">
        <article class="scenario-risk-card risk-dark">
          <div class="risk-card-top"><strong>信息分散</strong><i>${icon("file")}</i></div>
          <h3>一项要求，<br/>散在多个章节。</h3>
          <p>对象、条件、指标与验收方法需要跨页拼接。</p>
          <footer>人工定位成本高</footer>
        </article>
        <article class="scenario-risk-card risk-coral">
          <div class="risk-card-top"><strong>状态冲突</strong><i>${icon("route")}</i></div>
          <h3>“已支持”与<br/>“后续完善”并存。</h3>
          <p>同一能力的当前状态与规划状态容易被合并。</p>
          <footer>容易误判为已经完成</footer>
        </article>
        <article class="scenario-risk-card risk-violet">
          <div class="risk-card-top"><strong>证据断链</strong><i>${icon("search")}</i></div>
          <h3>结论有了，<br/>原文位置丢了。</h3>
          <p>摘要省略来源、适用条件和相关段落。</p>
          <footer>审核结果无法追溯</footer>
        </article>
        <article class="scenario-risk-card risk-yellow">
          <div class="risk-card-top"><strong>口径缺失</strong><i>${icon("shield")}</i></div>
          <h3>指标出现，<br/>通过条件未定义。</h3>
          <p>精度、时延或测试方法缺少明确判定方式。</p>
          <footer>验收结论无法落地</footer>
        </article>
      </div>
      <div class="scenario-audience">
        <span>典型使用阶段</span><b>需求梳理</b><i></i><b>方案评审</b><i></i><b>验收准备</b>
        <strong>面向方案人员、项目负责人和测试评审人员</strong>
      </div>
      <div class="scenario-capability-bridge">
        <div class="capability-copy">
          <span class="eyebrow">WHY SOLUTIONSCOPE</span>
          <h2>SolutionScope 的处理方式<br/>让每个判断都能被检查。</h2>
          <p>系统先把散落在不同章节中的要求还原为完整结构，再区分当前能力、规划状态与待确认内容；关键结论必须绑定原文证据，材料没有说明的条件和验收口径则明确进入人工审核。</p>
          <div class="capability-tags"><b>要求结构化</b><b>状态区分</b><b>证据追溯</b><b>缺口提示</b><b>人工门禁</b></div>
        </div>
        <div class="application-scenario-heading"><span>适合使用的场景</span><p>当材料低容错、模型能力受限，或多人需要共享同一判断依据时，结构化 Skill 与人工门禁比一次性生成更可靠。</p></div>
        <div class="application-scenario-grid">
          <article class="application-scenario-card app-coral"><span>低容错</span><h3>关键技术材料评审</h3><p>要求不能遗漏，审核结论必须能够回到原文、适用条件和验收依据。</p></article>
          <article class="application-scenario-card app-violet"><span>弱模型</span><h3>私有部署与受限算力</h3><p>用 Skill 的状态约束、证据锚点和人工门禁，补足轻量模型的稳定性。</p></article>
          <article class="application-scenario-card app-yellow"><span>多状态</span><h3>方案迭代与验收准备</h3><p>当前能力、后续规划和不同版本容易混写，需要保留差异与待确认口径。</p></article>
          <article class="application-scenario-card app-mint"><span>多角色</span><h3>跨团队协同审核</h3><p>方案、项目和测试人员围绕同一证据链确认问题，减少查找成本与口径偏差。</p></article>
        </div>
      </div>
    </div>`;
}

function reviewPane() {
  return `
    <section class="review-surface">
      <div class="processing-trace" id="semantic-trace">
        <div class="trace-heading">
          <span>INPUT → REVIEWABLE DECISION</span>
          <b>命题级语义标注 · 脱敏合成示例</b>
        </div>
        <div class="trace-flow">
          <article class="trace-source-card">
            <small>01 · 原始材料</small>
            <p>系统支持接入<span class="trace-current">摄像机、雷达、AIS 等多源数据</span>，并通过<span class="trace-ambiguous">统一时间轴完成数据对齐</span>；<span class="trace-future">后续将进一步完善跨设备时钟同步与误差校正</span>。</p>
            <div class="semantic-lens">
              <span><b>支持接入</b><small>动作词</small></span>
              <span><b>完成</b><small>当前状态</small></span>
              <span><b>后续 / 将</b><small>规划信号</small></span>
              <span><b>时间轴 / 同步</b><small>同一能力对象</small></span>
            </div>
          </article>
          <div class="trace-arrow">→</div>
          <article class="trace-analysis-card">
            <small>02 · 能力台账</small>
            <div class="ledger-row">
              <div><b>CAP-TIME-01</b><em class="ledger-current">CURRENT</em></div>
              <span>统一时间轴完成数据对齐</span>
              <small>SYN-01 · clause-1 · 锚点已绑定</small>
            </div>
            <div class="ledger-row">
              <div><b>CAP-TIME-01</b><em class="ledger-planned">PLANNED</em></div>
              <span>完善跨设备同步与误差校正</span>
              <small>SYN-01 · clause-2 · 锚点已绑定</small>
            </div>
            <div class="ledger-rule"><b>同一能力</b><span>＋</span><b>状态相反</b><span>→</span><strong>保留冲突</strong></div>
          </article>
          <div class="trace-arrow">→</div>
          <article class="trace-output-card">
            <small>03 · 审核结论</small>
            <strong>不能直接写成“已完成全链路时空同步”</strong>
            <p>保留原文证据，并向项目方确认当前实现范围与量化验收口径。</p>
            <div class="validation-receipt"><span>2 / 2 锚点通过</span><span>状态未被提升</span><span>进入人工门禁</span></div>
          </article>
        </div>
      </div>
      <div class="workspace-grid">
        <aside class="chapter-rail">
          <div class="rail-heading"><span>材料结构</span><b>5 章</b></div>
          ${chapters.map((chapter) => `
            <button class="chapter-item ${chapter.state === "active" ? "active" : ""}" data-chapter="${chapter.id}">
              <span class="chapter-id">${chapter.id}</span>
              <span><b>${chapter.title}</b><small>${chapter.count} 个证据片段</small></span>
              <i class="chapter-state ${chapter.state}"></i>
            </button>`).join("")}
          <button class="add-material js-demo-action">${icon("upload")} 添加材料</button>
        </aside>

        <article class="document-panel">
          <div class="panel-toolbar">
            <span class="file-label">${icon("file")} 项目可行性研究报告.pdf</span>
            <div><button aria-label="缩小">−</button><b>100%</b><button aria-label="放大">＋</button></div>
          </div>
          <div class="document-page">
            <div class="page-meta"><span>4.2</span><b>PAGE 12 / 46</b></div>
            <h3>数据接入与科研复现</h3>
            <p>平台支持按船舶建立独立的数据空间，配置 SSH、NVR、GPS、AIS、罗经、雷达及自定义传感器来源。</p>
            <p class="highlight mint-highlight">采集数据保留来源、时间、设备、文件校验值和采集任务等信息，为后续科研复现提供依据。<span>E-12</span></p>
            <p>用户可先保存接入参数，再按需执行检测或定时采集，避免因设备离线影响资料建档。</p>
            <p class="highlight coral-highlight">后续科研功能将重点完善多模态时空融合，包括 AIS、GPS、罗经、雷达和视频的统一时间轴对齐。<span>E-13</span></p>
          </div>
        </article>

        <aside class="review-panel">
          <div class="review-heading">
            <div><span>AI 审核草稿</span><strong>要求 R-08</strong></div><span class="review-score">86%</span>
          </div>
          <div class="status-strip"><i></i><span>存在 2 项待澄清</span><small>需人工确认</small></div>
          <dl class="field-list">
            <div><dt>要求对象</dt><dd>多源数据接入与科研数据留痕</dd></div>
            <div><dt>要求动作</dt><dd>保留来源、时间、设备、文件校验值及采集任务</dd></div>
            <div><dt>量化指标</dt><dd class="missing">原文未定义</dd></div>
            <div><dt>证据位置</dt><dd class="evidence">第 12 页 · §4.2 · E-12</dd></div>
          </dl>
          <div class="clarification-box">
            <span>${icon("shield")} 建议向项目方确认</span>
            <p>是否定义跨设备统一时间基准？</p><p>设备离线时采用何种补采策略？</p>
          </div>
          <div class="review-actions">
            <button class="button button-light js-demo-action">局部修改</button>
            <button class="button button-mint js-approve">接受并继续 ${icon("arrow")}</button>
          </div>
        </aside>
      </div>
    </section>`;
}

function workflowPane() {
  const steps = [
    ["01", "材料结构化", "分页、分段并记录章节与来源坐标", "coral", "file"],
    ["02", "任务路由", "根据问题意图选择检索与审核路径", "violet", "route"],
    ["03", "证据召回", "全局检索、邻段扩展与跨页合并", "cyan", "search"],
    ["04", "结构输出", "按 Schema 生成要求、证据与缺口", "lime", "spark"],
    ["05", "风险门禁", "检查无依据判断、状态漂移与冲突", "yellow", "shield"],
    ["06", "人工确认", "接受、局部修改或标记无法判断", "white", "human"],
  ];
  return `
    <section class="workflow-surface">
      <div class="workflow-pane-head"><div><span>RUN / 2026-08-09</span><h3>一条可以检查、回退和转人工的处理路径。</h3></div><button class="button button-dark js-demo-action">重新运行</button></div>
      <div class="workflow-stage">
        ${steps.map((step, index) => `
          <article class="workflow-step ${step[3]}" style="--step-delay:${index * .08}s">
            <div><span>${step[0]}</span><i>${icon(step[4])}</i></div><h4>${step[1]}</h4><p>${step[2]}</p><small>${index < 5 ? "已完成" : "等待确认"}</small>
          </article>`).join("")}
      </div>
      <div class="workflow-log">
        <div><i></i><span>10:42:18</span><p>已定位 26 个候选要求，保留 18 个可追溯条目。</p></div>
        <div><i></i><span>10:42:21</span><p>发现 3 个计划能力被误写为当前能力，已回退为待确认。</p></div>
        <div><i></i><span>10:42:22</span><p>结构门禁通过；2 个状态冲突等待人工判断。</p></div>
      </div>
    </section>`;
}

function reportPane() {
  return `
    <section class="report-surface">
      <div class="report-head"><div><span>DEVELOPMENT PILOT · N=6</span><h3>评测不是一个总分，<br/>而是一组能解释的风险。</h3></div><div class="report-status">描述性结果<br/><b>不代表泛化结论</b></div></div>
      <div class="report-grid">
        <article class="metric-card coral-card"><span>未来能力误判为当前</span><strong>8 → 0</strong><small>同材料、同问题的来源约束风险</small><div class="metric-track"><i></i><b></b></div></article>
        <article class="metric-card violet-card"><span>结构合同错误</span><strong>0</strong><small>最终输出进入人工审核所需的格式门槛</small><div class="zero-orbit">${icon("check")}</div></article>
        <article class="metric-card mint-card"><span>保留人工判断</span><strong>HITL</strong><small>对时间轴状态冲突不自动裁决</small><div class="people-dots"><i>AI</i><b>人</b><span></span></div></article>
        <article class="comparison-card">
          <div><span>直接提示</span><b>8</b><small>来源状态风险</small></div>
          <div class="comparison-divider">VS</div>
          <div><span>受控工作流</span><b>0</b><small>同口径风险</small></div>
          <footer>仅用于展示当前开发样本中的差异，未建设独立保留集。</footer>
        </article>
      </div>
    </section>`;
}

function productDemo() {
  return `
    <section class="product-section" id="product">
      ${scenarioIntro()}
      <div class="section-heading reveal"><div><span class="eyebrow">LIVE PRODUCT PREVIEW</span><h2>下面不是一张效果图，<br/>是一段完整的审核体验。</h2></div><p>这里使用合成内容演示信息层级与交互，不读取真实项目材料，也不调用任何模型。</p></div>
      <div class="demo-stack">
        <section class="demo-block demo-block-review reveal" id="review-workbench">
          <div class="demo-block-heading"><span class="demo-block-index">01</span><div><small>CORE INTERACTION</small><h3>审核工作台</h3><p>对照原文逐项核对要求、证据、缺口与验收口径，并保留人工决定。</p></div><b>可交互</b></div>
          <div class="product-shell product-shell-review">
            <div class="window-bar"><div><i></i><i></i><i></i></div><span>app.solutionscope.local / review</span><b>DEMO DATA</b></div>
            ${reviewPane()}
          </div>
        </section>
        <section class="demo-block demo-block-workflow reveal" id="workflow-run">
          <div class="demo-block-heading"><span class="demo-block-index">02</span><div><small>CONTROLLED PIPELINE</small><h3>工作流运行</h3><p>把材料导入、证据绑定、结构校验和人工门禁拆成可检查的处理阶段。</p></div><b>过程可见</b></div>
          <div class="product-shell product-shell-workflow">
            <div class="window-bar"><div><i></i><i></i><i></i></div><span>app.solutionscope.local / workflow</span><b>LOCAL RUN</b></div>
            ${workflowPane()}
          </div>
        </section>
        <section class="demo-block demo-block-report reveal" id="evaluation-report">
          <div class="demo-block-heading"><span class="demo-block-index">03</span><div><small>REVIEW EVIDENCE</small><h3>评测报告</h3><p>分开呈现审核进度、结构门禁与仍需人工处理的问题，不用单一总分掩盖风险。</p></div><b>结果可解释</b></div>
          <div class="product-shell product-shell-report">
            <div class="window-bar"><div><i></i><i></i><i></i></div><span>app.solutionscope.local / report</span><b>DEV PILOT</b></div>
            ${reportPane()}
          </div>
        </section>
      </div>
    </section>`;
}

function workflowStory() {
  return `
    <section class="story-section" id="workflow">
      <div class="story-grid">
        <article class="story-main reveal"><span class="eyebrow">WORKFLOW, NOT MAGIC</span><h2>AI 做初筛，<br/>人来做决定。</h2><p>系统不试图替代领域判断，而是把材料拆成可以被检查的要求、证据与问题。</p><button class="button button-coral js-open-pane" data-scroll-target="workflow-run">查看运行过程 ${icon("arrow")}</button></article>
        <article class="story-stat reveal"><span>关键标识召回</span><strong>+33.3 pp</strong><small>规则对齐 A/B · 74/111 → 111/111 · DEV n=6</small><div class="bars"><i></i><i></i><i></i><i></i><i></i></div></article>
        <article class="story-risk reveal"><div class="icon-tile">${icon("shield")}</div><span>风险不是隐藏</span><h3>原文没说的，<br/>系统不会替它说。</h3><div><b>缺口</b><b>冲突</b><b>待确认</b></div></article>
        <article class="story-source reveal"><span>ORIGINAL SOURCE</span><blockquote>“采集数据保留来源、时间、设备、文件校验值……”</blockquote><p><i></i> 已绑定证据 E-12</p></article>
      </div>
    </section>`;
}

function evaluationStory() {
  return `
    <section class="evaluation-section" id="evaluation">
      <div class="evaluation-copy reveal"><span class="eyebrow">MODEL EVALUATION</span><h2>同一轻量模型，<br/>少漏掉关键要求。</h2><p>两份 492 页与 733 页的公开标准按问题检索相关片段；在相同 <b>gpt-5.4-mini / low</b>、相同 6 个案例和证据候选下，受控工作流主要改善要求召回，同时保持证据绑定与验收边界判断不退化。</p><button class="button button-dark js-open-pane" data-scroll-target="evaluation-report">打开评测报告 ${icon("chart")}</button></div>
      <div class="evaluation-visual reveal">
        <div class="eval-header"><span>FROZEN DEVELOPMENT PILOT</span><b>gpt-5.4-mini / low · n=6</b></div>
        <div class="metric-compare-list">
          <article class="metric-compare">
            <div class="metric-title"><strong>关键标识召回</strong><b>+33.3 pp</b></div>
            <div class="pair-row"><span>直接回答</span><div class="compare-track"><i class="direct-fill" style="--value:66.7%"></i></div><em>74/111</em></div>
            <div class="pair-row"><span>SolutionScope</span><div class="compare-track"><i class="skill-fill" style="--value:100%"></i></div><em>111/111</em></div>
          </article>
          <article class="metric-compare">
            <div class="metric-title"><strong>评估目标召回</strong><b>+47.1 pp</b></div>
            <div class="pair-row"><span>直接回答</span><div class="compare-track"><i class="direct-fill" style="--value:52.9%"></i></div><em>37/70</em></div>
            <div class="pair-row"><span>SolutionScope</span><div class="compare-track"><i class="skill-fill" style="--value:100%"></i></div><em>70/70</em></div>
          </article>
          <article class="metric-compare">
            <div class="metric-title"><strong>评估方法召回</strong><b>+11.8 pp</b></div>
            <div class="pair-row"><span>直接回答</span><div class="compare-track"><i class="direct-fill" style="--value:88.2%"></i></div><em>15/17</em></div>
            <div class="pair-row"><span>SolutionScope</span><div class="compare-track"><i class="skill-fill" style="--value:100%"></i></div><em>17/17</em></div>
          </article>
        </div>
        <div class="guardrail-grid"><span><b>12/12 → 12/12</b>相关证据绑定</span><span><b>6/6 → 6/6</b>验收边界判断</span></div>
        <div class="eval-foot"><span><i class="coral-dot"></i>直接回答</span><span><i class="violet-dot"></i>受控工作流</span><b>Token 约 1.95×</b></div>
        <p class="eval-note">开发集诊断，不代表泛化；模型仅接收按题检索的证据片段，并非整本 1,225 页原文。</p>
      </div>
    </section>`;
}

function footer() {
  return `
    <footer class="footer">
      <div><span class="logo-mark">S</span><strong>SolutionScope</strong></div>
      <p>复杂材料的要求提取、证据追溯与人工审核工作台。</p>
      <span>THROWAWAY VISUAL FRONTEND · SYNTHETIC DATA ONLY</span>
    </footer>`;
}

function render() {
  document.getElementById("app").innerHTML = `${nav()}${hero()}${productDemo()}${workflowStory()}${evaluationStory()}${footer()}`;
  bindInteractions();
  observeReveals();
}

let toastTimer;
function toast(message) {
  const element = document.getElementById("prototype-toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 2200);
}

function bindInteractions() {
  document.querySelectorAll(".js-scroll-workbench").forEach((button) => button.addEventListener("click", () => document.getElementById("product").scrollIntoView({ behavior: "smooth" })));
  document.querySelectorAll(".js-open-pane").forEach((button) => button.addEventListener("click", () => {
    document.getElementById(button.dataset.scrollTarget)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }));
  document.querySelectorAll(".chapter-item").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".chapter-item").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    toast(`已切换至「${button.querySelector("b").textContent}」；当前为合成演示数据`);
  }));
  document.querySelectorAll(".js-demo-action").forEach((button) => button.addEventListener("click", () => toast("展示原型不执行真实操作，也不会上传或修改材料")));
  document.querySelector(".js-approve")?.addEventListener("click", (event) => {
    event.currentTarget.innerHTML = `${icon("check")} 已接受，准备下一项`;
    event.currentTarget.classList.add("approved");
    toast("演示状态已更新；刷新页面即可重置");
  });
}

function observeReveals() {
  const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (entry.isIntersecting) entry.target.classList.add("visible");
  }), { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

render();
