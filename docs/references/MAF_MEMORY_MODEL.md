# Microsoft Agent Framework Memory / Context 设计

> 状态：讨论参考  
> 时间基线：2026-09-29

## 1. 核心结论

MAF 的“记忆”不是单一 Memory Service，而是拆成多个不同生命周期和职责的层次：

~~~text
MAF Memory / Context
├─ Conversation Memory
│  └─ AgentSession / History
├─ Working Memory
│  └─ Plan / Todo / Mode / Harness State
├─ Long-Term Memory
│  ├─ FileMemoryProvider
│  └─ ChatHistoryMemoryProvider
├─ External Context
│  └─ ContextProvider / RAG / Profile / Enterprise Data
└─ Context Window Management
   └─ Compaction
~~~

这个拆法值得 Agent Harness Platform 借鉴，因为 Session、Working Memory、Long-Term Memory、RAG 和 Compaction 本质不同，不应该全部塞进一个 MemoryService。

## 2. Conversation Memory

AgentSession 负责保存一次会话中持续存在的历史和状态。

它解决：

> “这次会话之前发生了什么？”

典型内容：

- user / assistant message
- tool call / tool result
- agent session state
- provider/context provider scoped state

它对应平台中的 Conversation / Session 层，而不是长期用户记忆。

## 3. Working Memory

HarnessAgent 的 Plan、Todo、Mode、当前执行状态更接近 Working Memory：

~~~text
Task
├─ Plan
├─ Todo
├─ Current Mode
├─ Current Step
└─ Working State
~~~

它解决：

> “当前任务做到哪里？”

这部分应该映射到平台的 Run / Plan / Step State，而不应混入长期 Memory。

## 4. Long-Term Memory

### FileMemoryProvider

更接近 Agent 主动维护的长期笔记。

关键特征：

- Agent 可以主动写入/读取 memory
- 底层存储可以抽象
- scope 决定记忆边界
- scope 可以按 session / user / tenant / project 等组织

例如：

~~~text
scope = user-1001
Session A ─┐
           ├─ User Memory
Session B ─┘
~~~

### ChatHistoryMemoryProvider

更接近自动语义历史记忆：

~~~text
conversation history
      ↓
embedding / vector store
      ↓
semantic retrieval
      ↓
inject relevant history into current context
~~~

它与 FileMemoryProvider 的区别：

- FileMemory：显式、主动、结构化/半结构化长期记忆
- ChatHistoryMemory：自动从历史对话建立语义检索记忆

## 5. ContextProvider

ContextProvider 是 MAF 最值得借鉴的抽象之一。

从模型调用视角：

- Memory
- RAG
- User Profile
- Tenant Profile
- Repository Context
- Architecture Rules
- External Data

本质上都是“本次调用需要注入的 Context”。

因此可以统一成 Provider：

~~~text
ContextProvider
├─ ConversationHistoryProvider
├─ WorkingMemoryProvider
├─ UserMemoryProvider
├─ ChatHistoryVectorProvider
├─ RepositoryContextProvider
├─ RAGProvider
└─ TenantProfileProvider
~~~

Provider 的差异主要体现在：

- scope
- lifecycle
- retrieval
- persistence
- priority
- token budget
- update policy

## 6. Compaction

Compaction 不是 Memory。

~~~text
Memory
= 应该长期记住什么

Compaction
= 当前上下文怎样在 token window 中装得下
~~~

因此平台应把 Context Window Manager 与 Memory Store 分开。

## 7. 对 Agent Harness Platform 的映射

~~~text
MAF AgentSession
        ↓
Conversation / Session Store

MAF Plan / Todo
        ↓
Working Memory / Run State

MAF FileMemoryProvider
        ↓
Explicit Long-Term Memory

MAF ChatHistoryMemoryProvider
        ↓
Semantic Conversation Memory

MAF ContextProvider
        ↓
Context Provider SPI

MAF Compaction
        ↓
Context Window Manager
~~~

## 8. 架构建议

平台的 Context Engine 建议调整为：

~~~text
Context Engine
├─ Session Context
├─ Working Memory
├─ Long-Term Memory
├─ Retrieval Context
├─ User / Tenant Context
└─ Compaction
~~~

并以 ContextProvider 作为统一扩展抽象，而不是建立一个职责过大的 MemoryService。
