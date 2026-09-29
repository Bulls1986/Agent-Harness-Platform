# Coding Execution / Sandbox 架构讨论

> 状态：讨论参考  
> 日期：2026-09-29  
> 目标：记录 Agent Harness Platform 在 Coding 场景下的本地隔离执行、远程弹性执行、Provider 边界与生命周期设计。

## 1. 核心结论

Coding Harness 的生产执行路径不应默认裸跑在 Agent Runtime 宿主机上。

正式约束：

> **Coding Execution 必须进入隔离执行环境。Local Sandbox 是基线容量，Remote Sandbox 是弹性与特殊资源能力；裸 LocalShell 只保留给开发调试或显式低风险管理任务。**

因此平台执行链建议为：

~~~text
Harness / Workflow
      ↓
ExecutionScheduler
      ↓
SandboxProvider SPI
      ├─ CubeSandboxProvider   ← 生产默认；可连接本地或远程 Cube 集群
      ├─ DockerProvider        ← 开发、兼容、fallback
      ├─ K8sProvider           ← 后续可选
      └─ HyperlightProvider    ← 小型不可信函数/WASM/CodeAct 类场景
~~~

## 2. MAF 与执行隔离的边界

MAF/Harness Runtime 本身主要负责 Agent loop、Workflow、Context、Session、Tool 调度与异步 I/O。它不应该成为 Coding workload 的资源承载层。

需要区分：

~~~text
Agent logical concurrency
≠ OS process concurrency
≠ Sandbox concurrency
≠ Heavy build/test concurrency
~~~

模型请求、MCP、数据库、事件流等大量时间处于 I/O wait；真正显著消耗 CPU、内存与 I/O 的通常是外部执行：

- pnpm/npm/yarn build
- tsc
- Maven / Gradle
- pytest / JVM tests
- Playwright / Chromium
- Electron / electron-builder
- Docker build
- 大仓库索引与静态分析

因此 MAF 只负责发出 ExecutionRequest，并消费 ExecutionResult/Evidence；实际 shell/git/browser/build/test 必须进入 Sandbox/Data Plane。

## 3. 本地隔离是生产默认要求

生产 Coding Harness 不采用：

~~~text
MAF process
  ↓
host shell
  ↓
直接执行用户/Agent 命令
~~~

而采用：

~~~text
MAF / Harness
  ↓
ExecutionRequest
  ↓
Local Sandbox
  ↓
workspace
  ↓
build / test / browser / git
~~~

本地隔离至少需要控制：

- 独立 filesystem/workspace
- CPU limit
- memory limit
- PID/process limit
- timeout/cancellation
- network policy
- secret injection
- writable/readonly mount
- cleanup
- audit/evidence

## 4. SandboxProvider SPI

平台领域模型不绑定 E2B、Docker、CubeSandbox 或 K8s。

建议接口输入：

~~~yaml
execution_request:
  run_id: run-xxx
  step_id: step-xxx
  environment: coding-node24:1.3
  workspace: ws-xxx

  resources:
    cpu: 2
    memory: 4Gi
    disk: 20Gi

  isolation:
    level: microvm
    network: restricted

  lifecycle:
    persistence: session
    idle_policy: pause
    timeout: 20m
~~~

Provider 返回统一结果：

~~~yaml
execution_result:
  status: succeeded
  exit_code: 0
  stdout_ref: artifact://...
  stderr_ref: artifact://...
  evidence:
    - test-report
    - git-diff
  environment_fingerprint: envfp-xxx
~~~

## 5. Local 与 Remote 的职责

### Local Sandbox

目标：

- 企业数据不离开内网
- 承担稳定 baseline capacity
- 低单位成本
- 低网络延迟
- 可与企业 IAM、Registry、Artifact、Secret 体系直接集成

### Remote CubeSandbox Cluster

目标：

- 本地 CubeSandbox 容量不足时 burst
- 高 CPU / 高内存特殊规格
- 临时大规模并发
- 特殊隔离需求
- 跨区域/临时环境

远程弹性仍使用 CubeSandbox，只是连接不同 cluster/endpoint。E2B 兼容能力只作为 SDK/API interoperability contract，不代表平台依赖 E2B Cloud。

## 6. Sandbox 生命周期

建议支持三类生命周期。

### Ephemeral

~~~text
create → execute → verify → collect evidence → destroy
~~~

适合 CI、单次修复、一次性分析。

### Session

~~~text
create → execute → idle → pause → resume → ... → destroy
~~~

