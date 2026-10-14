# Quickstart · 本地五分钟体验

> **仅用于开发 / 演示。** 当前 `compose.yaml` 中有固定的本地测试数据库密码，端口仅绑定 `127.0.0.1`，不得直接部署到公网或企业生产环境。

## 1. 前置条件

- Docker Desktop / Docker Engine 与 Compose V2（`docker compose version`）
- Git、空闲本地 TCP 端口 8765（可设 `HARNESS_INSPECTOR_PORT`）和数据库端口 55447
- 初次构建能访问 Python 镜像源和 Python 包仓库
- 默认确定性模型模式不需要 API Key

## 2. 启动

从仓库根目录运行：

```sh
docker compose up -d postgres
docker compose --profile inspector up -d --build inspector
docker compose ps
```

在浏览器打开 [本地 Inspector](http://127.0.0.1:8765/)。启动后从「双 Agent 演示」提交一个**无敏感信息**的测试提示，观察 Run ID、Step A / Step B 输入输出、最终结果和事件时间线。当前本地测试 Agent 是固定模型输出，**不代表模型理解了提示的全部业务内容**。

选择「能力验证」可查看场景解释及已落库的证据；只读证据查询不等于实际沙箱/操作系统故障注入成功。M7 的合成演示位于同源 `/m7-demo`，仅在 Inspector Compose Profile 显式启用，使用服务端固定测试身份。

## 3. 基础检查

```sh
curl http://127.0.0.1:8765/api/config
curl http://127.0.0.1:8765/api/verification/scenarios
curl http://127.0.0.1:8765/openapi.json
docker compose logs --tail=100 inspector
```

请注意：`/api/config` 的模式默认是 `local`；只有配置了外部 Responses 兼容模型并选择 live，才是远端真实 LLM 模式。官方持续集成的真实 PostgreSQL / SDK 验收与浏览器演示的能力范围不同。

## 4. 停止 / 重建

```sh
docker compose --profile inspector stop inspector
docker compose --profile inspector up -d --build inspector
docker compose --profile inspector down
```

`down` **默认保留** PostgreSQL 和 Hatchet 的命名卷。只有确实决定**删除所有本地测试数据**时才运行 `docker compose --profile inspector down -v`。切勿在保存重要证据的环境里执行 `-v`。

## 5. 下一步

- [Inspector 使用手册](USER_GUIDE.md)：阅读结果、SSE、异常和审批能力边界
- [部署和常见问题](../deployment/README.md)：端口、数据卷、模型配置
- [公共 API 文档](../api/README.md)：版本化 API 与 Inspector 调试 API 的区别
- [开发阶段和未验收项](../DEVELOPMENT_MILESTONES.md)

**如果构建失败**，先检查镜像拉取、代理/DNS、Docker 可用内存及 `docker compose logs`；镜像与 Python 包镜像站可通过 [部署手册](../deployment/README.md) 中的现有环境变量覆盖。