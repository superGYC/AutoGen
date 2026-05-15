"""
Temporal Client — 提交工作流 + 发送审批信号

用法:
    1. 提交发票:     python client.py submit "阿里云服务器续费发票，金额8500元，发票号INV20260515001"
    2. 查看状态:     python client.py status <workflow_id>
    3. 审批通过:     python client.py approve <workflow_id> --name "张财务"
    4. 审批拒绝:     python client.py reject <workflow_id> --name "张财务" --notes "金额有误"
"""
import asyncio
import sys
import argparse

from temporalio.client import Client
from temporal_workflow_types import ApprovalDecision


async def get_client():
    return await Client.connect("localhost:7233", namespace="default")


async def submit_invoice(raw_text: str):
    """提交发票审批流程"""
    client = await get_client()

    # 用发票文本 hash 做 workflow_id，方便幂等和查询
    import hashlib
    workflow_id = f"invoice-{hashlib.md5(raw_text.encode()).hexdigest()[:12]}"

    handle = await client.start_workflow(
        InvoiceApprovalWorkflow.run,
        raw_text,
        id=workflow_id,
        task_queue="invoice-approval-queue",
    )

    print(f"✅ 已提交发票审批流程")
    print(f"   Workflow ID: {handle.id}")
    print(f"   Run ID:      {handle.result_run_id}")
    print(f"\n   查看状态:  python client.py status {handle.id}")
    print(f"   审批通过:  python client.py approve {handle.id} --name '你的名字'")
    print(f"   审批拒绝:  python client.py reject {handle.id} --name '你的名字' --notes '原因'")


async def check_status(workflow_id: str):
    """查询工作流状态"""
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    try:
        status = await handle.query(InvoiceApprovalWorkflow.get_status)
        print(f"📊 Workflow {workflow_id} 状态:")
        for k, v in status.items():
            print(f"   {k}: {v}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


async def send_approval(workflow_id: str, approved: bool, name: str = "", notes: str = ""):
    """发送审批信号"""
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    decision = ApprovalDecision(approved=approved, approver_name=name, notes=notes)

    try:
        await handle.signal(InvoiceApprovalWorkflow.approve, decision)
        action = "通过" if approved else "拒绝"
        print(f"✅ 已发送审批决定: {action} (Workflow: {workflow_id})")
    except Exception as e:
        print(f"❌ 发送失败: {e}")


async def get_result(workflow_id: str):
    """等待并获取工作流最终结果"""
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    try:
        result = await handle.result()
        print(f"📋 Workflow {workflow_id} 最终结果:")
        print(f"   状态: {result.status}")
        print(f"   阶段: {result.stage}")
        if result.invoice:
            print(f"   发票: {result.invoice}")
        if result.approver:
            print(f"   审批人: {result.approver}")
        if result.error:
            print(f"   错误: {result.error}")
    except Exception as e:
        print(f"❌ 获取结果失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="发票审批 Temporal Client")
    sub = parser.add_subparsers(dest="command")

    # submit
    p_submit = sub.add_parser("submit", help="提交发票")
    p_submit.add_argument("text", help="发票描述文本")

    # status
    p_status = sub.add_parser("status", help="查询状态")
    p_status.add_argument("workflow_id", help="Workflow ID")

    # approve
    p_approve = sub.add_parser("approve", help="审批通过")
    p_approve.add_argument("workflow_id", help="Workflow ID")
    p_approve.add_argument("--name", default="审批人", help="审批人姓名")

    # reject
    p_reject = sub.add_parser("reject", help="审批拒绝")
    p_reject.add_argument("workflow_id", help="Workflow ID")
    p_reject.add_argument("--name", default="审批人", help="审批人姓名")
    p_reject.add_argument("--notes", default="拒绝", help="拒绝原因")

    # result
    p_result = sub.add_parser("result", help="获取最终结果")
    p_result.add_argument("workflow_id", help="Workflow ID")

    args = parser.parse_args()

    if args.command == "submit":
        asyncio.run(submit_invoice(args.text))
    elif args.command == "status":
        asyncio.run(check_status(args.workflow_id))
    elif args.command == "approve":
        asyncio.run(send_approval(args.workflow_id, True, args.name))
    elif args.command == "reject":
        asyncio.run(send_approval(args.workflow_id, False, args.name, args.notes))
    elif args.command == "result":
        asyncio.run(get_result(args.workflow_id))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
