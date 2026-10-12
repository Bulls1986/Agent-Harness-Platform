# Inspector 能力验证 Tab · Tasks

> **开发子切片**：保留两个 Tab；Worker Takeover 已完成服务端受控执行与实机 API Gate，其余两个场景仍只读，本文件不替代生产门禁。

## 0. Scope
- [x] 0.1 复核现有 Run Inspector 页面和 API，保留原双 Agent Tab、PG Run/Provider/Final Result/SSE、默认模型说明。
- [x] 0.2 明确 UI 场景文字与证明标准；不把 PG Binding 误认为真实 Cube/Worker 通过，不把测试脚本当 HTTP 特权 Runner。

## 1. TDD 与实现
- [x] 1.1 先提交真实 PG 合同负例，覆盖 Catalog/Field/非法 Run/PG Binding/不虚假 PASS/Tab 结构。
- [x] 1.2 在同一 HTML 页面只添加一个顶层「能力验证」Tab；四场景均有使用场景、能力、步骤、证据、限制。
- [x] 1.3 新增只读 Catalog 与 PG 证据 API，采用有限证据字段与明确 `verified=false`；不存在后端特权 Runner 时不得出现假的开始按钮。
- [x] 1.4 Worker Takeover 受控场景执行子切片：服务端授权、固定 B03 运行器、真实 OS/Cube/Guest 证据与终态，已获新 Inspector API-to-Cube 实机 PASS；详见 docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md。Cube-only 与 Tool Receipt 独立执行、生产 IAM 和全场景操作台均不包括。
- [x] 1.4a B03 受控执行 API 与场景卡交互开发：默认只读，显式服务端 opt-in 与操作员鉴权、固定 Runner，不暴露 Shell 参数；独立证据查询，PG 观察不标记 verified。**证据**：docs/retrospectives/DEV_M5_INSPECTOR_TRUSTED_SCENARIO_20261012.md。HTTP→Cube E2E 已由 1.4b-1 单独实测，其他两个场景仍 OPEN。
- [x] 1.4b-1 真实 Linux/Hatchet/PG/Cube 的 Inspector HTTP 授权触发 Worker Takeover 联合 Gate、持久证据和新服务实例重读 PASS；Evidence proof-c7b82a4c3c6d4a4d963e5aee8fbf52e5，退出码 0。
- [ ] 1.4b-2 Cube-only Workspace 和非幂等 Tool Receipt 各自可信执行合同与实机验证，不能复用 Worker Takeover 的 PASS。

## 2. 门禁
- [x] 2.1 本 Tab 的真实 PG 合同、原 Inspector Black-box、Architecture Guards、Strict OpenSpec 均通过，新增 TDD 失败与整改已复盘：`docs/retrospectives/INSPECTOR_CAPABILITY_TAB_20261012.md`。完成文档后最终 Head CI 仍须复验再合并。
- [ ] 2.2 M5 联合实机/Guest Fencing/Production IAM 未通过前，仍保持 OPEN/NO-GO。
