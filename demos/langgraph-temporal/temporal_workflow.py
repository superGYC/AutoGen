"""
Temporal Workflow 定义 —— 持久化编排层
======================================

本文件定义了"发票审批"这个业务流程的完整执行计划。

关键设计原则:
  1. Workflow 是"声明式"的 —— 只描述"先做什么、后做什么、失败了怎么办"
     不直接执行业务逻辑，业务逻辑委托给 Activity
  2. Workflow 状态自动持久化 —— 每完成一个 Activity，Temporal Server 自动保存进度
     这意味着 Worker 进程可以随时重启、扩容、替换，不丢失流程状态
  3. 信号（Signal）机制 —— 外部系统（如财务审批人）可向运行中的 Workflow
     发送异步消息，Workflow 可以暂停等待信号数天，期间零资源占用

为什么 Workflow 代码里不能 import 业务模块？
  - Temporal 要求 Workflow 代码是"确定性的"（deterministic）
  - 业务逻辑可能有副作用（调用 API、读写数据库、随机数、时间），
    这些必须放在 Activity 中执行
  - Workflow 里只能做：变量赋值、条件判断、循环、Activity 编排、信号处理
"""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# ── 安全导入 ──────────────────────────────────────────────────
# workflow.unsafe.imports_passed_through() 标记下的导入是"安全的"
# 因为这些是纯数据类（dataclass），没有副作用
with workflow.unsafe.imports_passed_through():
    from temporal_workflow_types import InvoiceResult, ApprovalDecision


