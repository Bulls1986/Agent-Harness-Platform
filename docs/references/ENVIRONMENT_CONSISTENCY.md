# Local / Remote Sandbox 环境一致性

> 状态：讨论参考  
> 日期：2026-09-29

## 1. 问题

当平台同时存在 Local Sandbox 与 Remote Sandbox 时，最大的 correctness 风险之一是环境漂移：

> 本地验证通过，但切到远程后因为 Node/JDK/系统库/浏览器/工具版本不同失败。

因此不能仅要求“两个环境看起来差不多”。

正式目标：

> **Execution Environment Contract 一致；环境构建源唯一；每次执行可追溯到不可变环境版本。**

## 2. 单一环境源

~~~text
Dockerfile / OCI build definition
        ↓
OCI Image
        ↓
immutable digest sha256:...
        ↓
Environment Registry
      /            \
Local Template    Remote Template
~~~

本地与远程不要求底层 VM snapshot 字节一致，但应来自相同 OCI digest 和同一 Environment Profile。

## 3. Environment Registry

建议正式组件：

~~~text
EnvironmentRegistry
├─ profile
├─ version
├─ source OCI repository
├─ immutable digest
├─ local template id
├─ remote template id
├─ capabilities
├─ supported architectures
├─ resource profiles
├─ verification status
└─ deprecation status
~~~

示例：

~~~yaml
profile: coding-node24
version: 1.3.0

source:
  image: registry.example.com/agent/coding-node24
  digest: sha256:ABC

targets:
  cube:
    template: cube-coding-node24-1.3
  e2b:
    template: e2b-coding-node24-1.3

capabilities:
  - node24
  - pnpm
  - git
  - playwright
  - codex
~~~

## 4. Environment Fingerprint

每次 ExecutionResult 应记录环境指纹：

- environment profile/version
- OCI digest
- provider type
- template id/version
- architecture
- CPU/memory profile
- network policy version
- base toolchain versions
- workspace revision
- injected policy/secret references
- runtime mutation flag

这样出现“只在某个 Provider 失败”时可以直接做环境对比。

## 5. 基础工具与项目依赖分离

基础工具如 git、node、python、java、pnpm、ripgrep、browser/system libs、codex/opencode runtime 应进入 Environment Image，由平台版本管理。

项目依赖如 package lock、requirements、pom/Gradle dependency、repo-local toolchain 允许在 workspace 内安装。

平台不鼓励 Agent 在运行时随意修改基础 OS。若任务缺少基础 capability，应形成 Environment Profile 变更，而不是产生不可追踪漂移。

## 6. Template 与 Snapshot 的区别

### Template

- 可复现基础环境
- 来源于 immutable image/profile
- 用于大量创建 Sandbox

### Snapshot

- 某个 Sandbox/Session 的运行状态
- 可用于 pause/resume、rollback、fork
- 不是基础环境版本管理手段

不要用 Snapshot 替代 Environment Registry。

## 7. Promotion 流程

~~~text
Dockerfile change
   ↓
CI build OCI
   ↓
security scan
   ↓
digest freeze
   ↓
build Local template
   ↓
build Remote template
   ↓
environment conformance test
   ↓
mark READY
~~~

只有双端 conformance 都通过，Environment Profile 才能进入 READY。

## 8. Conformance Test

至少验证：

- uname/arch
- node/java/python/git versions
- package manager versions
- shell behavior
- file permissions
- workspace path
- DNS/network policy
- CA/proxy behavior
- browser availability
- command streaming
- terminal/PTY
- file upload/download
- test/build sample repo
- locale/timezone if business-sensitive

## 9. Scheduler 与环境版本

ExecutionRequest 必须明确环境版本，例如 coding-node24:1.3.0，不能只写 latest。

Run 启动后应 freeze 该版本，避免一次长任务中途切换 Template。

## 10. 当前结论

Local/Remote 双 Provider 能否真正无感切换，关键不在 API 名称是否一致，而在：

1. Environment Contract
2. Immutable OCI digest
3. Environment Registry
4. Conformance Test
5. Execution fingerprint

这五项应成为 Sandbox POC 的硬门禁。
