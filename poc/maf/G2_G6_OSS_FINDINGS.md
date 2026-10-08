# POC-A / A15-G2 Workspace + OSS Payload 真实集成

> 2026-10-09：独立 Docker SeaweedFS 3.99 S3 兼容 Provider + 独立 PostgreSQL，真实对象上传、下载、SHA-256、Workspace 文件恢复、引用保护和保留墓碑 **3/3 PASS**。不是企业现有 OSS 的生产验收。

## 平台拥有的内容（不复制外围服务）

- `poc_payload_refs` 仅存 Artifact/Evidence/Workspace 的逻辑 ID、Run/Step/Attempt/Execution 血缘、Kind、媒体类型、SHA-256、大小、外部 Object Key、Retention Policy Reference、Payload Status 和 Tombstone；二进制只进入 S3 Provider。
- `PayloadRefStore` 以外部 S3 标准 Put/Get/Delete 操作，不实现 OSS 引擎。上传先验证平台血缘，再 Put，再写 PG Metadata；失败尝试清理孤儿对象。**两库/OSS 并非原子分布式事务。**
- `RecoveryPoint` 可引用 Workspace Payload ID，Evidence/Artifact 可绑定到对应 RecoveryPoint 的 PIN；只有真正进入终态的 Run 才能按策略 Purge 对象；依赖仍被可恢复 Run 引用时拒绝清理。
- 每次读取将对象 Bytes 与 PostgreSQL 中保留的 SHA-256 和大小核对，不一致即 `PayloadIntegrityError`；工作区文件恢复限定可信根目录、拒绝越界/符号链接并使用同目录临时文件原子替换。
- 删除策略 `AVAILABLE → PURGE_PENDING → PURGED`，OSS 删除完成后仅清除 Object Key，保留历史的 Payload ID、Digest、Lineage 和 PurgedAt；中断可重试，不宣称 PG+OSS 分布式事务。

## 已实测

在独立 Docker 容器和临时端口中执行 `python poc/maf/verify_oss_acceptance.py`：

1. Artifact/Evidence/Workspace 三类真实 `put_object` 和 `get_object`，可还原 Workspace 文件原始 Byte 且 Hash 一致；RecoveryPoint PIN 阻止 RUNNING Run 的 GC，终态后对象删除 + PG Tombstone 保留。
2. 在 OSS 侧实际覆盖原 Object Key 为错误内容，下载 Hash 校验失败且不写回 Workspace 文件。
3. 不同 Run 的 RecoveryPoint 不可 PIN 另一 Run 的 Evidence，伪造 Run 与 Execution 身份不能入库。

**3/3 PASS**。容器由验收脚本自动创建、退出时清理；与其他项目的 OSS 服务完全独立。`requirements-oss.txt` 将 S3 SDK 作为可选依赖；默认无 S3 配置时本用例 SKIP 而不是虚构 PASS。

## 门禁边界

- SeaweedFS 是受控自托管 S3-compatible Provider，不是用户真实生产 OSS；生产 IAM/Policy/存储 HA/长期保留生命周期均属于外围能力，本平台只维护事实和引用约束。
- 本实验恢复的是一个经 Digest 保护的 Workspace 文件，没有演示完整代码库/多文件 Workspace revision set、Sandbox 文件挂载或 Provider Snapshot。真正 Restore 由 Workspace Adapter 执行。
- 无真实企业 OSS Endpoint 及 Provider 长期 retention / 跨 Region 故障注入；G2/G6 整体仍 PARTIAL/GAP。
