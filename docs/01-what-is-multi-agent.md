# 01 — 什么是多智能体系统（Multi-Agent System）

## 🧠 从一个问题开始

你有一个任务：**"帮我调研一下最近三个月 AI Agent 领域的融资情况，写成一份简报"**。

如果交给一个 Agent，它可能需要：
1. 搜索新闻和数据源
2. 筛选有效信息
3. 整理成表格
4. 撰写分析文字
5. 检查事实准确性

一个 Agent 做完全部步骤，容易出错、容易遗漏、容易跑偏。

**多智能体的思路**：把这个大任务拆成几个角色，每个 Agent 只做自己擅长的事，它们之间像真人团队一样协作。

---

## 🏗️ 多智能体的核心概念

### 1. Agent（智能体）

一个 Agent = **LLM + 角色定义 + 工具 + 记忆**

```
┌─────────────────────────────────┐
│           Agent                 │
├─────────────────────────────────┤
│  🎭 Role: "研究员"              │
│  📝 Goal: "找出所有融资事件"     │
│  🧠 LLM: GPT-4 / Claude        │
│  🔧 Tools: [搜索, 浏览器, 计算]  │
│  💾 Memory: 已收集的数据列表     │
└─────────────────────────────────┘
```

### 2. 多智能体协作的三种模式

| 模式 | 比喻 | 特点 |
|------|------|------|
| **序列（Sequential）** | 流水线 | A → B → C，一步一步传下去 |
| **层级（Hierarchical）** | 公司组织架构 | 经理分配任务，下属执行 |
| **网状（Network/Graph）** | 头脑风暴 | 任意 Agent 之间可以对话 |

### 3. 为什么不用一个超级 Agent？

| 问题 | 单 Agent | 多 Agent |
|------|---------|---------|
| 上下文窗口 | 容易爆 | 每个 Agent 只处理自己的部分 |
| 错误传播 | 一处错全崩 | 可以隔离、重试 |
| 专业化 | 万金油，不精 | 每个角色专注 |
| 可解释性 | 黑盒 | 每一步谁做了什么很清楚 |
| 成本 | 长对话贵 | 短对话并行，可能更省 |

---

## ⚔️ 多智能体的核心挑战

### 挑战 1：谁来说话？（Orchestration）

> 群聊里 5 个人同时开口，听谁的？

不同框架解决方式不同：
- **AutoGen**：用 "speaker selection" 算法，看对话上下文决定下一个谁发言
- **CrewAI**：由经理 Agent（或你写的流程）指定下一个执行者
- **LangGraph**：你在图里写死了：节点 A 执行完一定到节点 B

### 挑战 2：记忆怎么共享？（State Management）

```
Agent A 搜索到的数据 → Agent B 写报告时要用 → 怎么传？
```

| 方式 | 说明 |
|------|------|
| 消息传递 | Agent A 把结果发给 Agent B（AutoGen 风格） |
| 共享状态 | 所有 Agent 读写同一块状态（LangGraph 风格） |
| 任务上下文 | 经理把前一步的输出塞给下一步（CrewAI 风格） |

### 挑战 3：出错了怎么办？（Fault Tolerance）

```
Agent A 搜索失败了 → 重试？换人？跳过？通知人类？
```

- **LangGraph**：有 checkpoint，可以从任意节点恢复
- **CrewAI**：任务级隔离，单任务失败不崩全局
- **AutoGen**：主要靠 conversational memory，容易"漂移"

### 挑战 4：成本怎么控制？（Cost & Efficiency）

```
5 个 Agent 聊 20 轮 → 可能烧掉 $2
```

- 限制对话轮数（`max_turns`）
- 用便宜的模型做简单任务，贵的模型做核心判断
- LangGraph 的图结构天然比自由对话省 token

---

## 🧪 一个极简的多智能体例子

```python
# 伪代码：研究 → 写作 → 审稿

researcher = Agent(role="研究员", goal="收集 AI 融资数据")
writer = Agent(role="写手", goal="基于数据写简报")
reviewer = Agent(role="审稿人", goal="检查事实准确性")

# 方式 1：顺序传递（CrewAI 风格）
data = researcher.run("搜索近三月 AI Agent 融资")
draft = writer.run(f"基于以下数据写简报：\n{data}")
final = reviewer.run(f"审稿：\n{draft}")

# 方式 2：群聊讨论（AutoGen 风格）
groupchat = GroupChat(agents=[researcher, writer, reviewer])
manager = GroupChatManager(groupchat=groupchat)
manager.initiate_chat("一起完成这份融资简报")

# 方式 3：状态机（LangGraph 风格）
graph = StateGraph()
graph.add_node("research", researcher)
graph.add_node("write", writer)
graph.add_node("review", reviewer)
graph.add_edge("research", "write")
graph.add_edge("write", "review")
graph.add_conditional_edge("review", lambda s: "approve" if s.ok else "write")
result = graph.invoke({"topic": "AI Agent 融资"})
```

---

## 📖 延伸阅读

- [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation (Microsoft, 2023)](https://arxiv.org/abs/2308.08155)
- [CrewAI: Role-Based Agent Orchestration](https://github.com/crewAIInc/crewAI)
- [LangGraph: Building Stateful Multi-Agent Applications](https://langchain-ai.github.io/langgraph/)

---

下一章：[02 — 三大框架深度对比](02-framework-comparison.md)
