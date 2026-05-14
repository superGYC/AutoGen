"""
LangGraph Demo 02 — RAG Agent（检索增强生成）
一个简单的 RAG 流程：用户提问 → 检索知识 → 生成回答。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."
"""
import os
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document


# 1. 定义状态
class State(TypedDict):
    messages: Annotated[list, add_messages]
    retrieved_docs: list  # 检索到的文档


# 2. 初始化组件
llm = ChatOpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))

# 3. 构建知识库（模拟）
docs = [
    Document(page_content="AutoGen 是 Microsoft 开发的多智能体对话框架，支持群聊和代码执行。"),
    Document(page_content="CrewAI 使用角色驱动的团队模型，适合快速搭建内容生产流程。"),
    Document(page_content="LangGraph 基于状态图，提供精确的工作流控制和持久化 checkpoint。"),
    Document(page_content="多智能体系统的核心挑战是编排（orchestration）和状态管理。"),
]
vectorstore = InMemoryVectorStore.from_documents(docs, embeddings)


# 4. 定义节点
def retrieve_node(state: State) -> State:
    """检索节点：从知识库找相关内容"""
    user_question = state["messages"][-1].content
    results = vectorstore.similarity_search(user_question, k=2)
    return {"retrieved_docs": results}


def generate_node(state: State) -> State:
    """生成节点：基于检索结果回答问题"""
    docs = state["retrieved_docs"]
    user_question = state["messages"][-1].content

    context = "\n\n".join([f"- {doc.page_content}" for doc in docs])
    prompt = (
        f"基于以下参考资料回答问题：\n\n"
        f"{context}\n\n"
        f"问题：{user_question}\n\n"
        f"请给出简洁准确的回答，如果资料不够就说'我不知道'。"
    )
    response = llm.invoke(prompt)
    return {"messages": [response]}


# 5. 构建图
graph = StateGraph(State)
graph.add_node("retrieve", retrieve_node)
graph.add_node("generate", generate_node)

graph.add_edge(START, "retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)

app = graph.compile()


# 6. 运行
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 LangGraph Demo 02: RAG Agent — 知识问答")
    print("=" * 60)

    questions = [
        "AutoGen 是谁开发的？",
        "CrewAI 适合什么场景？",
        "LangGraph 的核心优势是什么？",
    ]

    for q in questions:
        result = app.invoke({"messages": [("user", q)]})
        answer = result["messages"][-1].content
        print(f"\n[Q] {q}")
        print(f"[A] {answer}")

    print("\n✅ 所有问题回答完毕")
