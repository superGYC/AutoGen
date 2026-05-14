"""
AutoGen Demo 01 — 基础对话
两个 Agent 互相讨论，完成一个简单的数学问题。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."

参考: https://microsoft.github.io/autogen/stable/
"""
import os
import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient


async def main():
    # 1. 配置 LLM 客户端
    # 你可以换成其他模型：gpt-4o, claude-3-5-sonnet 等
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # 2. 创建两个 Agent
    agent_a = AssistantAgent(
        name="Alice",
        model_client=model_client,
        system_message=(
            "你是一个数学爱好者。你喜欢用简单易懂的方式解释数学问题。"
            "当你觉得讨论可以结束时，说 'TERMINATE'。"
        ),
    )

    agent_b = AssistantAgent(
        name="Bob",
        model_client=model_client,
        system_message=(
            "你是一个严谨的逻辑分析师。你会检查别人的推理是否有漏洞。"
            "当你觉得讨论可以结束时，说 'TERMINATE'。"
        ),
    )

    # 3. 终止条件：任意 Agent 说 "TERMINATE" 就结束
    termination = TextMentionTermination("TERMINATE")

    # 4. 创建一个轮询群聊（Alice → Bob → Alice → ...）
    team = RoundRobinGroupChat(
        participants=[agent_a, agent_b],
        termination_condition=termination,
        max_turns=10,  # 安全上限，防止无限循环
    )

    # 5. 发起对话
    print("=" * 60)
    print("🤖 AutoGen Demo 01: 基础对话 — 两个 Agent 讨论数学问题")
    print("=" * 60)

    async for message in team.run_stream(task="计算 1+2+3+...+100 的和，并解释原理。"):
        if hasattr(message, "source"):
            print(f"\n[{message.source}]: {message.content}")
        else:
            print(f"\n[系统]: {message}")

    print("\n" + "=" * 60)
    print("✅ 对话结束")


if __name__ == "__main__":
    asyncio.run(main())
