# DEV-M5 · 真实 Cube/PG 联合验证与原始收口门禁（2026-10-13）

## 状态与结论

**DEV-M5 ACTIVE。** 完成真实 Cube MicroVM + Harness PostgreSQL Binding / WorkspaceRef / Lease / Fencing / Destroy 的集成实机验证。**真正的物理 Hatchet Worker A SIGKILL→B Native Retry→相同 Cube Workspace Guest 的联合门禁尚无 PASS**，不得勾选原 1.3 / 2.1～2.3，也不得归档。严格复用原 M5 OpenSpec 1.1～2.3、A.1～A.6；不增加 A.7/新调度器，不修改 M3/M4/M7 和 Production NO-GO。

## TDD / 根因 / 代码最小修复

- Red：真实 PostgreSQL 上，原 Native SDK Mock 创建测试先改为校验冻结 Cube 模板，实际报错 expected Sandbox.create(template=tpl-synthetic,metadata=...) but actual Sandbox.create(metadata=...)。
- Green：NativeCubeTransport.create 仅补传 CUBE_TEMPLATE_ID；M5 真实 PostgreSQL 合同 **14/14 PASS，0 SKIPPED**。此修复保持原 PG 创建屏障、UNKNOWN 禁止盲重试、Scope/Workspace/Owner/Epoch 核验；真实 Cube Endpoint/Template 缺失仍 Fail Closed。
- 原 Cube 服务复用 WSL2 CubeAPI/CubeMaster/Cubelet/Proxy，KVM 存在、真实 READY 模板。Guest 文件连接曾因本机 CubeProxy 域名无法解析失败；按官方 SDK 的本机代理选项 CUBE_PROXY_NODE_IP=127.0.0.1 后，Native SDK 实际 Sandbox.create→Guest Files→Native connect(same ID)→kill 全部成功。不把 Host 文件冒充 Guest 文件、不在仓库硬编码本机代理 IP。

## 已证实的真实 Cube + Harness PG 联合证据

**PASS_REAL_CUBE_MICROVM**：合成 Run m5-cube-live-42e3c6491d95489d94ade599f48ca9d2；原生 Cube Sandbox cf6d5b80f0a1468d84bcbc91d0ac86bb；WorkspaceRef workspace-m5-cube-live-42e3c6491d95489d94ade599f48ca9d2。A/7 在真实 Guest 写入合成字节，PG 时钟 Lease 到期后 B/8 接管，独立 Cube SDK 连接同一 Sandbox ID，逐字节读回原内容；旧 A/7 拒绝；真实 Cube Destroy ACK、PG 状态 RELEASED。异常测试后检查原生 Sandbox 清单为 0，未对 UNKNOWN 原 Allocation 盲目重建。

## 尚不能宣称已通过的原定 Gate

- 实际 Hatchet Worker A 的操作系统进程组 SIGKILL→独立进程 Worker B 真 Native Retry，并连回先前同一 Cube，读取原 Guest 数据、PG Epoch 8 和释放；现有 WSL feature 测试脚本纳入本 PR 的显式 M5 Cube Live Gate，**运行尚无成功结果**。
- OpenCode Shell/Files/Git 的 Guest 权限、跨 Scope/旧 Owner、model-only 0 Sandbox、OCI/Guest 完整隔离等原验收安全矩阵，必须按现有合同正/负例复核后才能勾选 1.1/1.3/1.4/2.1。
- WSL 物理测试首次卡在下载 Hatchet Embedded Sidecar。后来复用 Inspector Docker 中 v0.110.5 的同 SHA-256 本地 Linux ELF（18ddacae0005042bd982328bcb8d370cca6907352a1ab2a3c8406001d31e7dee），避免新增外部下载依赖；物理实机重新执行未取得 PASS，**不能把二进制校验 PASS 充当 Worker 接管证明**。
- 普通 dev-m5-cube-binding.yml 仅真实 PG + Fake Native Transport 和官方 SDK 方法形状；显式 dev-m5-cube-live.yml 需真实配置 Cube Endpoint、READY Template、Proxy 以及真实 Hatchet 执行。无 Endpoint/Template 时必须失败、不 SKIP、不冒充真 Cube 验收。

## 收口约束

只有以上原始事项全部通过且官方最新 Head CI/架构/失败注入/复盘可查，才关闭 DEV-HC-03、勾选阶段 Tasks 并归档。期间保持 DEV-M5 ACTIVE、平台 Production NO-GO。不上传私有 PDLC 资料，也不扩充出第二套执行引擎、企业 IAM、OSS 或 MCP 治理。
