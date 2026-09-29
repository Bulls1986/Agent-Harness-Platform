# Control Plane / Data Plane 边界说明

> 状态：讨论参考

## 1. 核心定义

### Control Plane / 控制平面

负责：

- 现在任务处于什么状态
- 下一步做什么
- 谁来做
- 是否允许做
- 失败后 Retry / Replan / Abort / Wait Human
- 是否达到完成条件
- Budget / Policy / Approval / Recovery

一句话：

> **决定“做什么、谁来做、做完之后怎么办”。**

### Data Plane / 执行平面

负责：

- 模型调用
- Agent Runtime
- Shell
- Git
- Filesystem
- Browser
- MCP
- Database
- Sandbox
- Code Execution

一句话：

> **负责“真的把事情做掉，并返回结果/证据”。**

## 2. 为什么 Control Plane 不跑 shell

错误设计：

~~~text
Harness Kernel
├─ Workflow
├─ Git
├─ Shell
├─ Docker
├─ npm
├─ Browser
└─ Deploy
~~~

结果是 Kernel 变成巨型单体，权限边界与执行环境耦合。

正确设计：

~~~text
Control Plane
  │ "执行测试"
  ↓
Execution Command
  ↓
Data Plane / Sandbox
  │ pnpm test
  ↓
ExecutionResult / Evidence
~~~

## 3. 为什么 Sandbox 不决定业务 Workflow

错误设计：

~~~text
Executor
发现测试失败
  ↓
自行修改目标
  ↓
继续改代码
  ↓
自行重规划
  ↓
自行 push
~~~

这样 Executor 实际上变成了 Orchestrator。

正确设计：

~~~text
Executor
  ↓
只执行当前 Step
  ↓
返回 Result/Evidence
  ↓
Verifier
  ↓
Control Plane
  ↓
Retry / Replan / Complete
~~~

## 4. 允许 Agent 自主到什么程度

可以允许 Agent 在 **一个 Step 内部** 做有限的工具循环：

~~~text
read
→ search
→ edit
→ test
→ inspect
~~~

但需要受以下条件约束：

- max_iterations
- max_runtime
- max_cost
- capability policy
- sandbox boundary
- step acceptance criteria

Agent 无权自行修改整个业务目标或越过审批。

## 5. 与 Temporal / MAF / ADK 的映射

### Temporal

~~~text
Temporal Workflow = Control Plane
Activity / Agent / Sandbox = Data Plane
~~~

### MAF

可由 Workflow 承担更高层 Control Plane，HarnessAgent 作为 Agent execution/harness。

### ADK

可将 ADK 作为 Java Agent Runtime / orchestration 组件；平台仍保留最终 Run/Policy/Artifact 控制权。

## 6. 最终原则

> Control Plane 不直接执行副作用操作。  
> Data Plane 不拥有平台业务状态机最终控制权。  
> Agent 可以提出决策，但确定性状态迁移由平台代码裁决。
