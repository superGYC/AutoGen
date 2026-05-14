"""
AutoGen Demo 03 — 群聊（Group Chat）
三个 Agent 在群聊中协作完成一个内容创作任务。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."
"""
import os
import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient


async def main():
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # 三个角色
    researcher = AssistantAgent(
        name="Researcher",
        model_client=model_client,
        system_message=(
            "你是研究员。你负责收集信息和事实。"
            "你提供的数据必须准确、可验证。"
        ),
    )

    writer = AssistantAgent(
        name="Writer",
        model_client=model_client,
        system_message=(
            "你是写手。你基于研究员提供的信息撰写内容。"
            "你的文字要生动、有吸引力。"
        ),
    )

    editor = AssistantAgent(
        name="Editor",
        model_client=model_client,
        system_message=(
            "你是编辑。你负责检查内容的准确性和风格。"
            "如果发现问题，提出修改意见。"
            "如果内容通过审核，说 'APPROVED'。"
        ),
    )

    # 最多 12 条消息自动终止
    termination = MaxMessageTermination(max_messages=12)

    team = RoundRobinGroupChat(
        participants=[researcher, writer, editor],
        termination_condition=termination,
    )

    task = "一起创作一篇 200 字的短文，介绍'多智能体系统'这个概念。"

    print("=" * 60)
    print("🤖 AutoGen Demo 03: 群聊协作 — 内容创作")
    print("=" * 60)

    async for message in team.run_stream(task=task):
        if hasattr(message, "source"):
            print(f"\n[{message.source}]: {message.content[:300]}")
        else:
            print(f"\n[系统]: {message}")

    print("\n✅ 群聊结束")


if __name__ == "__main__":
    asyncio.run(main())
