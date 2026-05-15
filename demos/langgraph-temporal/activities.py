"""
Temporal Activities — 实际执行业务逻辑

每个 Activity 都可能失败、超时或重试。
Temporal 保证 Activity 至少执行一次，通过 idempotency key 防止重复副作用。
"""
import os
from temporalio import activity

with activity.imports_passed_through():
    from langgraph_invoice_agent import run_invoice_agent


# ========== Activity 1: 调用 LangGraph Agent ==========
@activity.defn
async def analyze_invoice(raw_text: str) -> dict:
    """Activity: 运行 LangGraph 发票分析 Agent

    关键点:
    - 如果 LLM API 超时，Temporal 会自动重试（由 Workflow 的 retry_policy 控制）
    - 如果服务器挂了，Temporal 会在恢复后重新调度这个 Activity
    - LangGraph 自己的 checkpoint 确保 Agent 内部状态不丢
    """
    activity.logger.info(f"[Activity] 开始分析发票: {raw_text[:50]}...")
    result = run_invoice_agent(raw_text)
    activity.logger.info(f"[Activity] 分析结果: success={result['success']}, needs_approval={result.get('needs_approval')}")
    return result


# ========== Activity 2: 通知审批人 ==========
@activity.defn
async def notify_approver(payload: dict) -> None:
    """Activity: 通知财务审批人有待审批的发票"""
    workflow_id = payload["workflow_id"]
    amount = payload["amount"]
    flags = payload["flags"]
    summary = payload["summary"]

    # 实际生产: 这里发邮件 / 发飞书 / 发短信
    # 本 Demo 打印到控制台
    print("\n" + "=" * 60)
    print("🚨 待审批通知")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   金额: ¥{amount:.2f}")
    print(f"   摘要: {summary}")
    if flags:
        print(f"   ⚠️ 异常标记: {', '.join(flags)}")
    print(f"\n   审批命令: python client.py approve {workflow_id}")
    print("=" * 60 + "\n")

    activity.logger.info(f"[Activity] 已通知审批人: {workflow_id}")


# ========== Activity 3: 执行付款 ==========
@activity.defn
async def process_payment(payload: dict) -> None:
    """Activity: 执行付款或入账操作

    这是有副作用的操作，必须幂等！
    用 workflow_id 作为幂等键，防止重复付款。
    """
    workflow_id = payload["workflow_id"]
    invoice = payload["invoice"]
    auto_approved = payload.get("auto_approved", False)
    approver = payload.get("approver", "系统")

    print("\n" + "=" * 60)
    print("💰 执行付款")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   供应商: {invoice.get('vendor_name')}")
    print(f"   金额: ¥{invoice.get('amount', 0):.2f}")
    print(f"   审批方式: {'自动' if auto_approved else f'人工 ({approver})'}")
    print("=" * 60 + "\n")

    activity.logger.info(f"[Activity] 付款完成: {workflow_id}")


# ========== Activity 4: 记录失败 ==========
@activity.defn
async def log_failure(payload: dict) -> None:
    """Activity: 记录分析失败"""
    workflow_id = payload["workflow_id"]
    stage = payload["stage"]
    error = payload["error"]

    print(f"\n❌ Workflow {workflow_id} 在 [{stage}] 阶段失败: {error}\n")
    activity.logger.error(f"[Activity] 失败记录: {workflow_id} / {stage}: {error}")


# ========== Activity 5: 记录拒绝 ==========
@activity.defn
async def log_rejection(payload: dict) -> None:
    """Activity: 记录审批拒绝"""
    workflow_id = payload["workflow_id"]
    reason = payload["reason"]

    print(f"\n🚫 Workflow {workflow_id} 审批被拒绝: {reason}\n")
    activity.logger.info(f"[Activity] 审批拒绝: {workflow_id}: {reason}")


# ========== Activity 6: 超时升级 ==========
@activity.defn
async def escalate_timeout(payload: dict) -> None:
    """Activity: 审批超时，升级通知"""
    workflow_id = payload["workflow_id"]
    amount = payload["amount"]

    print("\n" + "=" * 60)
    print("⏰ 审批超时升级")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   金额: ¥{amount:.2f}")
    print(f"   已超过 48 小时未审批，已通知上级")
    print("=" * 60 + "\n")

    activity.logger.warning(f"[Activity] 审批超时: {workflow_id}")
