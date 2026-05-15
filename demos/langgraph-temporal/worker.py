"""
Temporal Worker — 处理 LangGraph + Temporal 工作流的执行进程

运行方式:
    python worker.py

它会一直运行，等待 client.py 提交的工作流任务。
"""
import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

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
    # 连接 Temporal server（默认本地 dev server）
    client = await Client.connect("localhost:7233", namespace="default")

    # 注册 Worker，绑定 Workflow + Activities
    worker = Worker(
        client,
        task_queue="invoice-approval-queue",
        workflows=[InvoiceApprovalWorkflow],
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
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
