"""
CrewAI Demo 01 — 基础 Crew
最简单的 CrewAI 用法：两个 Agent，两个 Task，顺序执行。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."

参考: https://docs.crewai.com/introduction
"""
import os

from crewai import Agent, Task, Crew, Process


def main():
    # 1. 定义 Agent（角色）
    researcher = Agent(
        role="研究员",
        goal="收集关于给定主题的全面信息",
        backstory="你是一个资深研究员，擅长快速搜集和整理信息。",
        verbose=True,
        allow_delegation=False,
    )

    writer = Agent(
        role="写手",
        goal="基于研究资料撰写清晰的总结",
        backstory="你是一个技术写作专家，能把复杂信息写成通俗易懂的内容。",
        verbose=True,
        allow_delegation=False,
    )

    # 2. 定义 Task（任务）
    research_task = Task(
        description="搜索并总结 'LangGraph 的核心特性'，列出 5 个关键功能。",
        expected_output="一个包含 5 个 LangGraph 核心特性的列表，每条带简短说明。",
        agent=researcher,
    )

    write_task = Task(
        description="基于研究员的输出，写一篇 150 字的介绍。",
        expected_output="一段 150 字左右的流畅介绍文字。",
        agent=writer,
        context=[research_task],  # 依赖前一步的输出
    )

    # 3. 组装 Crew（团队）
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,  # 顺序执行
        verbose=True,
    )

    # 4. 启动
    print("=" * 60)
    print("🤖 CrewAI Demo 01: 基础 Crew — 研究+写作")
    print("=" * 60)

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("✅ 最终结果:")
    print(result.raw)
    print("=" * 60)


if __name__ == "__main__":
    main()
