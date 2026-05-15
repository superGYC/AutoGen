"""
LangGraph + Temporal 生产级集成 Demo —— 发票审批工作流

架构:
    Temporal Workflow (持久化编排层)
        └── Activity: 运行 LangGraph Agent (智能体逻辑层)
        └── Activity: 等待人工审批 (Human-in-the-loop)
        └── Activity: 执行最终操作

运行前准备:
    1. 启动 Temporal dev server:  temporal server start-dev
    2. 安装依赖:  pip install -r requirements.txt
    3. 设置 OpenAI API Key:  export OPENAI_API_KEY="sk-..."

运行顺序:
    1. 先启动 worker:   python worker.py
    2. 再触发流程:     python client.py submit
    3. 模拟审批:       python client.py approve <workflow_id>

目录:
    requirements.txt
    langgraph_invoice_agent.py   # LangGraph: 发票分析 Agent
    temporal_workflow.py          # Temporal: 审批工作流定义
    activities.py                 # Temporal: Activity 实现
    worker.py                     # Temporal: Worker 进程
    client.py                     # CLI: 提交流程 + 发送审批信号
"""
