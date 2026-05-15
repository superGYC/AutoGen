"""
Workflow 间共享的数据类型（纯数据，无业务逻辑）
Temporal Workflow 必须能序列化这些类型。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApprovalDecision:
    """审批决定"""
    approved: bool = False
    approver_name: str = ""
    notes: str = ""


@dataclass
class InvoiceResult:
    """发票处理最终结果"""
    workflow_id: str
    status: str              # auto_approved / approved / rejected / timeout / failed
    stage: str               # analysis / approval / payment
    invoice: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    approver: str = ""
    error: str = ""
