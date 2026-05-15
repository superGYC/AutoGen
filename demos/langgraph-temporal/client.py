"""
Temporal Client —— 提交工作流 + 发送审批信号
===========================================

本文件是"外部系统"与 Temporal Workflow 交互的入口。

使用场景:
  1. 业务系统（如 ERP / 飞书 / Web 前端）调用 client.py 提交流程
  2. 审批人（财务总监）通过 CLI 发送 approve / reject 信号
  3. 运维人员查询流程状态

设计模式:
  - 每个操作都是独立的 CLI 命令，方便脚本化
  - 实际生产环境可替换为 REST API / WebSocket / 消息队列消费者
  - Client 是轻量级的：只负责"启动"和"发信号"，不参与执行

为什么 Client 和 Worker 分离？
  - Client 可以运行在任何机器上（甚至用户的笔记本电脑）
  - Worker 必须运行在有业务代码的服务器上
  - 这种分离让"提交任务"和"执行任务"解耦

用法:
    1. 提交发票:     python client.py submit "阿里云服务器续费发票，金额8500元"
    2. 查看状态:     python client.py status <workflow_id>
    3. 审批通过:     python client.py approve <workflow_id> --name "张财务"
    4. 审批拒绝:     python client.py reject <workflow_id> --name "张财务" --notes "金额有误"
    5. 获取结果:     python client.py result <workflow_id>
"""
import asyncio
import sys
import argparse
import hashlib

from temporalio.client import Client

# ── 安全导入 ──────────────────────────────────────────────────
# Client 操作（start_workflow / signal / query）不涉及执行逻辑
# 只需要 Workflow 定义和类型定义来确保 API 正确性
with __import__('temporalio').workflow.unsafe.imports_passed_through():
    from temporal_workflow import InvoiceApprovalWorkflow
    from temporal_workflow_types import ApprovalDecision


# =============================================================================
# 工具函数：获取 Temporal Client 连接
# =============================================================================
async def get_client() -> Client:
    """
    创建并返回 Temporal Client 连接

    生产环境:
      - 使用 mTLS 证书认证（替换 namespace 和 tls 配置）
      - 连接 Temporal Cloud: "my-namespace.tmprl.cloud:7233"
    """
    return await Client.connect("localhost:7233", namespace="default")


# =============================================================================
# 命令: submit —— 提交发票审批流程
# =============================================================================
async def submit_invoice(raw_text: str) -> None:
    """
    提交发票审批流程

    流程:
      1. 生成 workflow_id（基于发票文本的 MD5 hash）
         → 保证同一发票多次提交得到相同 workflow_id（天然幂等）
      2. 调用 Temporal Server 启动 Workflow
      3. Server 将任务放入 task_queue，等待 Worker 消费
      4. Worker 执行 Workflow，第一个 Activity 是 analyze_invoice

    参数:
        raw_text: 用户输入的发票描述文本（如"阿里云服务器续费发票，金额8500元"）

    返回:
        控制台打印 workflow_id 和后续操作命令
    """
    client = await get_client()

    # 用发票文本 MD5 hash 做 workflow_id
    # 好处:
    #   - 同一发票多次提交不会重复创建 Workflow（幂等）
    #   - 方便从文本反查 workflow_id
    # 注意:
    #   - 生产环境建议使用业务系统的唯一订单号
    workflow_id = f"invoice-{hashlib.md5(raw_text.encode()).hexdigest()[:12]}"

    # 启动 Workflow
    handle = await client.start_workflow(
        InvoiceApprovalWorkflow.run,        # Workflow 的入口方法
        raw_text,                           # 传给 run() 的参数
        id=workflow_id,                     # 自定义 workflow_id（幂等键）
        task_queue="invoice-approval-queue" # 任务队列名（Worker 监听）
    )

    print(f"✅ 已提交发票审批流程")
    print(f"   Workflow ID: {handle.id}")
    print(f"   Run ID:      {handle.result_run_id}")
    print(f"\n   查看状态:  python client.py status {handle.id}")
    print(f"   审批通过:  python client.py approve {handle.id} --name '你的名字'")
    print(f"   审批拒绝:  python client.py reject {handle.id} --name '你的名字' --notes '原因'")
    print(f"   最终结果:  python client.py result {handle.id}")


