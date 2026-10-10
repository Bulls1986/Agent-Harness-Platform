# 复盘 · 首个最小可运行 Agent Harness 闭环（2026-10-10）

> **范围：OpenSpec `minimal-run-closed-loop` · 本地 LIMITED POC**。**不是生产准入、不是 HC-01/02/03 全部 P0 场景 Accepted**。本复盘与测试结果只陈述真实发生过的证据；GitHub CI 最终验收应以实际 run conclusion 为准。

## 一、起因和验收合同

Architecture ADR-031/032 已将 Hatchet 定为技术执行权威、Harness 定为业务事实/审批/Receipt 终态裁决权威。最初已有 Hatchet 与 AgentRuntime 的**分立 POC**，缺少一个由 Platform Run ID 串起、在 PG 中可核对的真实链路。用户增加了两个必须条件：

1. **PostgreSQL 必须部署在 Docker**：同一 PG 实例创建相互独立的 `hatchet_poc` Engine DB / `harness_poc` Domain Facts DB，不使用 SQLite。
2. **Run Inspector 是必验收交付**：网页提交真实 Run、查看 Pydantic/OpenAI Steps、事件时间线和 Hatchet Binding，重启后从 PG 恢复显示；不建设完整 Portal 或伪造成功状态。

OpenSpec 4/4 规划文件（Proposal/四能力 Specs/Design/Tasks）经 `openspec validate minimal-run-closed-loop --strict` PASS。所有运行代码遵守 `AGENTS.md`、G01–G20、HC-01/02/03、Domain/Recovery/Receipt 不变式。

## 二、实际测试证据（2026-10-10）

