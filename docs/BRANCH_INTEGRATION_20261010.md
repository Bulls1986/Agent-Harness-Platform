# 2026-10-10 分支整合与主干准入记录

> 此报告记录分支整合**代码/文档范围**，不是 Agent Harness Platform 的**生产准入**。产品生产仍为 NO-GO。

## 两条必须合并的实际开发线

- 基准 `main`：`82c6328b21615bd7ed49d1cd0b9326d0e54aaaee`，包含 POC-A G2/G3/G6 真实恢复/Receipt、POC-C 的 Temporal Typed Event SSE / Postgres / S3 Artifact / Cancel 修复与 MXC 候选等成果。
- 集成来源 `poc/multi-harness-cube-architecture-20261009`：`6fe7a552b1d707e17c5dc8de7c0391d6036732fd`，包含 OpenCode 2/CubeSandbox/E2B/Pydantic/Runtime SPI、版本锁定、完整架构 README 与现有 OpenCode PDLC 无感迁移设计。
- 历史分叉：以上来源相对主干 **27 个新增提交**、主干有 **9 个不同提交**。两条均保留，**不用覆盖提交历史、强制推送、以旧 README 替换新架构**。

## 冲突解决

在独立 Worktree 以 `main` 为基线执行真实 `git merge --no-ff --no-commit`，仅出现两个内容冲突：

1. `README.md`：使用新版架构总方案（包含 OpenCode PDLC 无感迁移、Agent 串联、选型比较与 POC 证据）；主干原有 POC-A/POC-C 细节留在独立报告和原实现，不删除主干实际文件。
2. `docs/references/README.md`：**合并双方索引**，保留主干的 MXC Candidate、POC-C 阶段评估记录，以及 POC 分支的多 Harness/Cube/版本锁定/PDLC 迁移资料，修复序号冲突。

`docs/ARCHITECTURE.md`、`docs/POC.md`、`docs/ARCHITECTURE_BACKLOG.md` 等文件经 Git 自动三方合并，均未产生内容冲突。

## 历史分支范围核对（不盲合过时分支）

已刷新全部远端分支并对独立 Worktree 的**整合索引文件树**检查了除 `main` 与当前 POC 来源外 **46 个远端历史分支**；整合索引有 **329 个文件路径**，未发现只在这些历史分支出现、整合索引内**完全不存在**的文件路径。

**这只证明路径覆盖，不证明文件内容逐字相同或历史分支都已合并。** 许多历史分支是 MAF/Temporal/POC-A34/C00-C16 等阶段性实验，和主干/当前架构有不同的实现阶段或复验证据。保留 Git 分支供考古与审计，不把全部旧提交倒灌主干，也不自动删远端历史分支。需要把某份历史实现重新纳入正式版本时，应基于当前 Accepted Contract 单独审计，而不能仅因为分支在 `git branch --no-merged` 中就直接合并。

## 整合验收

- 根 README 的业务目标与 Accepted Contract 一致：**原 OpenCode PDLC 无感迁移 + 跨 Agent 串联**，并且明确技术 POC LIMITED GO、生产 NO-GO。
- 主干保留 POC-C G3 Typed SSE、S3 Evidence/UNKNOWN 保护、Temporal Cancel Confirmation；POC 分支保留 Cube/OpenCode 真机、E2B 版本兼容、Pydantic、Runtime SPI 和测试脚本。
- 本地集成检查运行 `poc/verify_repo_navigation.py`、`poc/verify_admission_offline.py`、`poc/runtime_spi/verify_runtime_spi.py`、`poc/compatibility/verify_stack.py --self-test`、`git diff --check`。
- **全部代码的 Linux 专用 CI/真实数据库/真实 Cube 测试仍以 GitHub Actions 或各专项 POC 原始证据为准。** 不把无外部依赖的本地验证宣称为全部 Live Gate 重测。

主干整合应通过 PR 验证合并，不关闭仍 OPEN 的 ARCH-TODO-025～029，不把独立功能 POC 误写为生产 Accepted。
