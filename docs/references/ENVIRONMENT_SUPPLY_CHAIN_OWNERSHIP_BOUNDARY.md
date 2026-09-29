# Environment Supply Chain Ownership Boundary

> 状态：Accepted Architecture Boundary  
> 日期：2026-09-29  
> 对应待办：ARCH-TODO-014

## 核心决策

Environment / OCI Supply Chain Security 不属于 Harness Platform 核心职责。

Harness 不实现：

- OCI provenance；
- SBOM generation/storage；
- image signing；
- signature verification service；
- vulnerability scanning；
- base image / dependency security policy；
- supply-chain attestation；
- security promotion workflow。

这些能力由企业 CI/CD、Artifact Registry、Container Security / Supply Chain Security 基础设施负责。

Harness 只消费：

- Environment Profile / version；
- immutable OCI digest；
- capability；
- verification status；
- optional external attestation/reference。

Run / Execution 继续冻结并记录实际使用的 Environment version / digest，以保证可追踪与可复现。

如果外部安全平台返回 verification / admission decision，Harness 可以把结果作为 metadata 或 Policy/Admission input 使用，但不拥有其内部模型、扫描流程或生命周期。

## Accepted Rules

1. Supply Chain Security 是外部基础设施责任。
2. Harness 只消费最终环境元数据与不可变 digest。
3. Harness 不建设 SBOM、签名、扫描、证明或镜像安全治理产品。
4. Environment correctness / reproducibility 仍属于 Harness 关注范围；Supply Chain Security 不属于。
5. 未来若要把供应链安全内建到 Harness，必须新立架构决策。