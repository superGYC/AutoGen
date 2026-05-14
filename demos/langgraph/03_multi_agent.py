"""
LangGraph Demo 03 — 多智能体协作（反射模式）
写作者生成内容 → 审阅者检查 → 通过则结束，不通过则返回修改。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."
"""
import os
from typing import TypedDict, Annotated, Literal

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI


# 1. 定义状态
class State(TypedDict):
    messages: Annotated[list, add_messages]
    draft: str          # 当前稿件
    feedback: str       # 审阅意见
    revision_count: int # 修订次数
    approved: bool      # 是否通过


# 2. LLM
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))


# 3. 节点：写作者
def writer_node(state: State) -> State:
    """写作者：基于反馈（如果有）修改稿件"""
    topic = "多智能体框架的选择指南"
    feedback = state.get("feedback", "")
    revision = state.get("revision_count", 0)

    if revision == 0:
        prompt = f"写一篇 200 字的文章，主题是：{topic}"
    else:
        prompt = (
            f"基于以下反馈修改文章：\n"
            f"反馈：{feedback}\n\n"
            f"当前稿件：{state['draft']}\n\n"
            f"请修改后输出完整新版本。"
        )

    response = llm.invoke(prompt)
    return {
        "draft": response.content,
        "revision_count": revision + 1,
    }


# 4. 节点：审阅者
def reviewer_node(state: State) -> State:
    """审阅者：检查稿件，给出通过/不通过+反馈"""
    draft = state["draft"]
    prompt = (
        f"审阅以下稿件：\n\n{draft}\n\n"
        f"检查：1)是否有事实错误 2)是否达到 200 字 3)结构是否清晰\n"
        f"如果通过，回复 'APPROVED'。\n"
        f"如果不通过，回复 'REVISION: ' 加具体修改意见。"
    )
    response = llm.invoke(prompt)
    feedback = response.content

    approved = "APPROVED" in feedback.upper()
    return {
        "feedback": feedback,
        "approved": approved,
        "messages": [response],
    }


# 5. 条件边：根据审阅结果决定走向
def review_router(state: State) -> Literal["writer", "end"]:
    """如果未通过且未超过最大修订次数，返回 writer；否则结束"""
    if state["approved"]:
        return "end"
    if state["revision_count"] >= 3:
        return "end"  # 最多改 3 次
    return "writer"


# 6. 构建图
graph = StateGraph(State)
graph.add_node("writer", writer_node)
graph.add_node("reviewer", reviewer_node)

graph.add_edge(START, "writer")
graph.add_edge("writer", "reviewer")
graph.add_conditional_edges(
    "reviewer",
    review_router,
    {"writer": "writer", "end": END},
)

app = graph.compile()


# 7. 运行
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 LangGraph Demo 03: 多智能体协作 — 写作者+审阅者")
    print("=" * 60)

    result = app.invoke({"messages": [], "revision_count": 0, "approved": False})

    print(f"\n[最终稿件] (修订 {result['revision_count']} 次):")
    print(result["draft"])
    print(f"\n[审阅结果]: {result['feedback']}")
    print("\n✅ 流程完成")
