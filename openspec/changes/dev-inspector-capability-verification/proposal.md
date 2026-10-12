# Proposal · Inspector 能力验证 Tab

## Why

当前 Run Inspector 只展示 Pydantic AI → OpenAI Agents SDK 两节点流程，无法让评审者直接理解后续 M4/M5 Tool Receipt、Cube Workspace 和 Hatchet 跨 Worker 接管分别解决什么问题。将真实 PG 事件直接展示成原始 JSON 会误导非开发人员，也可能把“存在一条事件”错误认定为“实机门禁 PASS”。

## What Changes

在原 Inspector 添加**仅一个新的顶层 Tab**「能力验证」，旧双 Agent 流程不改。每个场景要说明使用场景、证明的平台能力、实际步骤、必须取得的证据以及目前不能证明的范围。新增只读目录接口和按 Run ID 读取 PostgreSQL 事实的接口，允许观察 WorkspaceRef/Sandbox Locator/Owner/Fencing/Tool Receipt；不在无鉴权的 HTTP Inspector 内启动 SIGKILL、Cube 特权任务或重新实现调度器。

## Scope / Non-goals

本切片是“清楚解释能力与查看已有持久事实”，不是 M5 实机故障一键启动器，也不是生产 Observability/IAM。没有真实执行证据不得标成实机通过；真实 Cube/Worker 联合 Gate 继续由它们自己的验证/CI 负责。原双 Agent Tab 和 HTTP 路径保持兼容。

## Status

**ACTIVE：UI + 只读 PG 合同实现中；后续可信场景执行器集成单独计划，绝不混同已完成。**
