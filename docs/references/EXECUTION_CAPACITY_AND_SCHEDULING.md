# Coding Execution 容量模型与调度

> 状态：讨论参考  
> 日期：2026-09-29

## 1. 问题定义

100 个 Agent 用户不等于 100 个重计算任务，也不等于 100 个永久 Sandbox。

真正需要容量规划的是：

> **同一时刻正在执行 build/test/browser/compiler 等重资源操作的任务数。**

因此平台必须将 Agent Capacity 与 Execution Capacity 分开。

## 2. 两套容量指标

### Agent Capacity

- active sessions
- active runs
- concurrent model calls
- SSE connections
- MCP/HTTP I/O
- context/session state

### Execution Capacity

- active sandboxes
- active shell commands
- concurrent compilers
- concurrent test jobs
- browser slots
- heavy build slots
- CPU
- memory
- disk IOPS
- workspace/cache bandwidth

Agent Runtime 可以维持大量逻辑并发，但 Coding Execution 会成为资源热点。

## 3. Coding Harness 更接近 CI workload

### 3.1 OpenCode 现实校验

现有 OpenCode 使用经验说明，Coding Agent 不应按“每个用户永久绑定一个 VM/Sandbox”的模型估算容量。更接近实际的是 shared runtime/session + workspace/worktree + 按需 subprocess：用户在等待模型、阅读、搜索、编辑时几乎不消耗重计算资源，只有进入 compile/build/test/browser 等步骤时才形成明显硬件压力。

因此容量模型以 active heavy execution 为主，而不是 registered users、session count 或 Agent logical run count。

典型重资源任务：

~~~text
mvn test
gradle build
pnpm build
tsc
pytest
playwright
electron-builder
docker build
~~~

因此 Coding Harness 的资源模型应借鉴 CI/Build Farm，而不是聊天服务。

## 4. ExecutionScheduler

ExecutionScheduler 是平台独立组件，职责包括：

- admission control
- resource class
- priority
- quota
- fair scheduling
- local/remote placement
- queue SLO
- timeout/cancel
- backpressure
- spillover/burst

它不执行命令，只决定 ExecutionRequest 应进入哪个容量池。

## 5. Resource Class

不应把所有 shell command 当成相同重量。

| Class | 示例 | 典型特征 |
|---|---|---|
| LIGHT | git status / grep / small lint | 短时、低 CPU |
| MEDIUM | targeted test / tsc / module build | 中等 CPU/内存 |
| HEAVY | full build / full regression / Playwright / Electron | 高 CPU/内存/I/O |
| SPECIAL | GPU / privileged / browser farm | 特殊资源 |

可进一步采用 weighted slot：

~~~text
LIGHT  = 1
MEDIUM = 2
HEAVY  = 4
~~~

Scheduler 按资源预算而不是简单 task count 控制并发。

## 6. Admission Control

错误模式：

~~~text
本地资源满
→ 所有新任务继续进入 FIFO
→ queue 持续增长
→ interactive task 被 heavy task 堵住
~~~

目标模式：

~~~text
ExecutionRequest
      ↓
Resource Estimator
      ↓
Admission Control
      ↓
Scheduler
   ┌───────┬─────────┐
   ↓       ↓         ↓
Local    Remote     Queue
有容量    burst     最后保护
~~~

Queue 应是最后一道保护，不是默认路径。

## 7. Local Baseline + Remote Burst

建议：

~~~text
Local Sandbox Cluster
= baseline capacity

Remote CubeSandbox Cluster
= burst capacity
~~~

触发 burst 的条件可以包括：

- local CPU / memory pressure
- local sandbox slots exhausted
- queue_wait_p95 超阈值
- task requires larger resource profile
- data/policy permits remote execution

Scheduler 不需要等机器完全打满才切换。

## 8. 队列隔离

至少分：

- interactive queue
- normal verification queue
- heavy verification queue
- background queue

避免长时间 full E2E 堵住 git diff / lint / targeted test。

## 9. Verify 分层

Coding Agent 不应每次修改后都跑全量回归。

~~~text
Edit
 ↓
Fast Verify
 - targeted test
 - lint
 - typecheck
 ↓
Candidate Complete
 ↓
Full Verify
 - full build
 - regression
 - e2e
~~~

这可以显著降低 heavy workload 的并发峰值。

## 10. Queue SLO

初期可用工程基线，不作为最终 SLA：

- interactive queue p95 < 5s
- normal queue p95 < 15s
- heavy queue p95 < 60s

POC 需用真实 workload 修正。

核心监控：

- queue_wait_ms
- execution_duration
- active_by_resource_class
- local_capacity_utilization
- remote_burst_count
- sandbox_create_latency
- sandbox_resume_latency
- scheduler_reject_count
- timeout/cancel count
- CPU/memory/IO saturation

## 11. 100 用户容量理解

正确理解：

~~~text
100 users
   ↓
100 logical sessions/runs
   ↓
部分等待 LLM / I/O
   ↓
少量同时进入 build/test
~~~

容量规划应围绕“同时 heavy execution 数”进行压测，而不是按用户数静态分配一人一台 Sandbox。

## 12. POC 压测场景

至少模拟：

1. 100 logical sessions，低执行负载。
2. 20~30 concurrent coding runs。
3. 多个 HEAVY build 同时开始。
4. 本地 CPU/Memory 人工压到高水位。
5. 本地 CubeSandbox capacity exhaustion 后切换 Remote CubeSandbox cluster。
6. burst provider 不可用时 backpressure/queue。
7. heavy queue 饱和时 interactive queue 仍满足 SLO。
8. cancellation 后资源在可接受时间内释放。
9. pause/resume 后资源配额正确归还。
10. Scheduler 重启后队列/运行状态不失真。

## 13. 当前结论

> **Agent Runtime 的逻辑并发不是主要硬件风险；Coding Execution 才是重资源区。**

因此资源治理重点应放在 ExecutionScheduler、Sandbox capacity、resource class、queue SLO 和 burst，而不是简单限制 MAF session 数。
