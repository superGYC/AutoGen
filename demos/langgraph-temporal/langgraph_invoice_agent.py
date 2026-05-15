"""
LangGraph 发票分析 Agent
职责: 提取发票字段 → 验证 → 生成结构化结果

这个模块只管"AI 逻辑", 不管持久化、审批、重试——那些交给 Temporal。
"""
import json
from typing import TypedDict, Annotated
from operator import add

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


# ========== 1. 结构化输出 Schema ==========
class InvoiceData(BaseModel):
    """发票结构化数据"""
    vendor_name: str = Field(description="供应商名称")
    invoice_number: str = Field(description="发票号码")
    amount: float = Field(description="金额（元）")
    category: str = Field(description="费用类别: office/tech/travel/marketing/other")
    confidence: float = Field(description="AI 对提取结果的信心分数 0-1")
    flags: list[str] = Field(default_factory=list, description="异常标记,如 ['金额过高','重复发票']")


# ========== 2. LangGraph State ==========
class AgentState(TypedDict):
    raw_text: str                    # 用户输入的原始发票文本
    invoice: InvoiceData | None      # 提取结果
    error: str | None                # 错误信息
    retry_count: Annotated[int, add] # 重试计数


# ========== 3. 节点实现 ==========
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def extract_invoice(state: AgentState) -> dict:
    """从原始文本中提取发票字段"""
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
        data = json.loads(response.content)
        invoice = InvoiceData(**data)
        return {"invoice": invoice, "error": None}
    except Exception as e:
        return {
            "invoice": None,
            "error": f"提取失败: {str(e)}",
            "retry_count": 1
        }


def validate_invoice(state: AgentState) -> dict:
    """验证提取结果，标记异常"""
    invoice = state["invoice"]
    if not invoice:
        return {"error": state.get("error", "无发票数据")}

    flags = []

    # 规则验证
    if invoice.amount > 10000:
        flags.append("金额超过 1 万元，需额外审批")
    if invoice.amount <= 0:
        flags.append("金额异常")
    if invoice.confidence < 0.8:
        flags.append("AI 信心较低，建议人工复核")

    # 通过引用更新 flags（Pydantic 模型不可变，重建）
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
    """路由: 是否重试"""
    if state["error"] and state["retry_count"] < 3:
        return "retry"
    if state["error"]:
        return "fail"
    return "ok"


def format_result(state: AgentState) -> dict:
    """最终输出格式化"""
    invoice = state["invoice"]
    if not invoice:
        return {"error": state.get("error", "未知错误")}

    return {
        "invoice": invoice,
        "summary": f"供应商: {invoice.vendor_name}, 金额: ¥{invoice.amount:.2f}, 类别: {invoice.category}"
    }


# ========== 4. 组装 Graph ==========
builder = StateGraph(AgentState)

builder.add_node("extract", extract_invoice)
builder.add_node("validate", validate_invoice)
builder.add_node("format", format_result)

builder.add_edge(START, "extract")
builder.add_edge("extract", "validate")
builder.add_edge("validate", "format")
builder.add_edge("format", END)

# 重试路由（简化版：实际可从 validate 回 extract）
# 这里我们保持线性，错误由 Temporal 负责重试策略

invoice_agent = builder.compile()


# ========== 5. 对外 API ==========
def run_invoice_agent(raw_text: str) -> dict:
    """运行发票分析 Agent，返回结构化结果或错误"""
    initial_state: AgentState = {
        "raw_text": raw_text,
        "invoice": None,
        "error": None,
        "retry_count": 0
    }
    result = invoice_agent.invoke(initial_state)

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