# =============================================================================
# Workflow 定义
# =============================================================================
@workflow.defn
class InvoiceApprovalWorkflow:
    """
    发票审批工作流

    完整流程:
        1. [Activity] analyze_invoice      → 调用 LangGraph Agent 分析发票
        2. [判断] 是否需要人工审批？
           ├── 否 → [Activity] process_payment（自动通过）
           └── 是 → [Activity] notify_approver（通知审批人）
                   → [等待信号] approve()（最多 48 小时）
                   ├── 超时 → [Activity] escalate_timeout（升级通知）
                   ├── 拒绝 → [Activity] log_rejection（记录原因）
                   └── 通过 → [Activity] process_payment（执行付款）

    异常处理:
        - Activity 失败 → 自动重试（指数退避，最多 3 次）
        - Activity 超时 → 视为失败，触发重试
        - Workflow 崩溃 → 新 Worker 启动后自动从最后一个完成的活动继续
        - 审批超时（48h）→ 捕获超时异常，走升级分支

    幂等性保证:
        - Temporal 保证 Activity "至少执行一次"
        - 副作用操作（如付款）使用 workflow_id 作为幂等键
        - 外部系统需实现："相同的 workflow_id 不重复执行"
    """

    def __init__(self) -> None:
        """
        Workflow 构造函数 —— 每次 Workflow 实例创建时调用

        这里初始化的变量是"Workflow 级状态"，跨 Activity 持久化:
          - _approval: 审批人发送的决定
          - _approval_received: 是否已收到信号（用于 wait_condition）
        """
        self._approval: ApprovalDecision | None = None
        self._approval_received = False

    # ── 信号处理 ──────────────────────────────────────────────
    # 外部系统通过 handle.signal(InvoiceApprovalWorkflow.approve, decision)
    # 向运行中的 Workflow 发送审批决定
    # 信号是异步的：发送方不等待 Workflow 处理完成
    # ────────────────────────────────────────────────────────────
    @workflow.signal
    async def approve(self, decision: ApprovalDecision) -> None:
        """
        财务审批人发送审批决定

        参数:
            decision: ApprovalDecision —— 包含 approved(bool)、approver_name、notes

        注意:
            - 信号处理函数必须是 async
            - 多次发送信号会覆盖之前的决定（最后一条有效）
        """
        self._approval = decision
        self._approval_received = True

    # ── 查询处理 ──────────────────────────────────────────────
    # 外部系统通过 handle.query(InvoiceApprovalWorkflow.get_status)
    # 同步查询 Workflow 的当前状态（只读，不修改 Workflow）
    # ────────────────────────────────────────────────────────────
    @workflow.query
    def get_status(self) -> dict:
        """
        查询当前流程状态

        返回:
            {
                "workflow_id": str,
                "run_id": str,
                "approval_received": bool,
                "approval": dict | None
            }

        适用场景:
            - 审批人想查看"这个发票现在处理到哪一步了"
            - 仪表盘实时展示流程状态
        """
        return {
            "workflow_id": workflow.info().workflow_id,
            "run_id": workflow.info().run_id,
            "approval_received": self._approval_received,
            "approval": self._approval.model_dump() if self._approval else None
        }

    # ── 主执行逻辑 ──────────────────────────────────────────────
    # run() 是 Workflow 的入口，由 Temporal 调度执行
    # 整个 run() 函数的执行历史会被自动记录到 Temporal Server
    # ────────────────────────────────────────────────────────────
    @workflow.run
    async def run(self, raw_invoice_text: str) -> InvoiceResult:
        """
        工作流主入口

        参数:
            raw_invoice_text: str —— 用户输入的原始发票描述文本

        返回:
            InvoiceResult —— 包含最终状态（通过/拒绝/超时/失败）、发票数据等
        """
        workflow_id = workflow.info().workflow_id

        # ═══════════════════════════════════════════════════════════
        # Step 1: 调用 LangGraph Agent 分析发票
        # ═══════════════════════════════════════════════════════════
        # execute_activity("activity_name", args, ...)
        # 为什么把 LangGraph 包在 Activity 里？
        #   - LangGraph 调用 LLM 可能有网络超时，需要重试策略
        #   - LLM API 成本较高，Activity 失败重试不计费（Workflow 内部逻辑才计费）
        #   - LangGraph 内部状态通过 checkpoint 恢复，Activity 级别通过 Temporal 恢复
        # ═══════════════════════════════════════════════════════════
        analysis = await workflow.execute_activity(
            "analyze_invoice",                    # Activity 名称（在 worker.py 中注册）
            raw_invoice_text,                     # 传给 Activity 的参数
            start_to_close_timeout=timedelta(minutes=2),  # Activity 最多跑 2 分钟
            retry_policy=RetryPolicy(
                maximum_attempts=3,                # 最多重试 3 次
                initial_interval=timedelta(seconds=2),     # 首次失败后等 2 秒
                maximum_interval=timedelta(seconds=30)     # 最长间隔 30 秒（指数退避上限）
            )
        )

        # ═══════════════════════════════════════════════════════════
        # 错误分支: Agent 分析失败
        # ═══════════════════════════════════════════════════════════
        if not analysis["success"]:
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

        # ═══════════════════════════════════════════════════════════
        # Step 2: 判断是否需要人工审批
        # ═══════════════════════════════════════════════════════════
        # 这里的业务逻辑简单明了：
        #   - 小额（≤5000）+ 无异常 → 自动通过
        #   - 大额（>5000）或有异常标记 → 必须人工审批
        # ═══════════════════════════════════════════════════════════
        needs_approval = analysis.get("needs_approval", False)
        flags = analysis.get("flags", [])
        invoice_data = analysis.get("data", {})

        if not needs_approval:
            # ── 自动通过分支 ──
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

        # ═══════════════════════════════════════════════════════════
        # Step 3: 等待人工审批（Human-in-the-loop）
        # ═══════════════════════════════════════════════════════════
        # 这是 Temporal 的核心能力之一：
        #   - Workflow 可以"暂停"在 wait_condition，等待外部信号
        #   - 暂停期间不占用 CPU、内存、线程（零成本）
        #   - 信号到达后，Temporal 自动恢复 Workflow 执行
        #   - 即使暂停 3 天，服务器重启后仍能正确恢复
        #
        # 对比其他方案:
        #   - 轮询数据库: 浪费资源，延迟高
        #   - 消息队列: 需自己处理幂等、重试、超时
        #   - Temporal: 原生支持，自动持久化
        # ═══════════════════════════════════════════════════════════

        # 先通知审批人（发邮件 / 飞书 / 短信）
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

        # 等待 approve 信号，最多 48 小时
        try:
            await workflow.wait_condition(
                lambda: self._approval_received,   # 条件：收到审批信号
                timeout=timedelta(hours=48)      # 超时时间
            )
        except Exception:
            # ── 超时分支 ──
            # 48 小时内没有人审批，走升级流程
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

        # ═══════════════════════════════════════════════════════════
        # Step 4: 根据审批决定执行最终操作
        # ═══════════════════════════════════════════════════════════
        if self._approval and self._approval.approved:
            # ── 审批通过 ──
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
            # ── 审批拒绝 ──
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
