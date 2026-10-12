# Inspector 能力验证 Tab · Tasks

> **开发子切片**：只增加一个 Tab；「可信物理故障场景一键执行」仍是 DEV-M5 单独未完成任务，本文件不替代其验收。

## 0. Scope
- [x] 0.1 复核现有 Run Inspector 页面和 API，保留原双 Agent Tab、PG Run/Provider/Final Result/SSE、默认模型说明。
- [x] 0.2 明确 UI 场景文字与证明标准；不把 PG Binding 误认为真实 Cube/Worker 通过，不把测试脚本当 HTTP 特权 Runner。

## 1. TDD 与实现
- [x] 1.1 先提交真实 PG 合同负例，覆盖 Catalog/Field/非法 Run/PG Binding/不虚假 PASS/Tab 结构。
- [x] 1.2 在同一 HTML 页面只添加一个顶层「能力验证」Tab；四场景均有使用场景、能力、步骤、证据、限制。
- [x] 1.3 新增只读 Catalog 与 PG 证据 API，采用有限证据字段与明确 `verified=false`；不存在后端特权 Runner 时不得出现假的开始按钮。
- [ ] 1.4 后续可信 Worker/Cube 联合 Gate 真通过之后，接入由受信任后端运行的演示执行器、真实 OS/Cube/Guest 原生证据与终态，不得从无认证页面直接放行特权操作。

## 2. 门禁
- [ ] 2.1 本 Tab 的真实 PG 合同、原 Inspector Black-box、Architecture Guards、Strict OpenSpec 在最终 Head 的 CI 全部 PASS 后，才可合并本 UI 子切片。
- [ ] 2.2 M5 联合实机/Guest Fencing/Production IAM 未通过前，仍保持 OPEN/NO-GO。
