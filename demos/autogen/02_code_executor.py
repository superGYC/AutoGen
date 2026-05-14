"""
AutoGen Demo 02 — 代码执行器
一个会写代码的 Agent + 一个能执行代码的 Agent，完成数据分析任务。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."

⚠️ 代码执行有安全风险，只在你信任的环境中运行！
"""
import os
import asyncio

from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor


async def main():
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # 1. 代码执行 Agent（能跑 Python）
    code_executor = CodeExecutorAgent(
        name="PythonExecutor",
        code_executor=LocalCommandLineCodeExecutor(
            work_dir="./coding",  # 代码执行的工作目录
        ),
    )

    # 2. 程序员 Agent（负责写代码）
    coder = AssistantAgent(
        name="Coder",
        model_client=model_client,
        system_message=(
            "你是一个数据分析师。你写 Python 代码解决数据分析问题。"
            "代码要完整、可运行。每次只回复一段代码或解释。"
            "当你觉得任务完成时，说 'TERMINATE'。"
        ),
    )

    termination = TextMentionTermination("TERMINATE")

    team = RoundRobinGroupChat(
        participants=[coder, code_executor],
        termination_condition=termination,
        max_turns=15,
    )

    task = """
请用 Python 完成以下任务：
1. 创建一个包含 100 个随机数的列表（范围 0-1000）
2. 计算平均值、中位数、标准差
3. 找出最大值和最小值
4. 打印结果
"""

    print("=" * 60)
    print("🤖 AutoGen Demo 02: 代码执行 — 数据分析")
    print("=" * 60)

    async for message in team.run_stream(task=task):
        if hasattr(message, "source"):
            print(f"\n[{message.source}]: {message.content[:500]}")
        else:
            print(f"\n[系统]: {message}")

    print("\n✅ 任务结束")


if __name__ == "__main__":
    asyncio.run(main())
