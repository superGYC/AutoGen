# LangGraph + Temporal 生产级集成

## 项目概述

这是一个展示 **LangGraph** 与 **Temporal** 如何协作的完整工作流示例。核心目标是回答一个问题：

> **LangGraph 已经很强了，为什么还需要 Temporal？**

答案是：**它们解决的是不同层面的问题**。LangGraph 负责"AI 智能体内部怎么思考"，Temporal 负责"智能体调用之间的流程怎么保障"。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户/外部系统                              │
│              (提交发票 → 等待通知 → 发送审批决定)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Temporal Workflow (持久化编排层)                │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐  │
│  │ Activity  │  │ Activity  │  │ 等待信号   │  │ Activity      │  │
│  │ analyze_  │→ │ notify_   │→ │ (48h内)   │→ │ process_      │  │
│  │ invoice   │  │ approver  │  │ approve() │  │ payment       │  │
│  └─────┬─────┘  └───────────┘  └───────────┘  └───────────────┘  │
│        │                                                        │
│        │  💀 服务器崩溃？→ 恢复后从最后完成的 Activity 继续       │
│        │  ⏰ LLM 超时？→ Activity 自动重试 (指数退避)               │
│        │  🧍 审批人出差？→ Workflow 暂停等待信号，不占用资源        │
│  ──────┴──────────────────────────────────────────────────────  │
│                        状态持久化 ← 自动保存每一步                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ 内部调用
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph Agent (智能体逻辑层)                  │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐                     │
│  │  extract │ → │ validate │ → │  format  │                     │
│  │  节点    │    │  节点    │    │  节点    │                     │
│  └─────────┘    └──────────┘    └──────────┘                     │
│       │                                                        │
│       │  LangGraph checkpoint: 每个节点执行完自动保存状态          │
│       │  → 内部节点失败可重放，不丢失 LLM 调用上下文               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 两层架构的设计哲学

### 第一层：LangGraph（智能体逻辑层）

**职责**：单个 Agent 内部的推理、工具调用、状态流转

```python
# langgraph_invoice_agent.py
# 只管：怎么从发票文本提取字段、验证规则、输出结构化数据
def extract_invoice(state: AgentState) -> dict:
    # 调用 LLM，解析 JSON，处理异常
    ...

def validate_invoice(state: AgentState) -> dict:
    # 业务规则：金额>10000？信心<0.8？
    ...
```

**LangGraph 能搞定的事**（本层解决）：
- ✅ LLM 调用编排（prompt → LLM → parse → 工具）
- ✅ Agent 内部状态机（图结构、条件分支、循环）
- ✅ 单个任务内的 checkpoint（节点级重放）
- ✅ 结构化输出（Pydantic schema）

**LangGraph 搞不定的事**（需要 Temporal）：
- ❌ Agent 之间的流程编排（"分析完 → 审批 → 付款" 是跨 Agent 的流程）
- ❌ 流程级持久化（服务器崩溃后整个流程从哪里恢复）
- ❌ 人机审批（跨天、跨会话的外部信号等待）
- ❌ 跨步骤的审计追踪（"谁在什么时候做了什么决定"）
- ❌ 外部系统的幂等调用（"付款只能执行一次"）

### 第二层：Temporal（持久化编排层）

**职责**：工作流级别的可靠性、重试、超时、审批、审计

```python
# temporal_workflow.py
# 只管：步骤怎么串起来、失败了怎么办、人怎么参与、怎么恢复
async def run(self, raw_text: str) -> InvoiceResult:
    analysis = await workflow.execute_activity("analyze_invoice", ...)  # Step 1
    if needs_approval:
        await workflow.execute_activity("notify_approver", ...)          # Step 2
        await workflow.wait_condition(lambda: self._approval_received,   # Step 3
                                       timeout=timedelta(hours=48))
    await workflow.execute_activity("process_payment", ...)            # Step 4
```

**Temporal 补上的关键能力**：
- ✅ **Durable Execution**：服务器挂了，恢复后从最后一个完成的 Activity 继续
- ✅ **Human-in-the-loop**：Workflow 可暂停数天等待外部信号，期间零资源占用
- ✅ **重试策略**：每个 Activity 独立配置超时、重试次数、退避间隔
- ✅ **幂等保证**：Activity 至少执行一次 + idempotency key = 副作用不重复
- ✅ **审计回放**：完整执行历史可查询、可重放、可追溯

---

## 代码文件导航

| 文件 | 层级 | 说明 |
|------|------|------|
| `langgraph_invoice_agent.py` | 智能体层 | LangGraph 发票分析 Agent：提取 → 验证 → 格式化 |
| `temporal_workflow.py` | 编排层 | Temporal Workflow 定义：步骤顺序、审批等待、超时处理 |
| `temporal_workflow_types.py` | 共享层 | Workflow 间传递的纯数据类型（dataclass） |
| `activities.py` | 编排层 | Temporal Activity 实现：真正执行业务逻辑的函数 |
| `worker.py` | 编排层 | Temporal Worker：监听任务队列，调度执行 |
| `client.py` | CLI 层 | 提交流程、查询状态、发送审批信号的命令行工具 |
| `requirements.txt` | 依赖 | 所需 Python 包 |

---

## 快速开始

### 前置条件

```bash
# 1. Temporal CLI（开发环境用 dev server）
#    安装: https://docs.temporal.io/cli#install

# 2. Python 依赖
pip install -r requirements.txt

# 3. OpenAI API Key
export OPENAI_API_KEY="sk-..."
```

### 运行流程

需要 **3 个终端窗口**同时运行：

**终端 1 — Temporal Server**
```bash
temporal server start-dev
```

**终端 2 — Worker（等待执行）**
```bash
python worker.py
# 🚀 Temporal Worker 已启动...
```

