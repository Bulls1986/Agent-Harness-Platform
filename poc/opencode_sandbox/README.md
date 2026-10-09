# OpenCode + E2B-compatible Sandbox / Shared Runtime POC

> 2026-10-09。**专项进行中，不是 G5 或共享 Coding Runtime 的生产 GO。**
> 本专项遵循既有 Workspace/Sandbox、Control/Data Plane 和容量契约，
> 不更改 Runtime Domain Model，也不让 E2B Cloud 成为生产强制依赖。

## 核心问题

长期存在的大量逻辑 Agent Session **不能**等于相同数量的 OpenCode
进程或 Sandbox。需要分别证明以下三件事，不能互相替代：

1. 一个 OpenCode Server 通过公开 HTTP API 承载多个 Session。
2. OpenCode-in-Sandbox 通过完整 FS/Shell/Git/Session 行为，且每次执行
   有明确、可重建的 Workspace / Sandbox Binding。
3. 共享的 OpenCode Server 可以在不同项目/用户并发时，将 **全部**
   文件、编辑、Shell、Git、LSP、插件和其他可访问宿主机资源的路径
   安全隔离至目标 Sandbox；任意工具不支持则必须 fail closed。

第 1 项是容量前提，**不自动证明第 3 项的执行隔离**。

## 当前实测与状态

| 证据 | 状态 | 严格范围 |
|---|---|---|
| Windows OpenCode 1.14.28, headless HTTP health | PASS | 本机隔离临时目录与 loopback；未调用 LLM |
| 同一 Server 的两个已提交 Git 项目、6 与 20 个并发 Session | PASS | 两次独立启动各 1 个 Server 实例，项目列表无跨项目 Session；未测完整子进程树 |
| 只有 git init 但没有初始 commit | 发现风险 | 两个项目的 Project ID 均为 global，不能用作安全身份 |
| E2B Cloud OpenCode Sandbox | NOT RUN | 缺 E2B_API_KEY；明确 opt-in 后可执行 |
| CubeSandbox + OpenCode 自定义模板 | NOT RUN | 缺 Cube API Endpoint 和已构建的 OpenCode 模板 |
| 共享 OpenCode Runtime + Sandbox Tool Adapter | NOT PROVEN | 宿主机文件/Shell/LSP/插件路径未被完整隔离 |
| 多 Session RSS/CPU、10/100/1000 负载 | NOT RUN | 尚无相同负载资源对照与容量边界 |

测试 **没有**证明 OpenCode 的任意 Tool 能在跨项目场景安全路由，
更没有证明同一进程能够安全执行来自不同用户的任意不可信代码。
不同 Git 仓库可能共享相同 root commit，OpenCode 的 Project ID
也不适合用于授权、Sandbox Binding 或跨用户访问控制。

## 执行入口

### ① 本机共享 OpenCode HTTP（无需模型密钥）

```bash
python poc/opencode_sandbox/smoke_local_pool.py --sessions-per-project 3
```

创建两个**有独立首个提交**的临时 Git 项目，启动一个 OpenCode
Server，并发创建/查询 Session，打印单行可机器读取的 JSON。
仅验证 HTTP Session 路由；不会请求模型或运行项目代码；结束时
强制清理 Server 和临时目录。本机环境使用已安装的 OpenCode CLI。

### ② 官方 E2B 模板，真实 Sandbox 内 OpenCode

E2B 提供预构建 `opencode` 模板，可以在 Sandbox 内运行
`opencode serve`，平台通过 HTTP API 使用 Session。此验证
只使用健康检查和 Session CRUD，不调用模型，不进行 Git Push。

```bash
python -m pip install e2b
# 在可信执行环境中配置 E2B_API_KEY，不写入仓库或日志
export OPENCODE_TEST_ALLOW_REMOTE=1
python poc/opencode_sandbox/smoke_e2b_opencode.py --provider e2b
```

仅当明确允许产生 E2B Cloud 资源费用时开启 opt-in。工具结束时
销毁创建的 Sandbox；不要直接将 Sandbox 内的 OpenCode HTTP
服务无鉴权地公开到互联网，示例使用临时 Basic Auth 密码。

### ③ CubeSandbox：必须使用企业内网自建模板

CubeSandbox E2B-compatible 接口允许特定 SDK 操作复用，但
**E2B Cloud 的 `opencode` 模板不是 CubeSandbox 的预置模板 ID**。
先使用不可变 OCI 镜像在 CubeSandbox 注册并验证包含 OpenCode 的
自定义模板（其 HTTP 4096 端口可访问），再配置：

```bash
export E2B_API_URL="https://<private-cube-api>"
export E2B_API_KEY="<trusted-cube-api-key>"
export CUBE_OPENCODE_TEMPLATE_ID="<registered-cube-template-id>"
python poc/opencode_sandbox/smoke_e2b_opencode.py --provider cube
```

此脚本是 E2B Python SDK 兼容性探针；如果 Cube 当前 SDK/协议
不接受该调用，应报告 **UNSUPPORTED/GAP** 并评估 Cube 原生 SDK，
不可称为已通过，也不应绕过 TLS 或安全认证。E2B 保留为协议兼容
测试目标，不改变 CubeSandboxProvider 的生产候选地位。

## 下一阶段的不可豁免门禁

| Gate | 验收标准 |
|---|---|
| H1 | 真实 E2B/Cube 下 OpenCode 文件读/改、Git、Shell、取消、Session 恢复与完整 Evidence 链 PASS |
| H2 | 共享 Runtime 进行 **跨 Workspace 并发文件写入** 的正反对照，零串写；不支持的 Tool 必须明确拒绝 |
| H3 | 证明 bash、read、write、edit、glob、grep、git、LSP、插件及 Skills 脚本等宿主机执行面没有遗漏出口 |
| H4 | Server A 退出后 Server B 能基于持久 Session/Workspace 状态在已声明能力边界继续；不把缓存当权威状态 |
| H5 | 相同负载实测两种拓扑：OpenCode-in-Sandbox 与共享 OpenCode + remote Sandbox；记录 RSS、CPU、P95、活跃进程和 Sandbox 数量 |
| H6 | 100/1000 空闲 Session 不应线性创建进程或 Sandbox；Coding 执行仍遵守独立的 Sandbox 安全边界 |

若无法通过官方公开扩展点把 **全部** OpenCode 文件/执行入口
安全路由到外部 Sandbox，则应继续采用 **OpenCode-in-Sandbox
+ 生命周期池化/暂停**，而不是为降低 RSS 放弃隔离，或修改
OpenCode 内核。

## 参考

- [E2B 官方 OpenCode 集成](https://docs.e2b.dev/agents/opencode)
- [OpenCode Server](https://opencode.ai/docs/server/)
- [OpenCode SDK](https://docs.opencode.ai/docs/sdk/)
- [OpenCode Custom Tools](https://docs.opencode.ai/docs/custom-tools/)
- [CubeSandbox Quickstart](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/quickstart.md)
- [CubeSandbox Volume 兼容边界](https://github.com/TencentCloud/CubeSandbox/blob/master/docs/guide/volume-plugin.md)
- [OpenCode 无提交 Git Project ID 问题](https://github.com/anomalyco/opencode/issues/15192)