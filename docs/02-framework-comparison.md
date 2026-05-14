# 02 — 三大框架深度对比

> 参考了 2025-2026 年多篇行业基准测试与框架官方文档，力求准确。

---

## 🏛️ 架构哲学

### AutoGen：对话即一切

```
┌─────────────────────────────────────────┐
│           AutoGen 世界观                │
│                                         │
│   "Agent 就是会聊天的人"                │
│                                         │
│   工作流 = 多轮对话自然涌现              │
│   灵活性 = 让 Agent 自己决定下一步       │
└─────────────────────────────────────────┘
```

- **核心抽象**：`ConversableAgent` — 每个 Agent 是一个能发消息、收消息、调用工具的对话实体
- **编排方式**：GroupChat + SpeakerSelection，或者自定义的 `register_reply` 逻辑
- **控制粒度**：中等 — 你可以指定谁能发言，但对话走向由 LLM 决定

### CrewAI：团队即一切

```
┌─────────────────────────────────────────┐
│           CrewAI 世界观                 │
│                                         │
│   "Agent 就是团队里的角色"               │
│                                         │
│   工作流 = 角色 + 任务 + 流程           │
│   直觉 = 像管理一个真实团队              │
└─────────────────────────────────────────┘
```

- **核心抽象**：`Agent`（角色）+ `Task`（任务）+ `Crew`（团队）+ `Process`（流程）
- **编排方式**：Sequential（顺序）、Hierarchical（层级经理）、Flow（图流程，2025 新增）
- **控制粒度**：低到中等 — 适合快速搭建，复杂流程需要 Flow 扩展

### LangGraph：图即一切

```
┌─────────────────────────────────────────┐
│           LangGraph 世界观              │
│                                         │
│   "工作流就是一张状态转换图"             │
│                                         │
│   确定性 = 你画的图就是执行路径          │
│   可靠性 = 每个节点状态都能 checkpoint   │
└─────────────────────────────────────────┘
```

- **核心抽象**：`StateGraph` — 节点是函数/Agent，边是流转条件
- **编排方式**：显式图结构（DAG 或带循环的图）
- **控制粒度**：最高 — 每一步走向由你写的条件函数决定

---

## 🔀 编排模型对比

### 可视化：同样是 "研究 → 写作 → 审稿"

**AutoGen（对话驱动）**
```
研究员: "我找到了这些数据..."
写手: "好，我基于这个写"
审稿人: "等等，这个数据有问题"
写手: "那我改一下"
审稿人: "可以了"
     ↓
   [对话结束]
```
*走向不确定，可能写手先写，也可能审稿人先质疑*

**CrewAI（角色流程）**
```
[研究员] ──task──▶ [写手] ──task──▶ [审稿人]
   │                    │                  │
   └────经理协调───────┴────经理协调──────┘
```
*流程明确，经理决定分配*

**LangGraph（状态图）**
```
         ┌─────────────┐
         ▼             │
    ┌─────────┐   ┌───────┐
    │ research│──▶│ write │
    └─────────┘   └───────┘
                       │
                       ▼
                  ┌─────────┐
                  │ review  │──┐
                  └─────────┘  │
                       │ approve? │
                       └──── yes ──┘──▶ [END]
                            no ──▶ [write]
```
*每一步都精确可控*

---

## 📊 生产指标对比（基于 2025-2026 基准测试）

### 任务成功率与恢复能力

| 指标 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| **错误恢复率** | **96%** | 72% | 68% |
| **多步任务准确率** | **94%** | 87% | 91% |
| **GPT-4o 单次任务成本** | **$0.08** | $0.15 | $0.45 |
| **平均 LLM 调用次数** | **4.2** | 6.1 | 22.7 |
| **10 Agent/1K 消息内存占用** | **45MB** | 120MB | 200MB |

