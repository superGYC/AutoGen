"""
LangGraph 发票分析 Agent —— 智能体逻辑层
=======================================

本文件只负责"AI 智能体内部怎么思考"，包含三个核心节点：
  1. extract   — 从原始文本提取结构化字段（LLM 调用）
  2. validate  — 业务规则验证（金额阈值、信心分）
  3. format    — 输出标准化结果

设计原则:
  - 本层不关心"流程怎么持久化"、"审批人怎么通知"、"服务器挂了怎么办"
  - 这些问题由外层的 Temporal Workflow 解决
  - LangGraph 的 checkpoint 保证：单个 Agent 内部节点失败后，可从断点重放

为什么用 LangGraph 而不是裸调 LLM:
  - 图结构让每个步骤独立、可替换、可观测
  - checkpoint 机制让调试变得可逆（time-travel debugging）
  - 结构化输出（Pydantic）强制 LLM 返回合规数据，不是自由文本
"""
import json
from typing import TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# =============================================================================
# 1. 结构化输出 Schema
# =============================================================================
# 为什么要用 Pydantic BaseModel？
#   1. LLM 输出必须是可预测的结构，不能是自由文本
#   2. 运行时自动校验：如果 LLM 漏了字段或类型错误，立即报错
#   3. 下游系统（Temporal Activity）可以直接 .model_dump() 拿到纯 dict
# ------------------------------------------------------------------------------
class InvoiceData(BaseModel):
    """发票结构化数据 —— LLM 必须按此格式返回"""
    vendor_name: str = Field(description="供应商名称")
    invoice_number: str = Field(description="发票号码")
    amount: float = Field(description="金额（元）")
    category: str = Field(description="费用类别: office/tech/travel/marketing/other")
    confidence: float = Field(description="AI 对提取结果的信心分数 0-1")
    flags: list[str] = Field(default_factory=list, description="异常标记,如 ['金额过高','重复发票']")


# =============================================================================
# 2. LangGraph State —— 贯穿整个 Graph 的"记忆"
# =============================================================================
# TypedDict 定义了 Graph 中流动的数据形状
# Annotated[int, add] 表示 retry_count 用"加法"合并（LangGraph 的 reducer 语义）
# ------------------------------------------------------------------------------
class AgentState(TypedDict):
    raw_text: str                    # 用户输入的原始发票文本（只读输入）
    invoice: InvoiceData | None      # 提取结果（中间产物 → 最终输出）
    error: str | None                # 错误信息（节点失败时填充）
    retry_count: Annotated[int, add] # 重试计数（LangGraph 内部用）


# =============================================================================
# 3. 节点实现 —— 每个节点是纯函数: AgentState -> dict(更新字段)
# =============================================================================
# 关键设计：节点不修改全局状态，只返回"需要更新的字段"
# LangGraph 自动将返回值合并到全局 State
# ------------------------------------------------------------------------------

# LLM 实例：temperature=0 保证可重复性（财务场景需要稳定输出）
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def extract_invoice(state: AgentState) -> dict:
    """
    节点 1: 从原始文本中提取发票字段

    实现细节:
      - 用 zero-shot prompt 要求 LLM 返回 JSON
      - 解析 JSON 后用 Pydantic 校验结构
      - 任何异常（JSON 解析失败 / 字段缺失 / 类型错误）都会捕获

    为什么不用 Function Calling / Tool Calling？
      - 本 Demo 追求简洁，JSON 模式已足够
      - 生产环境可改用 OpenAI function calling 或 LangChain StructuredOutputParser
    """
    prompt = f"""你是一名财务助理。请从以下发票文本中提取关键字段。
如果信息不完整，标注缺失字段。

发票文本:
{state['raw_text']}

请按以下 JSON 格式返回:
{{
    "vendor_name": "供应商",
    "invoice_number": "发票号",
    "amount": 1234.56,
    "category": "office",
    "confidence": 0.95,
    "flags": []
}}

category 只能是: office(办公), tech(技术), travel(差旅), marketing(市场), other(其他)
"""
    try:
        response = llm.invoke(prompt)
        # 解析 LLM 返回的 JSON 字符串
        data = json.loads(response.content)
        # Pydantic 自动校验字段完整性和类型
        invoice = InvoiceData(**data)
        return {"invoice": invoice, "error": None}
    except Exception as e:
        # 任何异常都不应该让 Graph 崩溃
        # 返回 error 字段，让下游节点或外部重试机制处理
        return {
            "invoice": None,
            "error": f"提取失败: {str(e)}",
            "retry_count": 1
        }


