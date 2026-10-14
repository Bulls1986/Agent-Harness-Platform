# Deployment guide · 部署与运行

## 当前交付边界

仓库提供 `compose.yaml` 的**本地开发和验证部署**，并非可直接上线的 Kubernetes Chart / 企业安全配置。正式 M9 生产准入（认证、容量、恢复、运维、回退）尚未完成，**Production NO-GO**。不要把本 Compose 直接暴露在公网。

## 环境和组件

| 组件 | 当前实现 | 端口 / 数据 |
|---|---|---|
| PostgreSQL 16 | `postgres` service，独立 `hatchet_poc` 和 `harness_poc` DB | host `127.0.0.1:55447`，命名卷 `harness_poc_pg` |
| Hatchet Engine | Python SDK Embedded + 受控 Engine sidecar | `harness_hatchet_sidecar` 卷 |
| Run Inspector | `inspector` profile，FastAPI/Uvicorn | host `127.0.0.1:8765` |
| 一次性双 SDK E2E | `demo` profile / `loop` service | CLI 结束，不常驻服务 |
| Public API 体验 | 在 Inspector 下 `/m7-demo/api/v1` 可选挂载 | 固定合成身份，仅开发 |

所有数据卷必须被当作开发测试数据。固定本地密码 `local_poc_only` 不是生产密钥。

## 一键本地部署

```sh
docker compose config
docker compose up -d postgres
docker compose --profile inspector up -d --build inspector
docker compose ps
docker compose logs --tail=80 postgres inspector
```

访问 `http://127.0.0.1:8765/`，Swagger Inspector `/docs` 或 OpenAPI `/openapi.json`。固定合成 API 文档在 `/m7-demo/docs`，OpenAPI 可从 `/m7-demo/openapi.json` 获取（只在合成挂载启用时）。

## 配置参数（适用当前 Compose）

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `HARNESS_INSPECTOR_PORT` | `8765` | 仅改变宿主机 localhost 绑定端口 |
| `HARNESS_POC_PG_PORT` | `55447` | 宿主机 PG 端口 |
| `HARNESS_POC_PYTHON_BASE` | `python:3.12-slim` | 构建时 Python 基础镜像 |
| `HARNESS_POC_PIP_INDEX` | `https://pypi.org/simple` | 构建时 pip index |
| `HARNESS_MODEL_MODE` | `local` | 真实模型需 `live`，且**明确注入到容器** |
| `HARNESS_MODEL_BASE_URL` | 未配置 | 真实模型的 Responses 兼容服务 `/v1` |
| `HARNESS_MODEL_NAME` | 未配置 | 经验证的模型名称 |
| `HARNESS_MODEL_API_KEY` | 未配置 | 运行时密钥；不得写入仓库、日志或镜像 |

`compose.yaml` 的固定 DB、Hatchet 连接及 Inspector demo flag 是开发参数，不保证与企业基础设施兼容。Compose `inspector` 默认不转发 live 模型环境变量；如需现场 opt-in，可只在本地可信终端显式传入（下面用现有 Compose 的一次性容器示例）。

## 真实模型单次验证（仅可信开发环境）

```sh
export HARNESS_MODEL_MODE=live
export HARNESS_MODEL_BASE_URL=https://example.invalid/v1
export HARNESS_MODEL_NAME=your-approved-model-id
# 在本地 Secret Manager/可信交互中注入 HARNESS_MODEL_API_KEY，不要写在命令历史或文件中
docker compose --profile demo run --rm --no-deps \
  -e HARNESS_MODEL_MODE -e HARNESS_MODEL_BASE_URL \
  -e HARNESS_MODEL_NAME -e HARNESS_MODEL_API_KEY loop
```

这是运行现有两个 SDK 的**一次性演示**，不自动让已启动的 Inspector 进入 live 模式。不要把 `example.invalid` 当成真实可访问服务；密钥和端点由部署者自行提供。API 详情请看 [Public API](../api/PUBLIC_API.md)。

## 运维与备份边界

```sh
docker compose --profile inspector restart inspector
docker compose --profile inspector logs --tail=200 inspector
docker compose --profile inspector down
```

`down` 保留数据库和 Sidecar 卷；`down -v` 永久删除**本地数据**。重建镜像前先确认业务测试结果已外部保存。生产 PostgreSQL 备份/恢复、TLS、密钥管理、审计保留、跨宿主多 Engine、容量和回滚由既有基础设施/M9 负责，本文没有声称支持。

**故障定位**：容器 unhealthy → 检查 `docker compose ps` 与 DB 健康；镜像拉取失败 → 检查 DNS/代理及可验证镜像源；M7 读取 404 → 可能是授权拒绝而非资源不存在；503 → 检查外部 Adapter、状态库和日志，不应自动重试未知副作用。

[返回 Quickstart](../guides/QUICKSTART.md) · [发布手册](RELEASE.md)