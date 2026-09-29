# CubeSandbox 作为本地 Agent Sandbox 的候选评估

> 状态：讨论参考 / POC 候选  
> 日期：2026-09-29  
> 候选项目：https://github.com/TencentCloud/CubeSandbox

## 1. 评估背景

平台已经形成以下执行层约束：

- Coding Execution 必须隔离。
- 本地 Sandbox 承担 baseline capacity。
- 远程 Sandbox 承担 burst capacity。
- Local/Remote 环境需要同源、可版本化。
- Sandbox Provider 不得进入 Harness 领域模型。
- 需要快速 create/destroy、pause/resume、snapshot/rollback。
- 需要支持多节点与资源调度。

在这些约束下，CubeSandbox 与目标具有较高匹配度，值得进入第一轮 Sandbox POC。

## 2. 当前仓库确认的核心能力

截至 2026-09-29，CubeSandbox 仓库公开资料显示：

- RustVMM + KVM MicroVM。
- 每个 Sandbox 使用独立 Linux kernel。
- E2B-compatible REST/SDK 接口。
- 单节点与多节点部署。
- OCI image → template。
- template 包含 rootfs、sandbox config 与预热后的 MicroVM snapshot。
- CubeMaster 负责集群调度。
- Cubelet 管理节点内 Sandbox 生命周期。
- create/run/pause/resume/snapshot/destroy。
- CubeCoW snapshot/clone/rollback。
- AutoPause/AutoResume。
- v0.7 增加基于 S3 的跨节点 pause/resume / snapshot 路线，其中部分能力仍应按 preview 对待。
- eBPF 网络隔离与 policy。
- L7 egress security proxy。
- credential injection，避免 secret 直接进入 Sandbox。
- Kubernetes 与腾讯云 Terraform 部署路线。
- ARM64 支持；部分虚拟化能力受具体宿主条件限制。

这些能力均需在企业实际环境中重新验证，不能直接以 README benchmark 作为生产 SLA。

## 3. 架构映射

~~~text
Harness Control Plane
Run / Plan / Verify / Replan
        ↓
ExecutionScheduler
        ↓
CubeSandbox
        ↓
CubeAPI → CubeMaster → Cubelet → CubeShim/Hypervisor → MicroVM
~~~

两个 Control Plane 职责不同：

- Harness：业务运行状态、策略、验证、重规划。
- CubeSandbox：Sandbox 节点选择、资源与生命周期。

## 4. 对当前方案的影响

原讨论路线：

~~~text
Local Docker
+
E2B Cloud
~~~

调整为优先 POC：

~~~text
Local CubeSandbox
+
Remote CubeSandbox
~~~

Docker 降级为开发环境、兼容 fallback 与 POC 对照组。Hyperlight 保留为小型不可信代码执行的专项 Provider。

## 5. OCI / Template 一致性

CubeSandbox 使用 OCI image 作为 Template 构建输入：

~~~text
OCI Image
   ↓
rootfs
   ↓
临时 MicroVM boot
   ↓
readiness probe
   ↓
filesystem + memory snapshot
   ↓
Cube Template
~~~

因此可以与远程 E2B 共享 Environment Profile 的 OCI source：

~~~text
                 immutable OCI digest
                     /          \
                    /            \
          Cube Template      E2B Template
~~~

同一 OCI digest 不意味着两个平台生成的 VM snapshot 字节完全相同；平台要求的是 toolchain、filesystem、runtime contract 与验收结果一致。

## 6. 性能价值

CubeSandbox 仓库公开 benchmark 宣称：

- 裸机单并发创建低于 60ms。
- 50 并发创建平均约 67ms。
- P95 约 90ms。
- P99 约 137ms。
- Sandbox virtualization overhead 低于 5MB（特定 benchmark 条件）。

这些值只作为 POC 参考，不作为本项目生产承诺。

必须特别区分：

> 低 virtualization overhead ≠ Coding workload 只占少量内存。

真正的 JVM、Node、Chromium、编译器仍按实际 workload 消耗 CPU/RAM。

## 7. 为什么比纯 Docker 更值得 POC

相对普通 Docker Sandbox，它提供：

- MicroVM 级独立 kernel
- 更强租户隔离边界
- 快速 template restore
- snapshot/clone/rollback
- auto-pause/resume
- 更完整的 Agent Sandbox 网络安全能力
- E2B API compatibility
- 内建多节点 Sandbox scheduler

这减少了平台自行拼装 sandbox orchestration/security/lifecycle 的工作量。

## 8. 本地基线与远程弹性统一使用 CubeSandbox

