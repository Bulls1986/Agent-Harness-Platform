# 工作空间、仓库与 Git 契约

> 状态：Accepted Architecture Contract  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-003

## 1. 核心决策

Coding Harness 的代码事实与执行环境必须分层：

~~~text
权威 Git 仓库（Authoritative Git Repository）
        ↓
项目仓库（Project Repository）
        ↓
项目工作空间（Project Workspace）
        ↓
仓库工作空间（Repository Workspace）
        ↓
工作树（Worktree）
        ↓
沙箱（Sandbox）
~~~

核心原则：

- Git Server 保存权威代码事实。
- Project Repository 静态定义项目边界、项目规则、项目级 Skill 与需要拉取的仓库。
- Project Workspace 保存一个项目当前的可变工作状态。
- Repository Workspace 对应一个 Git Repository。
- Worktree 是 Git 仓库级的可写隔离单元。
- Sandbox 只提供执行环境，不拥有代码事实。
- Run 使用 Workspace，但不等同于 Workspace。
- Repository Mirror / Cache 只能作为可重建缓存，不能成为主干事实源。

## 2. 项目仓库（Project Repository）

每个项目建议存在一个专门的项目仓库，作为项目级事实入口，例如：

~~~text
project-control.git
├─ AGENTS.md
├─ project.yaml
├─ skills/
├─ docs/
└─ shared/
~~~

职责包括：

- 静态定义项目包含哪些代码仓库。
- 定义默认分支、访问模式等项目元数据。
- 保存项目级 AGENTS.md。
- 保存项目级 Skill。
- 保存项目公共规范、脚本、资源和说明。
- 可选记录仓库依赖关系与兼容信息。

Project Repository 本身不替代业务代码仓库，也不成为新的代码主干。

## 3. 项目清单（Project Manifest）

项目边界采用静态配置，不依赖运行时自动发现作为唯一事实来源。

示例：

~~~yaml
repositories:
  - id: user-service
    url: ...
    default_branch: develop
    access: write

  - id: order-service
    url: ...
    default_branch: develop
    access: write

  - id: portal-web
    url: ...
    default_branch: develop
    access: write

  - id: common-sdk
    url: ...
    default_branch: main
    access: read
~~~

仓库依赖关系可以记录，例如：

~~~yaml
dependencies:
  portal-web:
    - user-service
~~~

但它只作为 Metadata / Context，不作为平台强制执行的任务 DAG。

## 4. 多仓与单仓模型

### 4.1 单仓（Monorepo）

~~~text
repo
├─ backend/service-a
├─ backend/service-b
├─ frontend/admin
└─ frontend/portal
~~~

原则：

> 一个 Git Repository 对应一个 Repository Workspace / Worktree；Module 不是 Worktree 粒度。

### 4.2 多仓（Multi-repo）

~~~text
Project Workspace
├─ Repository Workspace: user-service
│    └─ Worktree
├─ Repository Workspace: order-service
│    └─ Worktree
├─ Repository Workspace: portal-web
│    └─ Worktree
└─ Repository Workspace: common-sdk
     └─ Worktree
~~~

原则：

> Worktree 是 Git Repository 级隔离单元；Project Workspace 才是完整项目任务的代码工作空间。

## 5. Workspace 与 Run / Sandbox 的关系

必须保持：

~~~text
Run ≠ Workspace
Sandbox ≠ Workspace
Runtime Session ≠ Workspace
~~~

允许：

~~~text
Run R1 ─┐
        ├─ Project Workspace PW1
Run R2 ─┘
~~~

也允许：

~~~text
Project Workspace PW1
   ↓
Sandbox S1
   ↓ destroy

Project Workspace PW1
   ↓
Sandbox S2
   ↓ continue
~~~

Sandbox 生命周期可以短于 Workspace 生命周期。

## 6. Workspace 生命周期

Project Workspace 允许跨多个 Turn / Run 复用。

建议状态：

- ACTIVE
- IDLE
- ARCHIVED
- DELETING

Run 启动时必须冻结本次使用的代码基线，不因为 Workspace 后续继续演进而改变已经形成的执行证据。

Workspace 长期存在不等于永久保留；Retention / GC 由后续生命周期策略细化。

## 7. 仓库版本集合（Repository Revision Set）

多仓项目不能只记录单一 base_revision。

每个 Run 至少记录本次使用的 Repository Revision Set：

~~~text
user-service = abc123
order-service = def456
portal-web = 789xyz
common-sdk = 456def
~~~

用途：

- Evidence
- Recovery
- Audit
- Debug
- Reproduce

Revision Set 只用于记录和追踪，不构建额外的跨仓版本事务系统。

## 8. 主干（Mainline）与权威事实

权威主干始终在 Git Server：

~~~text
origin/main
origin/develop
~~~

平台不得把 Harness 本地目录、Repository Mirror 或 Sandbox 中的 checkout 视为权威主干。

Repository Mirror / Git Object Cache 可以用于 clone/fetch 加速，但：

> Cache 丢失必须可以从 Git Server 重建。

## 9. 主干同步策略

原则：

> **执行期间追求可重复性，集成之前追求新鲜度。**

Run 启动：

~~~text
记录 base_revision
冻结本 Run 的 Repository Revision Set
~~~

执行过程中：

