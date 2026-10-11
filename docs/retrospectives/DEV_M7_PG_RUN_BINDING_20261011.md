# DEV-M7 PostgreSQL Run 归属授权子切片复盘（2026-10-11）

## 范围与权威

为正式只读 API 提供可追溯的 PostgreSQL Run 项目归属和发起者身份事实；数据库为 Harness Domain authority，Hatchet 的技术 Workflow ID 不承担授权依据。不修改 Accepted ADR/HC/G01–G20，不接入任何私有消费者数据。正式企业 IdP/Policy 接入、授权 SSE 与 OSS Artifact、Conversation/Turn、生产 GO 均不在本次验收范围。

## Red → Green（真实 PostgreSQL）

1. 首先增加 `poc/platform_access/test_pg_reader.py` 和强制 PostgreSQL 16 的 PR CI job。首次 [Red CI 38139768796](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38139768796) 在真实数据库启动成功后因 `ModuleNotFoundError: poc.platform_access.pg_reader` 失败；原有无数据库单测正常。
2. 增加 `harness_run.project_scope`、`initiator_principal_id` 与 `PgRunReader`，真实 [Green CI 38139867680](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38139867680) 成功。
3. 增加直接 SQL 改变 Run 归属及历史 Run 原地补绑的负例，[Red CI 38139953423](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38139953423) 确认 PostgreSQL 原先未禁止 UPDATE。
4. 加入数据库触发器 `harness_run_owner_immutable` 后，[Green CI 38140021577](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38140021577) 真实 PostgreSQL **5/5 PASS**（0 skipped），原有授权 HTTP 单测 **8/8 PASS**。
5. [Architecture Guard CI 38140021573](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38140021573) SUCCESS。独立 PG/Hatchet/Inspector [闭环回归 workflow 38140021579](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38140021579) **SUCCESS**；与本轮 PgFacts Schema 变更兼容。

## 验证行为与架构约束

- 带有项目/发起者归属的 Run 插入后可跨 PostgreSQL 连接再次读取，HTTP detail 与 events 允许读取且游标单调。
- 不同项目、伪造 Headers、权限撤销、无身份、未知 Run、历史无作用域 Run 均不得泄漏 Run Payload。
- 新 Run 的两个归属字段必须同时非空；数据库直接修改既有项目、发起者或提升历史无 Scope Run 会被拒绝，避免读取授权与载荷查询之间的 Owner 改绑。
- 旧本地 Inspector 仍使用无归属 POC Run；不通过正式授权入口把这些历史 Run 伪造迁入项目。
- PG 模型仍是 POC schema 而非正式迁移/上线准入；没有将外部 IAM、Policy Registry、OSS、MCP Governance、租户或多余调度器引入 Harness。

## 未关闭 Gate 与经验

DEV-M7 完整 Task 0.1/0.2 与 1.1～2.3 仍 OPEN：真实 Gateway/IAM 与当前 Policy、会话 Conversation/Turn、SSE 中途撤权/重放、ArtifactRef/OSS、UI 与用户级验收尚缺。M3 的真实 Replan v2、M4 Receipt UNKNOWN、M5 Cube Worker A→B 等门禁不受此切片影响。

经验：授权归属必须来源于持久事实，而不是模型输出、传入 Headers 或 Provider ID；历史无归属数据不默认补绑。HTTP 授权检查之前拒绝缺 Scope 的 Run，同时在数据库端阻止原地改绑，避免跨查询竞态。坚持真实 PG 与错误路径的 Red→Green 证据。