适合交互式 Coding Session。

### Snapshot / Branching

~~~text
checkpoint S0
   ↓
execute
   ↓
verify fail
   ↓
rollback S0
   ↓
replan
~~~

或从同一个 checkpoint fork 多条执行路径，用于候选方案比较。

## 7. Hyperlight 的定位

Hyperlight 不应作为通用 Coding Environment 的主路径。

其模型更接近：

~~~text
Host
  ↓
Hyperlight microVM
  ↓
Guest binary / WASM / controlled runtime
~~~

它不天然提供完整 Linux development workstation 语义，不适合作为 git clone、pnpm install、Maven build、Playwright、Electron、Codex/OpenCode 完整工作区的统一基础。

建议定位为：

- 小型不可信代码
- Function execution
- WASM
- CodeAct
- 插件执行

通用 Coding Sandbox 仍优先 OCI + 完整 Linux user space。

## 8. 两层 Control Plane

若采用 CubeSandbox 等 Sandbox 基础设施，需要避免把两层控制面混为一体。

~~~text
Agent Harness Control Plane
Run / Plan / Step / Policy / Verify / Replan
              ↓
       ExecutionScheduler
              ↓
Sandbox Infrastructure Control Plane
Sandbox create / schedule / pause / resume / snapshot
              ↓
Sandbox Data Plane
MicroVM / filesystem / network / process
~~~

Sandbox 平台只决定“在哪台执行节点运行 Sandbox”，不拥有 Harness 的业务 Run 状态机。

## 9. POC 必测

1. 同一 Workflow 在不同 SandboxProvider 间切换，不修改业务 Workflow。
2. Coding 命令默认不能逃逸到 Agent Runtime 宿主机。
3. timeout/cancel 能通过 SandboxProvider 的公开能力传播并终止/回收可终止资源；ACK 不等于 TERMINATED，具体语义服从 CANCELLATION_TIMEOUT_PROPAGATION.md。
4. workspace、network、secret、mount 策略可审计。
5. Provider 故障不会导致 Run/Plan/Step 状态丢失。
6. Sandbox destroy/pause/resume 事件映射为统一 Harness Event。
7. Sandbox crash 后能基于 Step/Checkpoint 策略恢复。
8. 本地 Provider 与远程 Provider 的 ExecutionResult/Evidence schema 一致。

## 10. 当前讨论结论

- LocalShell：开发/显式低风险 fallback，不作为生产默认。
- Docker/containerd：成熟、兼容性高，保留为开发/fallback Provider。
- Hyperlight：专用轻量不可信代码执行，不作为完整 Coding Sandbox。
- CubeSandbox：进入生产默认 Sandbox 第一候选 POC；本地与远程弹性均使用 CubeSandbox cluster。
- E2B：只保留兼容 API/SDK 语义，不作为独立 Sandbox Provider 或生产依赖。

最终生产默认 Provider 必须经过容量、隔离、稳定性、升级与恢复 POC 后确定。


## 11. 方案演进记录

本轮讨论的关键收敛过程如下：

1. **资源模型校正**：最初按“每个 Coding Task 一个重 Sandbox”估算过于保守；结合现有 OpenCode 使用经验，确认 Agent Session 本身不是主要资源瓶颈，build/test/browser 才是重资源区。
2. **生产隔离收紧**：虽然 LocalShell/Worktree 很轻，但生产 Coding Harness 明确要求本地隔离执行，因此 LocalShell 不作为默认生产路径。
3. **Hyperlight 重新定位**：Hyperlight 的 Guest/WASM 模型适合轻量不可信代码，但不适合完整 Linux Coding workstation，因此不承担主 Sandbox。
4. **环境一致性成为硬约束**：本地与远程执行必须由同一 Environment Profile / immutable OCI digest 派生，增加 Environment Registry 与 conformance test。
5. **E2B 自托管路线不进入最终 Provider 集**：讨论过 E2B Cloud 与本地/self-host 形态，但最终不引入 E2B Cloud 或独立 E2B Provider。
6. **CubeSandbox 收敛**：CubeSandbox 既满足本地自托管 MicroVM，又提供 E2B-compatible API/SDK，因此生产 Provider 收敛为 CubeSandbox；Local/Remote 只是不同 Cube cluster。
7. **最终拓扑**：Local CubeSandbox = baseline capacity；Remote CubeSandbox = burst capacity；Docker = dev/fallback；Hyperlight = specialized execution。
