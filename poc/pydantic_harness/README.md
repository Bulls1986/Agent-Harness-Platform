# Pydantic AI Harness + 可选 E2B Sandbox：高密度 Session POC

> 2026-10-09，候选专项。当前仅有**无模型、无网络**的本机基线。
> 不是 Pydantic Harness 的生产选型或 Cube 真机 GO。

## 验证目标

选择 Pydantic AI Harness 是为了缩减全新专业 Agent 的胶水代码，
不要求迁移既有 OpenCode 2 Coding Agent，也不改变 Workflow Task Facts、
RecoveryPoint、Approval、SandboxProvider SPI 的归属。

### 已完成的独立实测

| 测试项 | 实测版本与结论 |
|---|---|
| SDK 导入 | `pydantic-ai-harness==0.54.0` / `pydantic-ai-slim==2.54.0` PASS |
| 一个 Agent 实例承载多个 Run | 20 个并发 `Agent.run`，确定性 FunctionModel，无额外独立 Agent 进程，PASS |
| 不需要 Sandbox 的 Agent | 不加载 Sandbox 能力，20 次 Run PASS |
| Coder 配合可选 Sandbox | `E2BSandbox() + Coder(repo_context=False, sub_agents=False)` 构造及无工具 Run，PASS |
| 每 Run 明确 WorkspaceRef | 同一个 Coding Agent，两个不同 `WorkspaceRef(provider='e2b', ...)`，离线 Run PASS |
| 不使用执行工具时惰性连接 | 通过 SDK `AsyncSandbox.create/connect` 反向监控，创建/连接调用为 0，PASS |
| 同一 Agent 并发 Run 的真实工具调用 | Linux-only：两个独立 `LocalWorkspaceBackend`，真实 write_file/read_file/shell 工具三段链；新增 CI Gate，初次结果待确认 |
| Jev / TypeSafeModel | Python API 可导入；无 TypeSafe 凭据、未完成决策质量验证 |
| Windows 本地执行 `LocalWorkspace` | **NOT SUPPORTED（本机实测）**：`LocalWorkspaceBackend` 因需要 POSIX 进程组超时/终止语义抛 `NotImplementedError`；可使用 Linux 或远程 E2B/Cube |
| E2B 文件/Shell / Cube / Temporal | **未实测**，不可从以上结果推断 |

```bash
python -m pip install "pydantic-ai-harness[e2b]==0.54.0" "pydantic-ai-slim[typesafe]==2.54.0"
python poc/pydantic_harness/verify_offline_density.py
python poc/pydantic_harness/verify_local_tool_routing_posix.py  # Linux / POSIX
```

代码运行在一个普通 Python 进程中，通过 FunctionModel 伪模型回答。
测试时把 E2B 官方 SDK 的 `AsyncSandbox.create/connect` 替换为立即报错
的断言，以确保没有创建或访问实际 Sandbox。验证的主要是公开 Agent/
Workspace 接口行为，不代表已测真实资源消耗或隔离。

## 下一阶段共同验收（Cube 优先）

对 Pydantic AI Harness 和 OpenAI Agents SDK 使用**同一个**真实 Cube
E2B Endpoint、Template、数据面、Sandbox 生命周期：

1. 先用标准 E2B SDK 创建 Sandbox，验证 `commands.run`、文件操作和重连。
2. 将已有 Cube Sandbox ID 作为 Pydantic `WorkspaceRef` 传给 Agent，
   验证它能执行文件读取/命令，而不是在 E2B Cloud 新建。
3. 将同一个 Sandbox ID 交给 OpenAI Agents SDK E2B Client，验证双方
   接力；OpenCode 2 保留独立 Coding Runtime，测试目标相同。
4. 记录公开 API Adapter 数量、创建/重连/释放调用、进程/RSS 和恢复行为；
   不能只比较 API 方法名。
5. 没有可访问 Cube 时一律 `BLOCKED`，不把本机 Docker 的 PASS 换成 Cube PASS。

架构候选：[多 Harness 技术选型评估](../../docs/references/MULTI_HARNESS_TECH_SELECTION_20261009.md)；
真实 Cube 合约入口：[`verify_cube_e2b.py`](../opencode_sandbox/verify_cube_e2b.py)。