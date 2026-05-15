"""
Temporal Worker —— 工作流执行进程
=================================

Worker 是 Temporal 架构中的"执行器"。它不是 Workflow 状态的持有者，
只是从 Temporal Server 获取任务并执行。

关键设计原则:
  1. Worker 是无状态的 —— 可以随时启动、停止、扩容、替换
  2. Worker 崩溃不丢数据 —— Workflow 状态在 Temporal Server 中持久化
  3. 多个 Worker 可以共享同一个 task_queue 实现负载均衡
  4. 生产环境通常运行多个 Worker（多进程/多机器）

为什么需要单独一个 Worker 进程？
  - Worker 负责注册 Workflow 和 Activity 的"实现"
  - Temporal Server 只保存 Workflow 的"定义"和"状态"
  - 实际代码执行在 Worker 进程中完成
  - 这种分离让 Server 和 Worker 可以独立扩展

运行方式:
    python worker.py

它会一直运行，等待 client.py 提交的工作流任务。
"""
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

# ── 导入 Workflow 和 Activity ─────────────────────────────────
# Worker 必须知道它能执行哪些 Workflow 和 Activity
# 这些在启动时注册到 Worker 实例
from temporal_workflow import InvoiceApprovalWorkflow
from activities import (
    analyze_invoice,
    notify_approver,
    process_payment,
    log_failure,
    log_rejection,
    escalate_timeout,
)


async def main():
    """
    Worker 主函数

    流程:
      1. 连接 Temporal Server（默认本地 dev server: localhost:7233）
      2. 创建 Worker 实例，注册 Workflow + Activity
      3. 开始监听 task_queue，等待任务
      4. 阻塞运行，直到进程被终止

    生产环境:
      - 使用 Temporal Cloud 或自托管集群（非 localhost）
      - 运行多个 Worker 进程（通常 CPU 核心数 × 2）
      - 使用 Docker / Kubernetes 部署
    """
    # 连接 Temporal Server
    # namespace="default" 是默认命名空间，生产环境可按团队/项目隔离
    client = await Client.connect("localhost:7233", namespace="default")

    # 创建 Worker 实例
    # task_queue: 与 client.py 中提交任务时指定的队列名一致
    worker = Worker(
        client,
        task_queue="invoice-approval-queue",
        workflows=[InvoiceApprovalWorkflow],   # 本 Worker 能执行的 Workflow 类型
        activities=[
            analyze_invoice,
            notify_approver,
            process_payment,
            log_failure,
            log_rejection,
            escalate_timeout,
        ],
    )

    print("🚀 Temporal Worker 已启动，监听队列: invoice-approval-queue")
    print("   现在可以运行: python client.py submit")
    print("   按 Ctrl+C 停止")

    # 开始监听任务（阻塞）
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