| 门禁 | 证据 | 结论 |
|---|---|---|
| PostgreSQL Docker 双库 | `docker compose up -d postgres`；PG healthy；`hatchet_poc` 与 `harness_poc` 均实查存在；PgFacts 表初始化 | **LOCAL PASS** |
| 基础合同先写测试 | `python -B -m unittest poc.closed_loop.test_facts_pg poc.closed_loop.test_inspector_pg -v`，指定 Docker PG URL，**7 tests PASS**，不允许 env 缺失导致 7 skipped 仍宣称 green | **LOCAL PASS** |
| 真实 Hatchet DAG + 两公开 SDK | `docker compose --profile demo run --rm loop`；真实 Embedded v0.110.5 + PG，Pydantic AI → OpenAI Agents SDK，输出分别 `pydantic-sdk-real-run` / `openai-sdk-real-run`；一个平台 Run `loop-58d0a1b9d4e94fc395dfc9c65baaf1f0`，Provider Workflow ID `28ffde83-762e-4c97-8fe6-6889486d312e`，业务 COMPLETED、各 Step 1 Attempt、14 events、外部模型调用 0 | **LOCAL PASS** |
| 浏览器后端真实触发与持久读取 | `docker compose --profile inspector up -d inspector`；`http://127.0.0.1:8765` 返回 200。黑盒调用 `python -B -m poc.closed_loop.verify_inspector_live` 在一个 Run `run-1f9cc8929f534de3b5f273701c59c543` 完成两个真实 SDK，Provider ID `9ab4e1ad-7ef0-416e-9d51-94c6291bc4d0`，**14 events**，one `run.completed`/two `runtime.run.completed` | **LOCAL PASS** |
| 重启 Inspector 后的完整事实查询 | `docker compose restart inspector`，待端口 ready 再执行 `verify_inspector_live --run-id run-1f9cc8929f534de3b5f273701c59c543`；同 Provider/Step/Event 仍可查且 PASS | **LOCAL PASS** |
| Runtime 绑定、零 Sandbox 与权限拒绝 | `python -B poc/runtime_spi/verify_runtime_spi.py`；6 类 Scope/Owner/Fencing/Capability 基础负例 PASS，`no_sandbox_model_run=PASS`；这些是离线适配合同，不证明真实 Cube | **POC PASS / Cube NOT_TESTED** |
| 架构护栏及导航 | `python -B scripts/check_architecture_guardrails.py`：8 views / 9 Mermaid PASS；`python -B -m unittest tests.test_architecture_guardrails`：8 PASS；`python -B poc/verify_repo_navigation.py`：183 links PASS | **LOCAL PASS** |
| CI 一体化真实集成 | [GitHub PR #55](https://github.com/Bulls1986/Agent-Harness-Platform/pull/55) 上的 `closed-loop-poc.yml`；[CI run 38037718378](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38037718378) 全 job SUCCESS：PostgreSQL + 7 tests/8 guards、真实 Hatchet 两 SDK、HTTP Inspector 提交与进程组重启后读取全部通过。另 [Architecture Guard 38037718366](https://github.com/Bulls1986/Agent-Harness-Platform/actions/runs/38037718366) SUCCESS | **CI PASS** |

**避免混淆**：本机单测如果未传 `HARNESS_POC_DATABASE_URL` 会 `skipped=7`；那不是绿灯。本表基于真实 Docker PG 环境的非 skipped 7 项结果。

## 三、测试先行：从失败到修正

1. **Run Inspector 先写 HTTP 合同测试**，第一次执行 `ModuleNotFoundError: poc.closed_loop.inspector`（Red）；只实现 `create_app`、PG 查询 API 和纯静态 HTML，7 项 PG/API 测试全部转绿（Green）。没有引入 React、认证或第二套 Worker Scheduler。
2. **先运行 PG 负例，再修事件命名**：原来的 `runtime.run.completed` 被原样记为 `run.completed`，导致两个 SDK 子调用加一个平台终态合计出现三条同名完成事件。修正为 `runtime.*` 命名空间，只有真正的 Domain `complete()` 发出一次 `run.completed`。真实 14 条 Domain Event 已复验。
3. **先验证未知 ACK 断言，再保持 Fail Closed**：模拟 `DISPATCHING→BLOCKED_UNKNOWN`，后续 `dispatch` 强制拒绝，而不是以超时推测 Provider 未执行。真实 Hatchet Provider-side 去重/ACK-loss 查找**尚未验证**。
4. **先确立 Contract，再缩减第一轮 Scope**：Model-only 任务不得额外申请 Cube；Runtime 直接调用真实公开 SDK，但不把 buffered `delta` 冒充真实流式 Token。

## 四、故障与改进措施

| 实际问题 / 根因 | 当前处理 | 固化为后续开发原则 |
|---|---|---|
| 初版 OpenSpec 只覆盖三个技术能力，遗漏用户明确要求的可视化验收 | 增加第四项 `run-inspector` Spec、对应 Design/API/Tasks 与页面黑盒门禁，重新 strict validate | **验收体验属于需求合同**，不能开发结束才临时补 UI |
| Docker Hub Token 端点连接被重置，默认 `python:3.12-slim` 无法构建 | 添加可配置的可信 Python Base Image + pip Index；本地使用已缓存 `mcr.azure.cn/azure-functions/python:4-python3.11` 和镜像源，镜像实际 BUILD PASS | 基础镜像/依赖安装路径要可复现；回退不允许降低 PG/SDK 的真实性，也不得在仓库固定个人私服或 Secret |
| Hatchet Embedded Sidecar 首次下载耗时明显，并随临时容器 `--rm` 丢失 | 使用 `harness_hatchet_sidecar` 命名 Docker volume 缓存 **binary-only** 到 `/home/.hatchet/embedded`（不缓存 profiles/Token） | POC 环境应复用大体积二进制，减少误判测试运行性能 |
| CI 后台 `uvicorn`、Hatchet 子进程有挂住 shell `wait` 的风险 | Linux CI 改为 `setsid` 独立进程组，先 TERM、限时清理再 KILL；避免无界 `wait` 导致测试流程死锁 | **测试自身**也要具有超时、进程组清理和错误日志，不得用 CI Hang 充当引擎失败结论 |
| PostgreSQL Actor 与 Hatchet Engine 在两个独立 DB 中，不可能假设跨库原子 | Harness 内 Run+Steps+Outbox 同事务，Provider Workflow ID 独立 Binding；ACK 不确定状态显式 BLOCKED_UNKNOWN | 不做跨库 2PC、不造第二套 Durable Engine；真实 Reconciling 必须独立追加测试 |
| CI/本地绿灯易被误解为生产安全 | 所有输出显式显示 NOT_TESTED Gate（Cube、Token SSE、外部 Receipt、100 并发） | 单场景 PASS 不得推升整个平台 Accepted |

## 五、工程行为约束（今后默认执行）

- **测试先行**：每个可验收功能先写正例/负例合同和失败断言，再实现最小行为；单测不能覆盖 Engine/DB 时再加真实故障注入和端到端证据。
- **架构先于代码便利**：Domain 不 import Hatchet；Hatchet 不写平台终态；Provider ID 不能充当平台主键；Sandbox/Host Shell 不能混用；未知 SideEffect 无 ACK 不能被自动重放。
- **每项任务通过才勾选**：OpenSpec Tasks 与真实 CI/local 命令/日志/Run ID 对齐。跳过的测试、Mock 后端和尚在排队的 CI 均不能算 Passed。
- **复盘可追踪**：记录可复现命令、实际失败、根因、修复、证据、遗留风险；不要把耗时/网络环境限制误当 SDK 架构缺陷。
- **CI + 本地双重证据**：本地 Docker 的完整实际用户路径与 GitHub Actions 的 clean runner 必须分别核验；CI 阶段全部成功之后才合并主干。

## 六、仍需单独 P0 集成验收（不属于本模型闭环）

- HC-02：Provider 原生 Idempotency/Lookup + ACK 丢失主动 Reconciliation；并发 Outbox Dispatcher/Inbox 去重；真实非幂等 Tool Intent/Receipt 对账。
- HC-03：Hatchet Worker A→B + 真 Cube Session/Workspace/Lease/Fencing，同 Scope reconnect，旧 Owner 拒绝，OpenCode FS/Shell/PTY/Git 安全隔离。
- 真正 Token SSE + Last-Event-ID、durable WAITING_APPROVAL/INPUT、真实模型 LiteLLM 通路、100 Active Runs 资源测量与 PDLC M0–M4 迁移。

**最终证据结论：最小模型闭环本地成功，GitHub CI run 38037718378 成功；本项目仍处于集成 POC（LIMITED GO），不等于生产可用。**