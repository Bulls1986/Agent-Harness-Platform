"""Inspector capability verification catalog and read-only PG evidence.

This is an explanation/observability surface, NOT an orchestration runtime.
Real Cube Guest proof and physical Worker SIGKILL require trusted execution
attestation. PostgreSQL events alone MUST NOT be labeled real-MicroVM PASS.
"""
from __future__ import annotations

from poc.closed_loop.facts import PgFacts


SCENARIOS = [
    {
        "id": "agent-handoff",
        "title": "双 Agent 跨 SDK 接力",
        "use_case": "产品 Agent 完成需求整理后，将结构化结果安全交给另一套 SDK 的审核 Agent。",
        "capability": "同一 Run 内真实调用两套不同 Agent SDK；以已保存的上一步输出驱动下一步，最终由 Harness 持久化结果。",
        "execution_steps": [
            "提交业务输入并在 PostgreSQL 创建 Run",
            "Hatchet 调度节点 A（Pydantic AI）",
            "Harness 持久化 A 的输出，节点 B（OpenAI Agents SDK）接收原输出",
            "确认 Run 终态和最终输出可刷新恢复",
        ],
        "required_evidence": [
            "相同 Run ID、Hatchet Workflow ID 与两个 SDK 节点",
            "节点 B 的真实输入与已持久化节点 A 输出一致",
            "Run 最终结果来自节点 B，PG 只出现一次业务完成事件",
        ],
        "limitations": "默认确定性本地模型只验证 SDK/调度/数据接力，不能证明模型产生真实需求分析；不含 Cube。",
        "availability": "EXECUTABLE_EXISTING_TAB",
        "verified_by_inspector": False,
    },
    {
        "id": "public-api-agent-run",
        "title": "DEV-M7 · 公共 API 发起真实双 Agent Run",
        "use_case": "产品/研发客户端通过统一的 Conversation → Turn → Run API 提交任务，不直接调用 Hatchet 或依赖 Inspector 旧调试接口。",
        "capability": "受信任的本地演示身份调用已合并的版本化公共 API：冻结 Agent/Recipe、幂等创建 Run/Outbox，交给原 Hatchet Worker；两套 SDK 执行后通过授权 API/SSE 查看持久状态和结果。",
        "execution_steps": [
            "创建 Conversation 并选定 Turn 的 Agent/Recipe 引用",
            "携带 Idempotency-Key 调用公共 API 创建并启动 Run",
            "Hatchet 调度 Pydantic AI → OpenAI Agents SDK，Harness 写入 Step/业务终态",
            "通过公共 API 获取 Workflow ID、Typed Event、两个节点结果和最后输出",
        ],
        "required_evidence": [
            "同一 Conversation/Turn/Run ID 和真实 Provider WorkflowRun ID",
            "两个 SDK 的持久 Step 输出、Run.COMPLETED 与最终来源节点",
            "幂等 HTTP 提交不产生第二个 Workflow；事件序号可恢复",
        ],
        "limitations": "仅显式启用的本地 Inspector 开发环境，使用服务端固定合成身份；不证明企业 Gateway/IdP、外部 LLM、M5 Cube 或生产准入。只能凭实际 Run 事实说明本次执行结果。",
        "availability": "READ_ONLY_NOT_EXECUTABLE",
        "verified_by_inspector": False,
    },
    {
        "id": "cube-workspace",
        "title": "Cube Sandbox Workspace 恢复",
        "use_case": "研发 Agent 中断或更换执行者后，继续在原文件工作空间读写，无需从空目录重新开始。",
        "capability": "真实 Cube 创建与重连，同一个 Sandbox ID / WorkspaceRef 保持文件内容；Harness PG Fencing 拒绝失效 Owner。",
        "execution_steps": [
            "Harness 创建带 Scope、WorkspaceRef 和 Owner/Epoch 的持久 Binding",
            "Worker A 在原生 Cube Guest 中写入校验文件",
            "将 PG Owner A / Epoch 7 转移给 B / Epoch 8",
            "Worker B 连接原 Sandbox、比对真实 Guest 字节、销毁并确认释放",
        ],
        "required_evidence": [
            "原生 Cube Sandbox ID 在交接前后完全一致",
            "原 Guest 文件字节一致，旧 Owner 的读写被拒绝",
            "PG Binding/Transfer/Release 与 Native Cube Destroy ACK",
        ],
        "limitations": "Inspector 尚未接入可信 Cube 场景启动器；仅查看 PG 事实不能证明执行了真实 Guest 文件操作或隔离。",
        "availability": "READ_ONLY_NOT_EXECUTABLE",
        "verified_by_inspector": False,
    },
    {
        "id": "worker-takeover",
        "title": "Hatchet Worker 故障接管",
        "use_case": "Agent Worker 被异常终止，其他 Worker 接手未完成的任务并继续使用原 Cube Workspace。",
        "capability": "技术重试由 Hatchet 负责；新的独立 Worker 按 Harness PG Fencing 接管原 Execution，复用同一原生 Sandbox 而不是创建空 Workspace。",
        "execution_steps": [
            "独立 Worker A 领取原生 Hatchet Task 并写入 Cube Guest",
            "控制端确认写入后对 A 的整个 OS 进程组执行 SIGKILL",
            "独立 Worker B 领取同一 Workflow 的 Hatchet Native Retry",
            "B 按最新 Epoch 恢复原 Cube 数据、验证身份并释放资源",
        ],
        "required_evidence": [
            "Worker A 真实 PID、SIGKILL 退出码 -9、Worker B 不同 PID",
            "同一 Hatchet Workflow ID 与原生 Task Retry 计数",
            "同一 Cube Sandbox ID、原始 Guest 校验内容、Epoch 递增与 Release",
        ],
        "limitations": "物理 Hatchet + Cube 的联合 Gate 尚未通过时绝不能显示 PASS；PG 事件无法替代 OS SIGKILL 与真实 Guest 证据。",
        "availability": "READ_ONLY_NOT_EXECUTABLE",
        "verified_by_inspector": False,
    },
    {
        "id": "tool-receipt",
        "title": "非幂等 Tool 未知结果安全恢复",
        "use_case": "Agent 调用付款、审批或其他不能随意重试的外部操作，外部提交后 Worker 故障或返回 ACK 丢失。",
        "capability": "Harness 持久化 Intent/Receipt；状态 UNKNOWN 时不重发操作，而是查询可信外部证据，阻止重复副作用。",
        "execution_steps": [
            "执行外部 Tool 前提交不可重复的 Intent",
            "外部副作用落盘后注入进程故障/丢 ACK",
            "将状态记为 UNKNOWN，禁止盲目重派发",
            "仅凭可信唯一外部证据确认 Receipt 或继续维持 UNKNOWN",
        ],
        "required_evidence": [
            "独立外部系统的真实副作用计数仅有一次",
            "UNKNOWN → Receipt Confirmed 的 PG 事件与 Fencing",
            "多匹配、无匹配或旧 Owner 请求均安全拒绝",
        ],
        "limitations": "PG Receipt 事件本身不能证明独立外部账本恰有一次写入；Inspector 尚未提供真实 Tool 故障执行器。",
        "availability": "READ_ONLY_NOT_EXECUTABLE",
        "verified_by_inspector": False,
    },
]

