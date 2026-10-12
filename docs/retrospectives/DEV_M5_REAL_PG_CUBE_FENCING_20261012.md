# DEV-M5 · 真实 Harness PostgreSQL + Cube MicroVM Fencing 联调（2026-10-12）

## 本次已通过的真实执行证据

此验收直接执行仓库既有 `poc.sandbox.verify_cube_live`，并非独立原生 SDK Smoke，也没有使用 Fake Cube/SQLite、Host Files 或构造的 Sandbox ID。测试环境为已安装的 CubeMaster/Cubelet/CubeAPI/Proxy 和 Ready 的真实 Cube 模板，外加同一 WSL 测试进程内启动的隔离 Docker PostgreSQL 16。PG 只绑定本机 loopback 测试端口，执行结束自动停止。

真实终态输出：

```json
{
  "outcome": "PASS_REAL_CUBE_MICROVM",
  "run_id": "m5-cube-live-1bbc0dc3f09b412aaded954d75d90b8b",
  "sandbox_id": "ad3ea8818a7e45a2a49c9d1518102b59",
  "workspace_ref": "workspace-m5-cube-live-1bbc0dc3f09b412aaded954d75d90b8b",
  "worker_B_epoch": 8,
  "native_reconnect": true,
  "read_original_bytes": true,
  "destroy_ack": "RELEASED",
  "physical_worker_SIGKILL": "NOT_TESTED_IN_THIS_CUBE_GATE",
  "cross_host": "NOT_TESTED"
}
```

进程退出码为 **0**；实际 Harness PG `harness_cube_binding` 经历 `ALLOCATING → CREATING → ACTIVE → A/7 Lease 过期 → B/8 Fencing 接管 → RELEASING → RELEASED`。Worker A 的旧执行权限被拒绝，Worker B 使用新的 `PgFacts` 和 `NativeCubeTransport` 客户端，在相同原生 Cube Sandbox 中读取与 A 写入的相同 Guest 文件字节，然后以 Cube Native Kill ACK 完成 PG Release。该子切片没有真正杀死 A 进程，因此只属于**真实 Cube + PG 逻辑跨 Owner** Gate。

## 本机环境排障与复用

- 初次 WSL 命令间环境会冷启动，导致 CubeAPI 不就绪，容器服务被重置；历史事实不能假定当前 CubeAPI 长期驻留。已调整为**一个长生命周期 WSL 测试进程**内部等待 Cube health、启动 Docker PG、执行真实代码并通过 Shell Trap 自动停止专用测试 PG。这样实测 PASS，不将环境起停误判为业务故障。
- 本项目不需要重新搭建 Cube/MicroVM，已有 Cube 单节点实机具备官方 SDK Create/Connect/Files/Destroy 和真实模板。没有上传任何业务消费者私有实现或内部资源到公共仓库。
- 独立 `poc.sandbox.verify_cube_sdk_smoke` 在 PR #75 已有两次真实 MicroVM 创建证据；**当前更进一步**让 Harness PG 实际保存 WorkspaceRef/Owner/Fencing，并验证 B 的新的 SDK 连接和回收。

## 正在验证的下一道独立 Gate

同 PR #76 新增 `poc.sandbox.verify_hatchet_cube_worker_takeover`：真实 Hatchet Engine + 两个独立 Worker 进程 + 同一个 Cube MicroVM + Harness PG，控制端确认 Worker A 的原生 Guest 文件后杀掉整个 A 进程组；Worker B 必须通过 Hatchet 原生 Retry 领取同一 Workflow Run、在 PG 权威处 A/7→B/8 Fencing、重新连接**同一 Sandbox ID**，验证原内容与 Resource Release。此 Gate 的状态以独立实机命令退出码和证据为准，不能拿已 PASS 的 PG+Cube 或先前独立 Hatchet A→B Demo 相加冒充联合通过。

正式 DEV-M5 的 Guest in-flight Fencing、OCI Digest 一致性、跨主机/故障区、Scope/Principal 的真实隔离和生产治理仍 OPEN。M9 Production NO-GO。
