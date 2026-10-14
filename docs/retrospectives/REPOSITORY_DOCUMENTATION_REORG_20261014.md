# Repository Documentation / Open-source Landing Restructure · 2026-10-14

## Scope

M9 前的一次**纯仓库门面与文档治理**：根 README 缩短为开源项目入口；长期资料按 user guides / deployment / API / architecture / references / dated evidence 编目；部署、构建与发布说明和可重复导出的 OpenAPI 参考。**不触碰 M3–M8 实现、Run/Tool/Workspace 语义，不新增公开部署或生产保证。**

## Before / TDD Red

早期根 README 797 行，混合历史 POC 与部署状态，架构视图 9 图和项目首页相互锁定。Public API / Inspector HTTP 路由缺少按实现生成的、可比对的 checked-in OpenAPI。新增 `tests/test_repository_docs.py` 的 4 项 contract 测试首先因过长首页、缺用户手册、缺 API 文档/机器可读 schema 而失败（RED）。保留原有架构 guard 的 8 views / 9 Mermaid 约束，调整唯一图源到 `docs/ARCHITECTURE_VIEWS.md`，同时更新 guard 的离线负例。

## Changes and evidence

- Homepage 797 → 85 行；保留 GPL-3.0、CI、Quickstart、M9 Production NO-GO 与文档链接；旧长首页转 `docs/history/PROJECT_OVERVIEW_20261011.md` 并明确历史截面。
- 唯一 9 Mermaid 图源移到 `docs/ARCHITECTURE_VIEWS.md`，修正正式架构与参考材料链接，guard 不允许 README 复制整套视图。
- `docs/guides`：Quickstart、User Guide；`docs/deployment`：Docker 参数/运维、发布/版本与升级/回退检查；`docs/api`：公共 v1 合同、Inspector API、SSE/错误码与两份 OpenAPI。
- `scripts/export_openapi.py` 从现有 **真实 FastAPI 路由声明**离线导出；schema-only 构造不连接数据库/不伪造可运行认证。CI 使用 `--check` 防止接口定义与文档快照漂移。静态回归确保全部已声明公共 v1 路由在 Markdown + JSON 中存在。
- 本地验证：`python -B -m unittest discover -s tests -v` 27/27；`python -B scripts/check_architecture_guardrails.py` PASS（8 views/9 diagrams）；`python -B poc/verify_repo_navigation.py` PASS（123 links）；`python -B scripts/export_openapi.py --check` PASS；`docker compose config --quiet` PASS；8 OpenSpec specs Strict PASS。
- 已有 localhost Inspector `/`、`/api/config`、`/openapi.json`、`/m7-demo/openapi.json` 均实际 HTTP 200；未对已有环境执行 `down -v`，未改变 Docker 服务、身份机制或业务状态。

## Official CI version divergence and fix

首次 PR #97 架构 CI PASS；Native CI 38508985881 在 OpenAPI 快照逐字对比失败，原因是本地 FastAPI 0.115.14/Pydantic 2.12.5 与 GitHub CI FastAPI 0.143.0/Pydantic 2.14.1 生成元数据存在非语义差异。修正为纯标准库 `scripts/openapi_signature.py` 投影校验：仍阻断路径/方法、Query/Header/Body 字段、请求必填、响应状态等合同漂移，但容忍框架生成的描述和验证错误组件差异，不变更运行时依赖。新增负例测试证明路由删除/请求字段删除必 FAIL、info 元数据差异不导致 FAIL。修复后应以 PR 最新 Head 官方完整 CI 为准。

## Risk / follow-up boundary

旧历史文件中的某些相对链接仍以**原根目录位置**为参照，已显式标注历史快照而不作为当前运行指南；正式导航改为有检查的 docs hub。README 的精简不应改变 9 张 Mermaid 的语义。企业生产发布、镜像制品/签名、企业 IdP/OSS 和生产 M9 准入仍 **OPEN / NO-GO**，没有因手册存在就升级为能力。GitHub 官方 PR/CI 是最终合并准入，本地通过不是官方 CI。