> 数据来源：[altersquare.io 基准测试](https://altersquare.io/langgraph-vs-crewai-vs-autogen-review-recommend-production-deployment/)

### 解读

- **LangGraph**：调用次数最少 = 最便宜；恢复率最高 = 最可靠
- **AutoGen**：调用次数最多 = 最贵；但对话灵活，适合需要反复推敲的任务
- **CrewAI**：居中，"够用且不贵"

---

## 🧰 核心能力矩阵

| 能力 | LangGraph | CrewAI | AutoGen |
|------|-----------|--------|---------|
| **Human-in-the-loop** | ✅ 原生支持 | ⚠️ 有限 | ✅ 原生支持 |
| **持久化/Checkpoint** | ✅ 内置 | ⚠️ SQLite 扩展 | ❌ 手动实现 |
| **循环/条件分支** | ✅ 图天然支持 | ⚠️ Flow 扩展 | ⚠️ 需自定义 |
| **并行执行** | ✅ 图分支并行 | ⚠️ 有限 | ⚠️ 有限 |
| **工具调用** | ✅ 通过 LangChain | ✅ 原生装饰器 | ✅ 原生注册 |
| **调试观测** | ✅ LangSmith | ⚠️ 基础日志 | ⚠️ AgentOps |
| **可视化编辑** | ❌ 代码为主 | ✅ CrewAI Studio | ✅ AutoGen Studio |
| **跨语言** | Python/JS | Python | Python/.NET |
| **MCP 协议** | 通过 LangChain | 社区支持 | 有限 |
| **A2A 协议** | ❌ | ✅ | ❌ |

---

## 🎭 开发者体验

### 上手速度

| 任务 | CrewAI | AutoGen | LangGraph |
|------|--------|---------|-----------|
| "跑起来第一个 demo" | **5 分钟** | 10 分钟 | 15 分钟 |
| "做出生产可用版本" | 2-3 天 | 1-2 周 | 2-3 周 |
| "三行代码搭流水线" | ✅ | ❌ | ❌ |
| "三十行代码搭复杂流程" | ⚠️ | ✅ | ✅ |

### 代码量对比：同一个 "研究+写作" 任务

**CrewAI（最简洁）**
```python
researcher = Agent(role="研究员", goal="搜索", tools=[search])
writer = Agent(role="写手", goal="写作")
task = Task(description="研究 AI Agent 融资", agent=researcher)
task2 = Task(description="写简报", agent=writer)
Crew(agents=[researcher, writer], tasks=[task, task2]).kickoff()
```

**AutoGen（中等）**
```python
researcher = ConversableAgent("研究员", llm_config={...})
writer = ConversableAgent("写手", llm_config={...})
researcher.register_function(search)
groupchat = GroupChat(agents=[researcher, writer], messages=[])
manager = GroupChatManager(groupchat=groupchat)
manager.initiate_chat("研究并写简报")
```

**LangGraph（最显式）**
```python
def research_node(state): ...
def write_node(state): ...
graph = StateGraph(State)
graph.add_node("research", research_node)
graph.add_node("write", write_node)
graph.add_edge("research", "write")
graph.add_edge("write", END)
app = graph.compile()
app.invoke({"topic": "AI Agent 融资"})
```

---

## 🔍 各自的天花板与短板

### LangGraph

**天花板**
- 可以构建任意复杂的、带循环的、条件分支的状态机
- 100+ Agent/节点的大型工作流也能 hold 住
- 审计、金融、医疗等合规场景的首选

**短板**
- 学习曲线陡：要理解图论、状态管理、checkpoint 机制
- 代码量大：简单的任务也要写很多"样板"
- 调试需要 LangSmith 配合

### CrewAI

**天花板**
- 3-8 个 Agent 的团队最舒服
- 内容生产、SEO、销售自动化等角色明确的场景
- 快速原型验证

**短板**
- 超过 10 个 Agent 后层级管理容易崩
- 动态工作负载下弹性不足
- 没有内置的精确状态恢复（只有任务级隔离）

### AutoGen

**天花板**
- 多轮对话、辩论、迭代优化的场景很强
- 代码生成 + 执行 + 调试的闭环
- 研究实验、学术探索

**短板**
- 对话容易"漂移" — Agent 忘了最初要干啥
- 长对话上下文窗口爆炸
- 没有 checkpoint，崩了从头来
- 生产成本高（22 次调用 vs 4 次）

---

## 📖 一句话总结

```
LangGraph = 控制狂的终极武器
CrewAI   = 快速出活的团队管理器
AutoGen  = 自由探索的对话实验室
```

---

下一章：[03 — 如何选择](03-how-to-choose.md)