- 允许 fetch 更新远端视图。
- 禁止隐式 rebase / merge 改变当前 Worktree 基线。
- 所有改变 Workspace 基线的动作必须是显式事件。

准备交付前：

~~~text
fetch latest
→ 记录 upstream_revision
→ 比较当前基线
→ 显式 rebase / merge
→ 处理冲突
→ 重新 Verify
→ commit / PR / MR
~~~

关键版本字段至少包括：

- base_revision
- head_revision
- upstream_revision

## 10. 冲突处理

- 简单冲突可以由 Agent 自动处理。
- 任何冲突解决后必须重新执行相关 Verify。
- 复杂冲突进入重规划（Replan）或人工介入。
- 禁止静默覆盖冲突文件。
- 冲突解决本身必须形成可审计的 Git Diff / Evidence。

## 11. Worktree 隔离

默认规则：

> 一个并发可写执行主体，不得与另一个可写执行主体共享同一 Worktree。

典型情况：

- 一个可写 Run → 独立 Worktree。
- 一个可写子 Agent → 默认独立 Worktree。
- 只读分析任务可共享相同基线或只读快照。
- 多 Agent 并发写入时，各自独立 Worktree，后续由显式集成步骤处理。

Agent 不拥有 Worktree。Worktree 属于 Repository Workspace。

因此 Agent 崩溃、替换或重启后，可以由新的执行主体继续使用同一 Repository Workspace。

## 12. Git 自动化权限

建议默认：

### 可自动执行

- fetch
- status
- diff
- log
- read
- branch inspection
- 本地 commit（在 Recipe / Policy 允许时）

本地 commit 有利于：

- 恢复
- Diff
- 回滚
- Evidence
- 阶段性验证

### 外部副作用操作

以下操作必须进入 Policy 与副作用契约：

- push
- merge
- tag
- delete branch
- force push

其中 force push 默认禁止，除非明确 Policy 授权。

Git Credential 不进入模型上下文，应由 Secret / Credential Provider 临时注入。

## 13. 集成路径

生产默认建议：

~~~text
Workspace
→ Local Commit
→ Push
→ PR / MR
→ CI / Verify
→ Merge Queue / Protected Branch
→ Mainline
~~~

平台不把“多仓同时合并”抽象成强事务型 ChangeSet。

Run 可以记录本次影响的多个仓库、Commit、PR/MR 和状态，但平台 V1 不承诺：

- 跨仓原子合并
- 分布式补偿
- 多仓 merge transaction

如果项目需要特殊跨仓集成顺序，由项目级 Skill / Policy 描述，而不是写死在 Harness Kernel。

## 14. 项目工作方法属于 Skill

例如：

~~~text
修改 API
→ 后端测试
→ 更新 OpenAPI
→ 前端适配
→ 联调
~~~

这类流程属于项目工作方法，应由项目级 Skill 定义。

平台只提供：

- Repository
- Workspace
- Worktree
- Sandbox
- Tool
- Artifact
- Evidence
- Verification

不能把具体项目研发流程固化进 Harness Kernel。

## 15. 项目上下文（Project Context）

Project Repository 可以承载：

- AGENTS.md
- Project Manifest
- Project Skills
- 规范文档
- 公共脚本
- 公共资源

但本契约不规定 AGENTS.md 为所有 Agent 的强制格式。

平台需要的是“项目级指令与技能能力”，具体如何发现、解析、向主 Agent / 子 Agent / Runtime 传播，由独立架构待办继续讨论。

## 16. 项目仓库与业务仓库

建议 Project Repository 在 Workspace 中作为“只读优先”的 Repository Workspace 被拉取。

它用于提供：

- Project Definition
- Instructions
- Skills
- Shared Metadata

业务代码仓库则根据 Manifest 中的 access 模式决定 READ / WRITE。

## 17. 缓存边界

以下内容可以共享或缓存：

- Repository Mirror
- Git object cache
- npm/pnpm cache
- Maven/Gradle cache
- Python package cache

但：

- Cache 不是代码事实源。
- 业务源码写空间必须隔离。
- Cache poisoning / tenancy / eviction 由 ARCH-TODO-019 继续讨论。

## 18. E2E / 测试环境不在本契约展开

多仓项目通常需要组合测试环境，但以下问题不属于 Workspace / Git Contract：

- 如何创建一套 E2E 环境
- 是否复用现有测试环境
- 多仓服务如何部署组合
- 环境租约与生命周期
- 测试数据
- 并发环境隔离

该主题作为独立架构待办讨论，不在 ARCH-TODO-003 发散。

## 19. Accepted Rules

~~~text
Git Server
→ 权威代码事实

Project Repository
→ 静态定义项目 / AGENTS.md / Skills / Repo Manifest

Project Workspace
→ 项目当前工作状态

Repository Workspace
→ 一个 Git Repository 的工作状态

Worktree
→ Git 仓库级可写隔离单元

Sandbox
→ 临时执行宿主

Run
→ 使用 Workspace，但冻结自己的 Revision Set
~~~

同时冻结：

- Workspace 可跨多个 Turn / Run 复用。
- Run 执行中不隐式追主干。
- 集成前刷新主干并重新 Verify。
- 可自动本地 commit；push/merge 等外部写操作进入 Policy 与副作用契约。
- 多仓 Revision Set 记录但不形成强事务。
- 项目工作流程由 Skill 定义，不由平台内核固化。
