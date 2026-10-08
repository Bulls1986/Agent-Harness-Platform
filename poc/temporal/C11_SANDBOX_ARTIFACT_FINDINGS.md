# POC-C C11 — SandboxProvider SPI / Object Storage Artifact & Evidence

> 2026-10-08 | 本机真实 Docker + SeaweedFS S3 + 双 PG + Temporal 技术链路 **PASS**；Linux CI 待核对。

## 架构责任边界

- Temporal 只执行**确定性** Workflow 调度，原生 History 仅承载短
  Artifact/Evidence ID、Digest/Storage Ref，不承载文件大 Payload；
  Sandbox/OSS/PostgreSQL 均位于独立 Activity/Data Plane。
- Harness PostgreSQL 独立拥有 Run/Plan/Step/Attempt/Execution，
  冻结 Native Workflow/Sandbox Image、Artifact/Evidence 的逻辑身份、
  Lineage、Digest、Size、S3 引用、Recovery Pin、Tombstone。
- 大 Payload 通过通用 S3 API 存在 SeaweedFS 3.99，物理对象独立于
  Harness 数据库；Object Storage 生命周期/备份/副本机制不属于 Harness。
- 两个真实受限 Sandbox 执行模式分别为
  `docker-oneshot` 和 `docker-session`，共享同一个 Docker Engine。
  **这验证 SandboxProvider SPI 在真实隔离执行下切换，
  不是两种生产隔离产品，也没有验证 CubeSandbox。**
  企业生产第一候选仍是 CubeSandboxProvider
  （`EXECUTION_SANDBOX_ARCHITECTURE.md`、
  `CONTROL_DATA_PLANE.md` Accepted Boundary）。

## 本地实测结果

`python poc/temporal/verify_c11_real_s3.py` 通过：

| 指标 | 本地实际值 |
|---|---|
| Temporal | 非 `start-dev` OSS 1.31.0 + 专属 PostgreSQL |
| Harness | 第二套独立 PostgreSQL |
| Sandbox | 两个独立 Docker 容器执行模式；均无网络、只读根 FS、non-root、cap-drop ALL、CPU/Memory/PID 限制，tmpfs、无宿主机工作区映射 |
| Artifact | 2 个逻辑对象，各 **262,160 bytes** 的真实文件 |
| Evidence | 2 个独立 Verify S3 GetObject + SHA256 成功，另写 2 个 S3 Evidence 文件 |
| Harness 事件 | 6 条：Run Started、Artifact Created/Verification Passed ×2、Run Terminal |
| Native History JSON | **29,369 bytes**，未包含 262KiB 文件内容 |
| GC/PIN | PIN 的 Artifact Purge 被 PG Trigger 拒绝；终态 Run 显式解除 PIN、执行 S3 DELETE 后保留 PG Tombstone/Digest/Lineage |
| Run | `COMPLETED`，2 个 Attempt/Execution 验证成功 |

另有 **4 项真实 PostgreSQL 负例 PASS**：冻结 Sandbox 映射不可改、
伪造 lineage/digest 不能录入或改写、Active Run 的 PIN 不可解除/
Payload 不可删除、终态显式 Release/Purge 后仍保留只读 Tombstone。

## 独立可重复验证

S3 Docker 镜像固定
`chrislusf/seaweedfs@sha256:8d5b323911a996d5ea152115306bed468d9a849d72bcbb3800ea8d91b7728563`。
本地 S3 endpoint **只能绑定 127.0.0.1**，当前 POC
Gateway 没有企业 IAM，绝不可直接发布到公网/企业生产网络。
旧 MinIO 镜像无法匿名拉取，不影响 S3 协议测试及 OSS 产品中立性。

使用 `compose-oss-postgres.yml`、`compose-platform-pg.yml`、
`compose-objectstore.yml` 启动三个相互独立的基础服务。
`requirements-c11.txt` 仅增加 boto3；设置本机可信环境的
`POC_C_PLATFORM_DSN`、`POC_C_TEMPORAL_ADDRESS`、
`POC_C11_S3_ENDPOINT` 后运行：

```bash
python -m unittest discover -s poc/temporal/tests -p 'test_c11_artifact_pg.py' -v
python poc/temporal/verify_c11_real_s3.py
```

GitHub CI 会独立启动实际 OSS Temporal + 两套 PostgreSQL +
SeaweedFS S3 + Docker Container，验证与本机相同的原生 Workflow。
不提供真实模型凭据、不使用生产 Bucket 或企业 Secret。

## 仍未验收 / 不过度承诺

- **CubeSandbox Local/Remote API、真正不同 Sandbox 技术替换**、
  MicroVM、安全逃逸审计、Snapshot/Pause/Resume/真实 Coding
  workload、跨物理主机弹性调度未验收；不可把 Docker Adapter
  PASS 写成生产 CubeSandbox G5 PASS。
- 当前 Docker 容器只运行**受控无害 Fixture**，不执行模型生成的
  任意代码；安全隔离参数不代表完整生产安全认证。
- S3 Put 与 PG 元数据提交没有分布式事务。S3 成功后 PG 失败
  可能形成孤立 Payload，需要后续可信对账/保留策略；
  Delete 和 Tombstone 更新也不具有跨系统原子性。
- 只验证受控显式 PIN/Release/PURGE，不实施自动对象 Retention/
  Governance/DR、真实企业 OSS 身份认证与 Bucket ACL。
- 整体 POC-C G2/G5/G6 仍需最终评估，C11 scoped 结果不能
  代替整个 Harness 生产验收。

**本轮 C11 证明：真实隔离 Data Plane 的两种 Docker Adapter 模式
可以返回相同对象引用契约，Artifact/Evidence Payload 存在
独立 S3，Task Facts 与逻辑 Lineage 存在 Harness PG，
Temporal History 不必承载文件内容。**
