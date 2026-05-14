# 🤖 AutoGen · CrewAI · LangGraph — 多智能体框架完全指南

> **一句话总结**：LangGraph 是流程控制的极致，CrewAI 是团队分工的直觉，AutoGen 是自由对话的乐园。选谁，取决于你要的是确定性还是灵活性。

---

## 📑 目录

| 章节 | 内容 |
|------|------|
| [01 什么是多智能体系统](docs/01-what-is-multi-agent.md) | 概念、为什么需要多智能体、核心挑战 |
| [02 三大框架深度对比](docs/02-framework-comparison.md) | 架构哲学、编排模型、状态管理、生产指标对比 |
| [03 如何选择](docs/03-how-to-choose.md) | 决策矩阵、场景匹配、团队能力考量 |
| [04 常见设计模式](docs/04-common-patterns.md) | 分层、路由、反射、人机协作等模式 |
| `demos/autogen/` | AutoGen 实战 Demo（3 个） |
| `demos/crewai/` | CrewAI 实战 Demo（3 个） |
| `demos/langgraph/` | LangGraph 实战 Demo（3 个） |

---

## 🚀 快速开始

### 你想先看哪个？

```bash
# 想看对话驱动的 Agent 协作 → AutoGen
cd demos/autogen && pip install -r requirements.txt

# 想看角色分工的团队 → CrewAI
cd demos/crewai && pip install -r requirements.txt

# 想看精确控制的流程图 → LangGraph
cd demos/langgraph && pip install -r requirements.txt
```

---

## 📊 三秒速览

| | **AutoGen** | **CrewAI** | **LangGraph** |
|---|---|---|---|
| **出品方** | Microsoft Research | CrewAI Inc. | LangChain Inc. |
| **核心理念** | 对话驱动 | 角色分工 | 图状态机 |
| **编排方式** | 自由对话/群聊 | 顺序/层级/流程 | DAG / 循环图 |
| **上手难度** | ⭐⭐⭐ 中等 | ⭐⭐ 简单 | ⭐⭐⭐⭐ 较难 |
| **状态持久** | ❌ 手动 | ⚠️ 有限 | ✅ 原生 |
| **生产可靠** | ⚠️ 研究导向 | ✅ 快速上线 | ✅ 企业级 |
| **错误恢复** | 68% | 72% | **96%** |
| **单次成本** | ~$0.45 | ~$0.15 | ~$**0.08** |
| **最佳场景** | 代码生成、辩论研究 | 内容管道、SEO、销售 | 客服、合规、复杂流程 |

---

## 🎯 一句话选框架

| 你的需求 | 选它 |
|---------|------|
| "我要搭一个研究员+写手+编辑的内容团队" | **CrewAI** |
| "我要一个能写代码、能调试、能自己修 bug 的助手" | **AutoGen** |
| "我要一个每一步都可追溯、可回滚的审批流程" | **LangGraph** |
| "我们团队没专门做 AI 的人，想快速出原型" | **CrewAI** |
| "我们在金融/医疗行业，需要审计和合规" | **LangGraph** |
| "我要做学术实验，需要多轮对话迭代" | **AutoGen** |

---

## 📚 参考索引

- [AutoGen 官方文档](https://microsoft.github.io/autogen/)
- [CrewAI 官方文档](https://docs.crewai.com/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [LangSmith 调试平台](https://smith.langchain.com/)
- [AgentOps 观测平台](https://agentops.ai/)

---

*本教程持续更新。如有问题或建议，欢迎提 Issue。*
