"""
LangGraph Demo 01 — 基础状态图
一个简单的顺序流程：输入 → 分析 → 输出。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."

参考: https://langchain-ai.github.io/langgraph/
"""
import os
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI


# 1. 定义状态结构
class State(TypedDict):
    # messages 字段用 Annotated + add_messages 实现自动追加
    messages: Annotated[list, add_messages]
    analysis: str


# 2. 创建 LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
)


# 3. 定义节点函数
def analyze_node(state: State) -> State:
    """分析节点：让 LLM 分析用户输入"""
    user_input = state["messages"][-1].content
    prompt = f"分析以下内容的主题和情绪倾向：\n\n{user_input}\n\n用一句话总结。"
    response = llm.invoke(prompt)
    return {"analysis": response.content}


def respond_node(state: State) -> State:
    """回复节点：基于分析结果生成回复"""
    analysis = state["analysis"]
    user_input = state["messages"][-1].content
    prompt = (
        f"用户说：{user_input}\n"
        f"分析结论：{analysis}\n"
        f"请给出一个友好、有针对性的回复。"
    )
    response = llm.invoke(prompt)
    return {"messages": [response]}


# 4. 构建图
graph = StateGraph(State)
graph.add_node("analyze", analyze_node)
graph.add_node("respond", respond_node)

# 5. 定义边（流转规则）
graph.add_edge(START, "analyze")
graph.add_edge("analyze", "respond")
graph.add_edge("respond", END)

# 6. 编译
app = graph.compile()


# 7. 运行
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 LangGraph Demo 01: 基础状态图 — 分析+回复")
    print("=" * 60)

    # 用户输入
    user_message = "我最近在学习多智能体框架，感觉 LangGraph 好复杂啊！"

    # 运行图
    result = app.invoke({"messages": [("user", user_message)]})

    print(f"\n[用户输入]: {user_message}")
    print(f"\n[分析结果]: {result['analysis']}")
    print(f"\n[Agent 回复]: {result['messages'][-1].content}")
    print("\n✅ 流程完成")