**终端 3 — 客户端（提交发票 & 审批）**
```bash
# 提交发票（金额 8500，会触发人工审批）
python client.py submit "阿里云服务器续费发票，金额8500元"

# 控制台会打印审批通知，复制 workflow_id 然后：
python client.py approve <workflow_id> --name "张总监"

# 查看最终结果
python client.py result <workflow_id>
```

---

## 典型场景演示

### 场景 1：小额发票自动通过（无需审批）

```bash
# 金额 3000 元，无异常
python client.py submit "购买打印纸，金额3000元，发票号12345"
```

**流程**：
1. Agent 分析 → 金额 ≤ 5000，无异常标记
2. Workflow 判断 `needs_approval = False`
3. 直接执行 `process_payment` Activity
4. 状态：`auto_approved`

### 场景 2：大额发票触发人工审批

```bash
python client.py submit "购买服务器，金额25000元，发票号67890"
```

**流程**：
1. Agent 分析 → 金额 > 5000，`needs_approval = True`
2. 通知审批人（打印到控制台，实际环境可发邮件/飞书）
3. Workflow **暂停**，等待 `approve` 信号（最多 48 小时）
4. 财务总监运行：`python client.py approve <id> --name "张总"`
5. 收到信号，执行 `process_payment`
6. 状态：`approved`

### 场景 3：审批拒绝

```bash
python client.py reject <workflow_id> --name "张总" --notes "发票抬头错误"
```

**流程**：
1. Agent 分析 → 等待审批
2. 收到拒绝信号
3. 执行 `log_rejection`，记录拒绝原因
4. 状态：`rejected`

### 场景 4：审批超时

```bash
# 提交后 48 小时没有任何人审批
```

**流程**：
1. Agent 分析 → 等待审批
2. 48 小时未收到信号
3. `wait_condition` 超时，捕获异常
4. 执行 `escalate_timeout`，通知上级
5. 状态：`timeout`

### 场景 5：服务器崩溃恢复

```bash
# 假设在 "notify_approver" 之后、审批之前，Worker 进程被 kill -9

# 重新启动 Worker
python worker.py

# 神奇之处：Temporal 自动恢复 Workflow，从 "notify_approver" 之后继续
# 审批人之前收到的通知仍然有效，发送 approve 信号后流程继续
```

**关键点**：
- Workflow 状态保存在 Temporal Server，不在 Worker 内存里
- Worker 只是执行器，随时可替换
- 崩溃 = 换个 Worker 继续跑，数据零丢失

---

## 核心概念对照表

| 概念 | LangGraph 中的含义 | Temporal 中的含义 |
|------|-------------------|-------------------|
| **Node** | Agent 内部的一个计算步骤（LLM 调用/工具/逻辑） | — |
| **Activity** | — | Workflow 中一个可重试、可超时、可追踪的外部调用单元 |
| **State** | Agent 执行中的字典数据（prompt 上下文、中间结果） | Workflow 的持久化状态（Activity 结果、信号、变量） |
| **Checkpoint** | 节点执行完后自动保存的快照 | Workflow 历史事件（每完成一个 Activity 自动记录） |
| **Graph** | Agent 的决策拓扑（节点 → 边 → 条件分支） | — |
| **Workflow** | — | 完整的业务流程定义（多个 Activity + 控制流） |
| **Signal** | — | 外部系统向运行中的 Workflow 发送的异步消息（如人工审批） |
| **Retry Policy** | 每个 LangChain 组件可配 | 每个 Activity 独立配置重试次数、退避策略 |
| **Human-in-the-loop** | 需借助外部工具（不原生） | `wait_condition` + `signal` 原生支持，可跨天 |

---

## 生产部署注意事项

### Temporal 部署选项

| 环境 | 方式 | 说明 |
|------|------|------|
| 本地开发 | `temporal server start-dev` | 单机内存模式，重启丢数据 |
| 测试环境 | Docker Compose | 持久化存储，多 Worker |
| 生产环境 | Temporal Cloud / 自托管 | 高可用集群，99.99% SLA |

### LangGraph 单独运行 vs. 嵌入 Temporal

| 模式 | 适用场景 | 注意 |
|------|---------|------|
| **纯 LangGraph** | 简单 Agent，单次调用，秒级完成 | 服务器崩溃后需自行处理恢复 |
| **LangGraph in Temporal Activity** | 复杂流程，需审批，跨天运行，审计要求 | Activity 超时需覆盖 Agent 可能的最长运行时间 |
| **Temporal + 其他 Agent SDK** | 不局限于 LangGraph，可用 Pydantic AI / Google ADK 等 | 架构模式完全相同，替换 Activity 内部实现即可 |

---

## 扩展思路

1. **多模态发票**：LangGraph 节点可以接入 OCR（发票图片 → 文字 → LLM），Temporal 层不变
2. **邮件/飞书通知**：`notify_approver` Activity 接入企业 IM API
3. **真实支付**：`process_payment` Activity 调用企业财务系统 API，用 `workflow_id` 做幂等键
4. **审批链**：多级审批（经理 → 总监 → CFO），Workflow 中串多个 `wait_condition`
5. **批量处理**：Temporal 的 `for` 循环批量提交发票，每个发票独立 Workflow 实例

---

## 参考资源

- **Temporal Docs**: https://docs.temporal.io/
- **LangGraph Docs**: https://langchain-ai.github.io/langgraph/
- **Pydantic AI + Temporal**: https://ai.pydantic.dev/ (Pydantic AI 官方也推荐 Temporal 做 durable execution)
- **Google ADK + Temporal**: https://google.github.io/adk/ (2025 年 Google 官方集成)

---

*最后更新: 2026-05-15*
