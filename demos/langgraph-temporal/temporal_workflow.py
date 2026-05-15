"""
Temporal Workflow 定义
职责: 编排发票审批流程的持久化执行

关键能力:
    - 服务器崩溃后自动恢复
    - 人机审批节点（Human-in-the-loop）
    - 超时与重试策略
    - 完整的审计追踪
"""
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# 注意: workflow 中只能导入 data class / 标量类型，不能 import 业务逻辑模块
# 业务逻辑通过 Activity 调用
with workflow.unsafe.imports_passed_through():
    from temporal_workflow_types import InvoiceResult, ApprovalDecision


# ========== Workflow 信号定义 ==========
@workflow.defn
class InvoiceApprovalWorkflow:
    """
    发票审批工作流

    流程:
        1. Activity: 调用 LangGraph Agent 分析发票
        2. 如果金额 > 5000 或有异常标记 → 等待人工审批（信号）
        3. 审批通过后 → Activity: 执行付款/入账
        4. 审批拒绝 → 流程结束，记录原因
        5. 超时（48小时未审批）→ 自动升级通知
    """

    def __init__(self) -> None:
        self._approval: ApprovalDecision | None = None
        self._approval_received = False

    @workflow.signal
    async def approve(self, decision: ApprovalDecision) -> None:
        """财务审批人发送审批决定"""
        self._approval = decision
        self._approval_received = True

    @workflow.query
    def get_status(self) -> dict:
        """查询当前流程状态"""
        return {
            "workflow_id": workflow.info().workflow_id,
            "run_id": workflow.info().run_id,
            "approval_received": self._approval_received,
            "approval": self._approval.model_dump() if self._approval else None
        }

    @workflow.run
    async def run(self, raw_invoice_text: str) -> InvoiceResult:
        workflow_id = workflow.info().workflow_id

        # ===== Step 1: 调用 LangGraph Agent 分析发票 =====
        analysis = await workflow.execute_activity(
            "analyze_invoice",
            raw_invoice_text,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=30)
            )
        )

        if not analysis["success"]:
            # Agent 分析失败，记录并结束
            await workflow.execute_activity(
                "log_failure",
                {"workflow_id": workflow_id, "stage": "analysis", "error": analysis["error"]},
                start_to_close_timeout=timedelta(minutes=1)
            )
            return InvoiceResult(
                workflow_id=workflow_id,
                status="failed",
                stage="analysis",
                error=analysis["error"]
            )

        # ===== Step 2: 判断是否需要审批 =====
        needs_approval = analysis.get("needs_approval", False)
        flags = analysis.get("flags", [])
        invoice_data = analysis.get("data", {})

        if not needs_approval:
            # 小额且正常，自动通过
            await workflow.execute_activity(
                "process_payment",
                {
                    "workflow_id": workflow_id,
                    "invoice": invoice_data,
                    "auto_approved": True
                },
                start_to_close_timeout=timedelta(minutes=1)
            )
            return InvoiceResult(
                workflow_id=workflow_id,
                status="auto_approved",
                stage="payment",
                invoice=invoice_data,
                flags=flags
            )

        # ===== Step 3: 等待人工审批（Human-in-the-loop） =====
        await workflow.execute_activity(
            "notify_approver",
            {
                "workflow_id": workflow_id,
                "summary": analysis.get("summary", ""),
                "flags": flags,
                "amount": invoice_data.get("amount", 0)
            },
            start_to_close_timeout=timedelta(minutes=1)
        )

        # 等待审批信号，最多 48 小时
        try:
            await workflow.wait_condition(
                lambda: self._approval_received,
                timeout=timedelta(hours=48)
            )
        except Exception:
            # 超时未审批
            await workflow.execute_activity(
                "escalate_timeout",
                {"workflow_id": workflow_id, "amount": invoice_data.get("amount", 0)},
                start_to_close_timeout=timedelta(minutes=1)
            )
            return InvoiceResult(
                workflow_id=workflow_id,
                status="timeout",
                stage="approval_pending",
                invoice=invoice_data,
                flags=flags,
                error="审批超时（48小时）"
            )

        # ===== Step 4: 根据审批决定执行 =====
        if self._approval and self._approval.approved:
            await workflow.execute_activity(
                "process_payment",
                {
                    "workflow_id": workflow_id,
                    "invoice": invoice_data,
                    "auto_approved": False,
                    "approver": self._approval.approver_name,
                    "notes": self._approval.notes
                },
                start_to_close_timeout=timedelta(minutes=1)
            )
            return InvoiceResult(
                workflow_id=workflow_id,
                status="approved",
                stage="payment",
                invoice=invoice_data,
                flags=flags,
                approver=self._approval.approver_name
            )
        else:
            # 审批拒绝
            await workflow.execute_activity(
                "log_rejection",
                {
                    "workflow_id": workflow_id,
                    "invoice": invoice_data,
                    "reason": self._approval.notes if self._approval else "未提供原因"
                },
                start_to_close_timeout=timedelta(minutes=1)
            )
            return InvoiceResult(
                workflow_id=workflow_id,
                status="rejected",
                stage="approval",
                invoice=invoice_data,
                flags=flags,
                error=self._approval.notes if self._approval else "审批拒绝"
            )
