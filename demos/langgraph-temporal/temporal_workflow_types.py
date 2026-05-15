"""
Temporal Workflow 共享数据类型 —— 纯数据，零业务逻辑
=====================================================

本文件只定义 dataclass，供 Workflow 和 Activity 之间传递数据。

关键约束:
  - 必须是可序列化的（Temporal 用 protobuf 序列化 Workflow 状态）
  - 不能包含任何方法（纯数据容器）
  - 不能 import 业务模块（避免循环依赖和副作用）

为什么单独一个文件？
  - Temporal Workflow 和 Activity 都需要这些类型
  - 独立文件避免循环 import（Workflow 不能 import Activity，Activity 可以 import Workflow types）
  - 清晰的边界：类型定义 ≠ 业务逻辑
"""
from dataclasses import dataclass, field
from typing import Any


# =============================================================================
# ApprovalDecision —— 审批人发送的决定
# =============================================================================
@dataclass
class ApprovalDecision:
    """
    审批决定

    由外部审批人通过 client.py 发送信号到 Workflow:
        client.handle.signal(InvoiceApprovalWorkflow.approve, decision)

    字段:
        approved:      bool —— True=通过, False=拒绝
        approver_name: str  —— 审批人姓名（审计用）
        notes:         str  —— 备注（拒绝时填写原因）

    序列化:
        Temporal 自动将 dataclass 序列化为 JSON
        不需要手动写 serializer
    """
    approved: bool = False
    approver_name: str = ""
    notes: str = ""


# =============================================================================
# InvoiceResult —— 发票处理最终结果
# =============================================================================
@dataclass
class InvoiceResult:
    """
    发票审批 Workflow 的最终输出

    Workflow 的 run() 方法返回此对象，client.py 通过 handle.result() 获取

    字段:
        workflow_id: str  —— 唯一标识（用于追踪和审计）
        status:      str  —— 最终状态:
            - "auto_approved": 小额自动通过
            - "approved":      人工审批通过
            - "rejected":      人工审批拒绝
            - "timeout":       审批超时（48小时未响应）
            - "failed":        分析阶段失败（LLM/API 异常）
        stage:       str  —— 结束阶段: analysis / approval / payment
        invoice:     dict  —— 结构化发票数据（成功时存在）
        flags:       list  —— 异常标记（供审计参考）
        approver:    str  —— 审批人姓名（人工审批时存在）
        error:       str  —— 错误信息（失败/拒绝/超时时存在）

    为什么用 dataclass 不用 dict？
      - 类型安全：IDE 自动补全、类型检查
      - 文档自描述：字段含义在类型定义中一目了然
      - Temporal 原生支持 dataclass 序列化
    """
    workflow_id: str
    status: str              # auto_approved / approved / rejected / timeout / failed
    stage: str               # analysis / approval / payment
    invoice: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    approver: str = ""
    error: str = ""