# =============================================================================
# 命令: status —— 查询工作流状态
# =============================================================================
async def check_status(workflow_id: str) -> None:
    """
    查询工作流当前状态（同步查询，不等待 Workflow 完成）

    原理:
      - Query 是只读操作，不修改 Workflow 状态
      - Query 由 Worker 本地处理，不经过 Server 重试
      - Query 响应延迟低（毫秒级）

    适用场景:
      - 审批人想查看"这个发票现在处理到哪一步了"
      - Web 仪表盘实时展示流程状态
    """
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    try:
        status = await handle.query(InvoiceApprovalWorkflow.get_status)
        print(f"📊 Workflow {workflow_id} 状态:")
        for k, v in status.items():
            print(f"   {k}: {v}")
    except Exception as e:
        print(f"❌ 查询失败: {e}")


# =============================================================================
# 命令: approve / reject —— 发送审批信号
# =============================================================================
async def send_approval(
    workflow_id: str,
    approved: bool,
    name: str = "",
    notes: str = ""
) -> None:
    """
    向运行中的 Workflow 发送审批信号

    原理:
      - Signal 是异步消息：发送方不等待 Workflow 处理完成
      - Workflow 通过 wait_condition 监听信号到达
      - 信号可以发送到任何正在运行的 Workflow 实例
      - 多个信号会覆盖，最后一条有效

    参数:
        workflow_id: 目标 Workflow ID
        approved:    True=通过, False=拒绝
        name:        审批人姓名（审计用）
        notes:       备注（拒绝时填写原因）

    使用场景:
      - 财务审批人在 Web 界面点击"通过"按钮
      - 飞书/钉钉机器人接收审批指令后转发
      - 邮件回复中的审批决定被解析后发送
    """
    client = await get_client()
    handle = client.get_workflow_handle(workflow_id)

    decision = ApprovalDecision(approved=approved, approver_name=name, notes=notes)

    try:
        await handle.signal(InvoiceApprovalWorkflow.approve, decision)
        action = "通过" if approved else "拒绝"
        print(f"✅ 已发送审批决定: {action} (Workflow: {workflow_id})")
    except Exception as e:
        print(f"❌ 发送失败: {e}")


# =============================================================================
# 命令: result —— 获取最终结果
# =============================================================================
async def get_result(workflow_id: str) -> None:
    """
    等待 Workflow 完成并获取最终结果

    原理:
      - handle.result() 是阻塞调用，会一直等到 Workflow 结束
      - 如果 Workflow 还在运行（等待审批），此命令会挂起
      - 适合脚本自动化场景（CI/CD 中等待流程完成）

    对比 status:
      - status:  查询当前状态（非阻塞）
      - result:  等待最终结果（阻塞）
    """
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


# =============================================================================
# CLI 入口 —— argparse 解析命令行参数
# =============================================================================
def main() -> None:
    """
    CLI 主入口

    支持的子命令:
      submit  — 提交发票审批流程
      status  — 查询流程状态
      approve — 审批通过
      reject  — 审批拒绝
      result  — 获取最终结果
    """
    parser = argparse.ArgumentParser(
        description="发票审批 Temporal Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  提交发票:   python client.py submit "阿里云服务器续费发票，金额8500元"
  查看状态:   python client.py status invoice-a1b2c3d4e5f6
  审批通过:   python client.py approve invoice-a1b2c3d4e5f6 --name "张总监"
  审批拒绝:   python client.py reject invoice-a1b2c3d4e5f6 --name "张总监" --notes "金额有误"
  获取结果:   python client.py result invoice-a1b2c3d4e5f6
        """
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # ── submit ──
    p_submit = sub.add_parser("submit", help="提交发票审批流程")
    p_submit.add_argument("text", help="发票描述文本（如\"购买服务器，金额5000元\"）")

    # ── status ──
    p_status = sub.add_parser("status", help="查询流程状态（非阻塞）")
    p_status.add_argument("workflow_id", help="Workflow ID")

    # ── approve ──
    p_approve = sub.add_parser("approve", help="审批通过")
    p_approve.add_argument("workflow_id", help="Workflow ID")
    p_approve.add_argument("--name", default="审批人", help="审批人姓名")

    # ── reject ──
    p_reject = sub.add_parser("reject", help="审批拒绝")
    p_reject.add_argument("workflow_id", help="Workflow ID")
    p_reject.add_argument("--name", default="审批人", help="审批人姓名")
    p_reject.add_argument("--notes", default="拒绝", help="拒绝原因")

    # ── result ──
    p_result = sub.add_parser("result", help="获取最终结果（阻塞等待）")
    p_result.add_argument("workflow_id", help="Workflow ID")

    args = parser.parse_args()

    # 路由到对应的 async 函数
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
        sys.exit(1)


if __name__ == "__main__":
    main()