_EVENT_ALLOWLIST = {
    "workflow.bound", "step.completed", "run.completed",
    "tool.dispatched", "tool.outcome.unknown",
    "tool.receipt.confirmed", "tool.recovery.owner.transferred",
    "sandbox.binding.requested",
    "sandbox.binding.creation_dispatched",
    "sandbox.binding.confirmed",
    "sandbox.binding.unknown",
    "sandbox.binding.reconciled",
    "sandbox.binding.transferred",
    "sandbox.binding.released",
}


def catalog(*, m7_demo_enabled: bool = False) -> dict:
    scenarios = [dict(s) for s in SCENARIOS]
    for scenario in scenarios:
        if scenario["id"] == "public-api-agent-run":
            scenario["availability"] = (
                "EXECUTABLE_M7_CAPABILITY_TAB" if m7_demo_enabled
                else "READ_ONLY_NOT_EXECUTABLE"
            )
    return {
        "scenarios": scenarios,
        "production_ready": False,
        "evidence_note": (
            "只有显式启用的本地 M7 公共 API 场景可发起普通双 SDK Run；其他 Cube、Worker 故障和非幂等 Tool 场景仍只读。只有可信运行器返回完整实机验证证据后，"
            "才能将物理 Worker / 真实 Cube / 非幂等效果标为通过；单凭 PostgreSQL 事件不构成证明。"
        ),
    }


def evidence(db: PgFacts, run_id: str) -> dict:
    """Inspect a persisted Run; never execute external Tools or launch Cube."""
    with db.tx() as c:
        run = c.execute(
            "SELECT state,provider_workflow_id FROM harness_run WHERE id=%s",
            (run_id,),
        ).fetchone()
        if run is None:
            raise KeyError(run_id)
        rows = c.execute(
            "SELECT type FROM harness_event WHERE run_id=%s ORDER BY seq",
            (run_id,),
        ).fetchall()
        cube = None
        if c.execute(
            "SELECT to_regclass('harness_cube_binding') IS NOT NULL"
        ).fetchone()[0]:
            bindings = c.execute(
                "SELECT execution_id,provider_sandbox_id,workspace_ref,"
                "owner_id,fencing_epoch,state,binding_generation "
                "FROM harness_cube_binding WHERE run_id=%s "
                "ORDER BY execution_id LIMIT 2",
                (run_id,),
            ).fetchall()
            if len(bindings) == 1:
                item = bindings[0]
                cube = {
                    "execution_id": item[0],
                    "sandbox_id": item[1],
                    "workspace_ref": item[2],
                    "owner_id": item[3],
                    "fencing_epoch": item[4],
                    "state": item[5],
                    "generation": item[6],
                }
        receipt = []
        if c.execute(
            "SELECT to_regclass('harness_tool_intent') IS NOT NULL"
        ).fetchone()[0]:
            rec = c.execute(
                "SELECT execution_id,state FROM harness_tool_intent "
                "WHERE run_id=%s ORDER BY execution_id LIMIT 20",
                (run_id,),
            ).fetchall()
            receipt = [{"execution_id": eid, "state": state} for eid,state in rec]
    observed = list(dict.fromkeys(kind for (kind,) in rows
                                  if kind in _EVENT_ALLOWLIST))
    return {
        "run_id": run_id,
        "run_state": run[0],
        "provider_workflow_run_id": run[1],
        "observed_events": observed,
        "cube_binding": cube,
        "tool_receipts": receipt,
        "evidence_level": "PERSISTED_FACTS_ONLY",
        "verified": False,
        "limitations": (
            "仅为持久数据库观察结果；无法凭这些字段证明真实 Cube Guest 字节、"
            "OS 进程 SIGKILL、Hatchet Worker B 接管或外部非幂等写入次数。"
        ),
    }