企业本地硬件仍是有限资源，因此保留 Local/Remote 两级容量池，但两级均使用 CubeSandbox。

~~~text
ExecutionScheduler
      │
      ├─ Local CubeSandbox
      │     baseline
      │
      └─ Remote CubeSandbox
            burst
~~~

当出现 local resource saturation、queue wait 超 SLO、特殊 CPU/memory profile 或临时并发峰值，且 Policy 允许远程执行时，切换到 Remote CubeSandbox cluster。

E2B 不进入 Provider 列表。CubeSandbox 的 E2B-compatible API/SDK 只作为兼容协议价值，用于降低客户端/生态适配成本。

## 9. E2B Compatibility 的使用原则

CubeSandbox 的 E2B-compatible API 是重要优势，但平台不能因此把 E2B 或其云服务变成领域模型或独立 Provider。

~~~text
SandboxProvider SPI
      ↓
CubeSandboxProvider
      ↓
E2B-compatible client/adapter semantics
      ↓
Cube endpoint
~~~

POC 必须实际验证目标兼容面：

- create/destroy
- command streaming
- filesystem
- PTY
- upload/download
- exposed ports
- network rules
- timeout
- pause/resume
- snapshot
- volume
- credential/network policy

缺失能力通过 Provider capability 声明暴露，不允许静默降级。

## 10. Snapshot 对 Harness 的价值

~~~text
Plan
 ↓
Snapshot S0
 ↓
Execute
 ↓
Verify FAIL
 ↓
Rollback S0
 ↓
Replan
 ↓
Execute v2
~~~

未来还可从同一 checkpoint fork 多条候选执行路径。

但 Harness 的 Plan/Step/Artifact/Event 状态仍保存在平台层，不能只依赖 Sandbox snapshot。

## 11. 风险

### 项目成熟度

CubeSandbox 2026 年进入公开 0.x 阶段，变化速度较快。K8s、跨节点 snapshot 等部分能力仍需要明确版本与成熟度门禁。

### 基础设施要求

生产 MicroVM 路线依赖 Linux/KVM 与宿主虚拟化能力，需要验证 bare metal/cloud VM、nested virtualization/PVM、kernel/eBPF、filesystem/reflink、network topology 与 security policy。

### 运维复杂度

CubeSandbox 比 Docker 单机更复杂，包括 Control Plane、Redis/DB、compute nodes、network/egress、template lifecycle 等。

### API compatibility

E2B-compatible 不等于当前全部 E2B 能力永久完全一致，需要 contract test。

## 12. POC Gate

- G-CUBE-1 Isolation：错误/恶意命令不得影响宿主与其他 Sandbox。
- G-CUBE-2 Template：从指定 OCI digest 构建 Template，可重复创建一致环境。
- G-CUBE-3 Lifecycle：create/destroy/pause/resume 稳定，资源正确回收。
- G-CUBE-4 Capacity：多并发 build/test 下调度稳定，不发生节点级失控。
- G-CUBE-5 Snapshot：snapshot/clone/rollback 可重复，并与 Harness checkpoint 分层。
- G-CUBE-6 Network：egress policy、private network deny、credential injection 满足企业要求。
- G-CUBE-7 E2B Compatibility：目标 SDK/API 集合通过 contract tests。
- G-CUBE-8 Upgrade：版本升级后 Template compatibility、rebuild/redo、rolling upgrade 有明确 runbook。
- G-CUBE-9 Failure：CubeMaster/Cubelet/compute node 故障注入后，Harness 不丢业务状态。
- G-CUBE-10 Environment Parity：Local Cube 与 Remote Cube 使用同一 Environment Profile 时通过 conformance suite。

## 13. 当前结论

CubeSandbox 不直接成为最终选型，但进入：

> **本地生产 Sandbox 第一候选 POC。**

| Provider | 定位 |
|---|---|
| CubeSandbox | Production default candidate；Local baseline + Remote burst |
| Docker/containerd | Dev / compatibility / fallback |
| Hyperlight | Specialized untrusted function/WASM execution |
| K8s Job/Pod | Future infrastructure adapter |

## 14. 参考

- CubeSandbox repository: https://github.com/TencentCloud/CubeSandbox
- Architecture: https://github.com/TencentCloud/CubeSandbox/blob/master/docs/architecture/overview.md
- Templates: https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/templates.md
- v0.5 changelog: https://github.com/TencentCloud/CubeSandbox/blob/master/docs/changelog/v0.5.0.md
- v0.7 changelog: https://github.com/TencentCloud/CubeSandbox/blob/master/docs/changelog/v0.7.0.md