def validate_invoice(state: AgentState) -> dict:
    """
    节点 2: 验证提取结果，标记异常

    验证规则（可根据企业政策调整）:
      - 金额 > 10000 元：标记"需额外审批"
      - 金额 <= 0：标记"金额异常"
      - AI 信心分 < 0.8：标记"建议人工复核"

    为什么不在 extract 节点里做验证？
      - 关注点分离：extract 只管"提取"，validate 只管"规则判断"
      - 方便替换验证规则（比如对接企业 ERP 查重复发票）
      - LangGraph 的图结构让每个节点独立可测
    """
    invoice = state["invoice"]
    if not invoice:
        return {"error": state.get("error", "无发票数据")}

    flags = []

    # ── 规则引擎 ──
    if invoice.amount > 10000:
        flags.append("金额超过 1 万元，需额外审批")
    if invoice.amount <= 0:
        flags.append("金额异常")
    if invoice.confidence < 0.8:
        flags.append("AI 信心较低，建议人工复核")

    # Pydantic v2 模型不可变，需重建对象以更新 flags
    validated = InvoiceData(
        vendor_name=invoice.vendor_name,
        invoice_number=invoice.invoice_number,
        amount=invoice.amount,
        category=invoice.category,
        confidence=invoice.confidence,
        flags=flags
    )

    return {"invoice": validated, "error": None}


def should_retry(state: AgentState) -> str:
    """
    路由函数: 是否重试（本 Demo 中未接入条件边，保留供扩展）

    如果未来需要加入循环（extract 失败 → 重试 → 再次 extract）：
      builder.add_conditional_edges("validate", should_retry, {
          "retry": "extract",
          "fail": END,
          "ok": "format"
      })
    """
    if state["error"] and state["retry_count"] < 3:
        return "retry"
    if state["error"]:
        return "fail"
    return "ok"


def format_result(state: AgentState) -> dict:
    """
    节点 3: 最终输出格式化

    将 InvoiceData 转换为下游系统（Temporal Activity）需要的格式
    包含 summary 字段，方便审批人快速阅读
    """
    invoice = state["invoice"]
    if not invoice:
        return {"error": state.get("error", "未知错误")}

    return {
        "invoice": invoice,
        "summary": f"供应商: {invoice.vendor_name}, 金额: ¥{invoice.amount:.2f}, 类别: {invoice.category}"
    }


# =============================================================================
# 4. 组装 Graph —— 把节点和边连起来
# =============================================================================
# 当前结构: START → extract → validate → format → END（线性流水线）
# 未来可扩展为分支结构（validate 后根据 flags 决定是否需要人工介入）
# ------------------------------------------------------------------------------
builder = StateGraph(AgentState)

builder.add_node("extract", extract_invoice)     # 提取
builder.add_node("validate", validate_invoice)     # 验证
builder.add_node("format", format_result)        # 格式化

# 线性连接（所有发票都走完整流程）
builder.add_edge(START, "extract")
builder.add_edge("extract", "validate")
builder.add_edge("validate", "format")
builder.add_edge("format", END)

# 编译为可执行的 Agent
invoice_agent = builder.compile()


# =============================================================================
# 5. 对外 API —— 封装为普通函数，方便 Temporal Activity 调用
# =============================================================================
# Temporal Activity 不需要知道 LangGraph 的存在
# 它只调用: run_invoice_agent(raw_text) -> dict
# 这是"分层架构"的体现：上层只依赖接口，不依赖实现细节
# ------------------------------------------------------------------------------
def run_invoice_agent(raw_text: str) -> dict:
    """
    运行发票分析 Agent，返回统一格式的结果

    返回结构:
      {
          "success": bool,
          "data": InvoiceData.dict(),       # 成功时存在
          "needs_approval": bool,            # 是否需要人工审批
          "flags": list[str],                # 异常标记
          "summary": str,                    # 一句话摘要
          "error": str                      # 失败时存在
      }

    判断 needs_approval 的逻辑:
      - 金额 > 5000 元 → 必须审批
      - 有异常标记（flags 非空）→ 建议审批
      - 小额且无异常 → 自动通过
    """
    initial_state: AgentState = {
        "raw_text": raw_text,
        "invoice": None,
        "error": None,
        "retry_count": 0
    }
    result = invoice_agent.invoke(initial_state)

    # 处理 Graph 执行失败
    if result.get("error"):
        return {
            "success": False,
            "error": result["error"]
        }

    invoice = result["invoice"]
    return {
        "success": True,
        "data": invoice.model_dump(),
        "needs_approval": invoice.amount > 5000 or len(invoice.flags) > 0,
        "flags": invoice.flags,
        "summary": result.get("summary", "")
    }
