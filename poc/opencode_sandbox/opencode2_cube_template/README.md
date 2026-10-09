# OpenCode 2 Harness-in-Cube OCI 模板（待实测验收）

> 状态：**Docker OCI Build + `opencode --version` PASS / Cube Template NOT VERIFIED**。
> 本目录是 ARCH-TODO-027 的执行候选，与官方 Cube “Bash Tool Plugin” 属于**不同拓扑**。
> 2026-10-09 WSL Docker 真实构建输出 `Successfully built 825b61c967d0` / `opencode v2.0.24`，
> 已解决 Alpine musl 与 Cube Debian guest 的运行库兼容；**尚未通过 Registry Push / Cube Template READY / 真正 MicroVM V2 Session**。
> 宿主机 Docker Desktop 的 13 个现有运行容器未清理或停止。

> **最新 22:50 双阶段验证结论：** 本目录组合 OCI Build、Registry Push、CubeMaster OCI Pull、EXT4 Artifact **READY** 和节点 1/1 分发已真实 PASS。首次 Job 40% 僵滞为 WSL/systemd 停止进而 `context canceled` + FAILED 回调丢失；WSL 保活后同镜像新 Job 到达 85%，但 Cubelet/Shim 在 **10 秒 VM 启动事件超时**后 FAILED。**Cube Template 仍未 READY**、VM 内 OpenCode V2 Server 未测试。证据与复验日志见 [事件 RCA](INCIDENT_20261009.md)。下文仅记录构建过程和历史阶段的状态，不应覆盖此最终进展。

## 为什么此拓扑

- CubeSandbox 官方示例 `examples/opencode-plugin-sandbox` 在 Host 上运行 OpenCode，
  通过 `tool.execute.before` 仅拦截 `bash`；每个 Bash 调用新建一个
  MicroVM，`read/write/edit` 仍写 Host，**编辑后 Bash 看不到同一个文件系统**。
  官方还明确列出 Session ID 键缺失导致状态串联与锁超时继续无锁等限制。
  因此它不满足本项目“同一授权 Session/Sandbox/Workspace 可复用”核心门禁。
  [官方实现与局限](https://github.com/TencentCloud/CubeSandbox/tree/master/examples/opencode-plugin-sandbox)
- 本方案将 OpenCode 的实际 Runtime 置于 Cube MicroVM 内；
  业务 Process/API/模型路由与 Task Facts 在平台外层，仍可由共享平台 Worker
  对多个 Sandbox/OpenCode Server 发送 V2 HTTP 请求。历史 Session 不永久占进程。

## 依赖与复验步骤（仅独立 WSL Docker）

先有官方 `cube-sandbox-int.tencentcloudcr.com/cube-sandbox/sandbox-code:latest`
Guest 基础镜像，以及此前已验证的
`ghcr.io/anomalyco/opencode:2.0.24`。
OpenCode 2.0.24 历史 Docker 镜像 ID：
`sha256:9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315`。

```sh
docker build -f poc/opencode_sandbox/opencode2_cube_template/Dockerfile \
  -t <your-oci-registry>/ahp-opencode2-cube:2.0.24 \
  poc/opencode_sandbox/opencode2_cube_template
# docker build 的 RUN opencode --version 必须成功
docker push <your-oci-registry>/ahp-opencode2-cube:2.0.24
cubemastercli tpl create-from-image \
  --image <your-oci-registry>/ahp-opencode2-cube:2.0.24 \
  --writable-layer-size 1G \
  --expose-port 49983 --expose-port 49999 --expose-port 4096 \
  --probe 49999
# cubemastercli tpl watch --job-id <job-id> ; 直到 Template READY
```

- **不要**把 Docker-daemon 内的本地镜像 ID 直接交给 CubeMaster CLI：
  `create-from-image` 读取 OCI Registry，通常需要先 Push。
- 镜像消耗真实磁盘与内存；这是功能 POC，不等于官方生产资源容量。
- 不在 Dockerfile 写入任何模型/API Key。Cube 启动后按授权上下文注入，
  对 V2 Server 设置临时认证，并执行至少两个 Session、FS/Shell/Git 与外部
  OpenAI/Pydantic SDK 同 Sandbox ID 接力；数据面路由需暴露 4096。
- 遇到 ABI/动态依赖不兼容，`RUN opencode --version` 明确失败，不允许跳过
  再声称 Template 能运行。
- 创建成功后按 Sandbox Lease 生命周期关闭 OpenCode 并 Kill/Pause VM；
  不把一个长期历史 Session 固定到一个 VM/Worker 进程。

## 本地实际构建记录（2026-10-09）

1. 从 Windows Docker Desktop 现成 OpenCode 2.0.24 镜像 `docker save`，到隔离 WSL 的 Docker daemon `docker load`（无需重复公网拉取），验证源镜像为 Alpine 3.24.2 amd64，`/usr/local/bin/opencode` 约 204 MB。
2. 独立 WSL Docker 拉取 Cube 官方 `sandbox-code:latest`，Digest `sha256:743d264fad8c9dc9a49f07e931166d24d025363360ae770ca4b70e3f19540944`。
3. 首次 Docker build 因 `ARG` 作用域失败；修正后仅 COPY 二进制，在 Cube Debian guest 内 `opencode --version` exit 127（缺 musl loader）。
4. 运行 `ldd /usr/local/bin/opencode` 确认依赖 `/lib/ld-musl-x86_64.so.1`、`libstdc++.so.6`、`libgcc_s.so.1`；改为 copy 到 OpenCode 私有路径，OpenCode 专用 wrapper 设置 `LD_LIBRARY_PATH`，不污染 Cube envd 的动态库路径。
5. **真实 build PASS**：`RUN /usr/local/bin/opencode --version` 输出 `opencode v2.0.24`；生成本地 OCI image `ahp-opencode2-cube:poc` / ID `825b61c967d0`。注意这个只是 Docker 镜像构建/ABI smoke，不等于 Cube 内启动、Server 鉴权、Session 或文件隔离合约通过。

**本地 Registry Push 已通过（新增证据）：** 最初 WSL Docker 直接拉取 `registry:2` 遇 Docker Hub HTTP 连接重置，改走国内镜像站 `docker.m.daocloud.io/library/registry:2` 后成功。只在独立 WSL Docker 启动临时 `ahp-cube-local-registry`，监听 `127.0.0.1:5000`，经过 `/v2/` 健康重试后，`docker push localhost:5000/ahp-opencode2-cube:2.0.24` **PASS**，Registry 返回 Manifest Digest `sha256:825b61c967d09e94e9fb42fdc192796952a03842ec6fc3e9dff88f0d9e70679c`。该 Registry 为**HTTP 本机临时 POC**，不等于 CubeMaster/Cubelet 已能拉取；下一步需真实 `cubemastercli tpl create-from-image --image localhost:5000/...`。生产 Registry 必须使用可信 TLS/认证，勿将该 HTTP 配置作为生产方案。

## 后续验收

记录 Template Digest / TemplateID / READY、Cube Sandbox ID、
`opencode --version`、V2 `POST /api/session` 两 Session、真实
`/api/shell`/文件/Git、跨 Harness 读写以及 finally Kill。
完整隔离的生产门禁依然适用。
