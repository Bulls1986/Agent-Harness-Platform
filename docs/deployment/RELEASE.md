# Release and maintenance guide · 发布与版本管理

> **当前事实：** 仓库的 CI 会构建和验证代码，但还**没有官方发布的生产镜像、版本化 Helm 包或生产交付流水线**。DEV-M9 尚未验收，因此本指南说明现阶段**可重复验证的源码/本地开发镜像发布流程**，不代表 Production GO。

## 发布前置

1. 选择已合并到 `main` 的提交，确认未包含客户业务代码、专用配置、密钥或真实运行数据。
2. 明确本次范围和相容性，列出 OpenSpec/ADR、API 差异、已验证与 NOT TESTED。
3. 验证 Python SDK 依赖和镜像版本（以 [Dockerfile](../../poc/closed_loop/Dockerfile) 为准）、Compose profiles、迁移脚本和持久化 schema 的向前兼容。
4. 运行所有相关架构/文档/PG/SDK E2E 门禁，确保官方 GitHub Actions 最新 Head 是 SUCCESS，而非 queued、SKIPPED 或仅本地模拟。
5. 列出数据保留、Volume/Schema 回退风险；不得用 `docker compose down -v` 作为升级回滚。

## 本地源码构建与验收

```sh
docker compose config
docker compose build inspector loop
docker compose up -d postgres
docker compose --profile inspector up -d inspector
docker compose ps
```

Python 开发环境可执行：

```sh
python -B -m unittest discover -s tests -v
python -B scripts/check_architecture_guardrails.py
python -B -m unittest tests.test_repository_docs -v
python -B scripts/export_openapi.py --check
```

最后一项需要 FastAPI/Pydantic 等现有 Python 依赖已安装；官方集成 CI 应在安装 SDK 后执行。PG/真实模型/Cube 实测必须分别依照其专项验证脚本执行，不得因本地单测 PASS 省略。

## 版本与发布说明

目前**没有承诺固定的 SemVer / 制品仓库策略**。如维护者需要创建一次**源码预发布**：

- 在受保护的主干完成 PR 审核和 CI；
- 给可追溯 commit 打有说明的版本 tag（例如 `v0.x.y-rc.1`，具体号由维护者决定），附清晰发布说明；
- Release Notes 包含 commit、必要环境、启动方式、变化/兼容性、验收证据和仍然未支持的能力；
- 若需上传 Docker/OCI 制品，先明确仓库、镜像签名、SBOM、凭证和供应链 Owner；本仓库未配置自动推送，不得宣称已经发布；
- 测试所有公开链接、README 示例以及 [API schema](../api/README.md) 的版本一致性。

## 更新 / 回滚原则

在开发环境升级时应先保留 PostgreSQL 测试快照、镜像 digest 与现有环境变量，按文档重新构建并运行 E2E；问题出现时以对应已验证源码/镜像版本恢复应用。**数据库回滚仅在经过独立迁移/备份验证后实施**，尤其是 Outbox、Receipt、Run/Step 权威事实；不要复制/删除单个表以“回滚”。

## Production readiness（尚未满足）

M9 要另外确认真实企业 IAM/Policy、TLS、Secret/Otel/OSS Provider、资源配额、100 Active Runs、Cross-host、灾难恢复、数据库备份和回退。M3～M7 的“限定 CLOSED”并不自动满足这些生产条件。

[部署指南](README.md) · [里程碑与 M9](../DEVELOPMENT_MILESTONES.md) · [项目首页](../../README.md)