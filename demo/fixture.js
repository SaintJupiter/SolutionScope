(function attachFixture(root) {
  "use strict";

  const fixture = {
    contract: "SolutionScope-ui-review-payload-v1",
    fixtureId: "SS-RD-V2-DEMO-001",
    fixtureType: "sanitized_synthetic_public_demo",
    title: "技术材料要求抽取与审核",
    subtitle: "脱敏合成演示 · 不含客户、课题组、ISO 或受限材料原文",
    boundary: [
      "所有短摘录均由项目作者独立编写，仅用于演示审核交互。",
      "页面不调用模型，不代表准确率、效率、用户验证或跨场景能力。",
      "历史开发实验仅展示已经允许对外陈述的聚合边界，不展示受限输入与输出。"
    ],
    historicalDevelopmentObservation: {
      scope: "本地受限、单一来源族、开发性描述观察；不是正式评测或泛化结论。",
      a0StrictContractErrors: 37,
      b1StrictContractErrorsAfterOneMachineRetry: 0,
      b1OverCompleteRiskCount: 18,
      b1ComparedItemCount: 20,
      interpretation: "结构合同通过不等于语义内容正确；过度 complete 是下一版优先 Bad Case。"
    },
    items: [
      {
        id: "DEMO-R01",
        topic: "运行记录留存",
        risk: "high",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-001",
          locator: "§2.1 / paragraph 03",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "系统应保留关键任务的运行记录，以支持后续问题追溯。"
        },
        aiDraft: {
          requirement_object: "关键任务运行记录",
          preconditions: "任务已执行",
          required_action: "保存运行记录",
          expected_result: "能够支持后续问题追溯",
          quantitative_target: null,
          test_or_acceptance_method: "检查是否存在对应运行记录",
          clarification_questions: ["运行记录需要保留多长时间？", "哪些字段属于关键记录？"]
        },
        aiCompleteness: "complete",
        reviewHints: ["保留周期未定义", "关键字段范围未定义"],
        suggestedMissingFields: ["quantitative_target", "scope_boundary"]
      },
      {
        id: "DEMO-R02",
        topic: "答案证据定位",
        risk: "normal",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-001",
          locator: "§2.3 / paragraph 01",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "回答应展示引用来源，并允许审核者定位到对应原文段落。"
        },
        aiDraft: {
          requirement_object: "AI 回答",
          preconditions: "回答引用了知识材料",
          required_action: "展示来源并提供段落定位",
          expected_result: "审核者能够回到支持该回答的原文",
          quantitative_target: null,
          test_or_acceptance_method: "抽查引用链接和段落定位是否可用",
          clarification_questions: []
        },
        aiCompleteness: "complete",
        reviewHints: [],
        suggestedMissingFields: []
      },
      {
        id: "DEMO-R03",
        topic: "高峰期响应",
        risk: "high",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-001",
          locator: "§3.2 / bullet 02",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "在业务高峰期，系统仍应保持快速响应。"
        },
        aiDraft: {
          requirement_object: "系统响应性能",
          preconditions: "处于业务高峰期",
          required_action: "维持快速响应",
          expected_result: "用户请求能够及时获得结果",
          quantitative_target: null,
          test_or_acceptance_method: "在模拟高峰流量下观察响应时间",
          clarification_questions: ["高峰期的并发量如何定义？", "可接受的响应时间阈值是多少？"]
        },
        aiCompleteness: "complete",
        reviewHints: ["并发规模未定义", "响应阈值未定义"],
        suggestedMissingFields: ["preconditions", "quantitative_target", "test_or_acceptance_method"]
      },
      {
        id: "DEMO-R04",
        topic: "客户材料访问控制",
        risk: "high",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-002",
          locator: "§1.4 / paragraph 02",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "只有经过授权的人员可以查看客户材料。"
        },
        aiDraft: {
          requirement_object: "客户材料",
          preconditions: "用户访问客户材料",
          required_action: "校验用户是否获得授权",
          expected_result: "未授权人员无法查看材料",
          quantitative_target: null,
          test_or_acceptance_method: "使用授权与未授权账号分别访问",
          clarification_questions: ["授权角色和材料范围如何配置？", "是否需要记录访问审计日志？"]
        },
        aiCompleteness: "partial",
        reviewHints: ["角色范围待定义", "审计要求待确认"],
        suggestedMissingFields: ["scope_boundary", "audit_requirement"]
      },
      {
        id: "DEMO-R05",
        topic: "无依据时的保守响应",
        risk: "normal",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-002",
          locator: "§2.2 / bullet 01",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "无法找到充分依据时，系统应提示信息不足，不得自行补充事实。"
        },
        aiDraft: {
          requirement_object: "证据不足的用户请求",
          preconditions: "可用材料不足以支持结论",
          required_action: "提示信息不足并停止补充事实",
          expected_result: "输出不包含无依据断言",
          quantitative_target: null,
          test_or_acceptance_method: "使用无答案样本检查是否明确提示信息不足",
          clarification_questions: []
        },
        aiCompleteness: "complete",
        reviewHints: [],
        suggestedMissingFields: []
      },
      {
        id: "DEMO-R06",
        topic: "敏感材料处理环境",
        risk: "high",
        evidence: {
          status: "bound",
          sourceId: "DEMO-SPEC-002",
          locator: "§4.1 / paragraph 01",
          origin: "独立编写的脱敏合成演示文本",
          excerpt: "敏感材料原则上应在受控环境中处理。"
        },
        aiDraft: {
          requirement_object: "敏感材料",
          preconditions: "材料被识别为敏感",
          required_action: "在受控环境中处理",
          expected_result: "材料不会进入未经批准的处理环境",
          quantitative_target: null,
          test_or_acceptance_method: null,
          clarification_questions: ["哪些材料属于敏感材料？", "受控环境的技术和权限边界是什么？"]
        },
        aiCompleteness: "complete",
        reviewHints: ["敏感材料定义缺失", "受控环境边界缺失", "验收方式缺失"],
        suggestedMissingFields: ["preconditions", "scope_boundary", "test_or_acceptance_method"]
      }
    ]
  };

  root.SOLUTION_SCOPE_DEMO_FIXTURE = fixture;
  if (typeof module !== "undefined" && module.exports) module.exports = fixture;
})(typeof window !== "undefined" ? window : globalThis);
