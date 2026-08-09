# SolutionScope Review → Decision v2

> **静态两页审核原型。** 页面不调用模型；既可使用公开合成 fixture，也可本地导入 Skill 生成的审核包。

## 要回答的问题

当一个 AI 候选版本已经通过结构合同、但仍可能存在语义完整性误判时，用户能否在同一个最小流程中：

1. 回看来源短摘录与 AI 字段；
2. 修正 `complete / partial / incomplete / unknown`；
3. 记录缺失字段和待澄清问题；
4. 将人工审核转化为结构、证据、语义三层门禁；
5. 明确选择阻断或有限放行至下一轮人工评测。

当前采用固定的“队列＋证据/字段＋人工审核”布局。Skill 在最终结构门禁通过后生成 `final/ui_review_payload.json`，页面通过右上角“导入审核包”读取该文件，并在两页之间保留当前会话。

## 数据与结论边界

- `fixture.js` 中的短摘录和 AI 字段均为作者独立编写的**脱敏合成公开演示 fixture**，不复制客户、课题组、ISO 或本地受限 Pilot 原文。
- 导入文件只写入当前标签页的 `sessionStorage`，不会上传；审核状态按 `fixtureId` 隔离保存在本地。关闭标签页后导入内容失效。
- 受限材料生成的 `ui_review_payload.json` 只能在本地审核，不得上传至公开 Pages 或仓库。
- 页面展示的历史 `A0 37 → B1 0` 严格合同错误和 `18/20` 过度 `complete` 风险，只是项目已经允许对外陈述的聚合开发观察。
- 聚合观察来自本地受限、单一来源族开发样本，不是正式准确率、语义提升、泛化、用户验证、效率或 ROI。
- “有限放行”只表示进入下一轮受控人工评测，不代表上线、部署或生产批准。

## 运行

可以直接双击 `index.html` 打开。推荐从项目根目录运行：

```bash
python3 -m http.server 8000 --directory SolutionScope/prototype/review-decision-v2
```

然后访问：

- `http://localhost:8000/`：语义审核页；
- `http://localhost:8000/decision.html`：门禁与阶段决策页。

审核和决策保存在当前浏览器 `localStorage`，键名按审核包隔离：

```text
solutionscope.reviewDecisionV2.v1:<fixtureId>
```

为兼容部分浏览器直接打开 `file://` 页面时对 `localStorage` 的限制，同一标签页导航还使用 `window.name` 作为降级备份；推荐使用本地 HTTP 以获得最稳定行为。

页面右上角“重置本地审核”清空当前审核包的状态，“恢复合成演示”退出导入包。审核页和决策页均可导出 JSON。

## 最小自测

无需安装依赖：

```bash
node SolutionScope/prototype/review-decision-v2/smoke_test.js
```

自测检查：

- fixture 与导入审核包合同；
- 来源定位与合同字段完整；
- 初始门禁和摘要逻辑；
- 按审核包隔离的 localStorage 状态规范化；
- 人工修正后语义门禁变化；
- 审核与决策导出边界；
- 两个 HTML 页面和必要脚本引用。

## 原型结论记录

尚未进行独立用户试用。完成一次真实试用后，应记录：用户能否独立发现高风险 `complete`、完成修正并作出正确阶段决定。若流程成立，将审核交互吸收到后续正式产品；若不成立，优先修改信息层级，不扩展模型、RAG、多 Agent、上传、权限或集成功能。
