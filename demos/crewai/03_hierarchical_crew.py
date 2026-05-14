"""
CrewAI Demo 03 — 层级 Crew（Hierarchical）
经理 Agent 管理团队，分配任务、审阅结果。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."
"""
import os

from crewai import Agent, Task, Crew, Process


def main():
    # 经理 Agent：负责任务分配和质量把控
    manager = Agent(
        role="项目经理",
        goal="确保团队按时交付高质量的内容策略方案",
        backstory="你是一个经验丰富的项目经理，善于拆解任务和把控质量。",
        verbose=True,
        allow_delegation=True,
    )

    # 执行 Agent
    researcher = Agent(
        role="内容研究员",
        goal="研究目标受众的内容偏好和竞品策略",
        backstory="你专注于社交媒体内容趋势研究。",
        verbose=True,
        allow_delegation=False,
    )

    strategist = Agent(
        role="策略师",
        goal="基于研究结果制定内容策略",
        backstory="你是一位资深内容策略师，擅长制定可执行的内容计划。",
        verbose=True,
        allow_delegation=False,
    )

    # Task
    task1 = Task(
        description="研究 'AI 编程助手' 话题在小红书和公众号上的热门内容形式。",
        expected_output="内容形式清单（如：教程、对比测评、案例分享等），附带热度分析。",
        agent=researcher,
    )

    task2 = Task(
        description="基于研究结果，制定一份下周的内容发布计划（5 条内容）。",
        expected_output="5 条内容的标题、形式、发布平台和预期效果。",
        agent=strategist,
    )

    # 层级流程：manager 分配和监督
    crew = Crew(
        agents=[researcher, strategist],
        tasks=[task1, task2],
        process=Process.hierarchical,
        manager_agent=manager,
        verbose=True,
    )

    print("=" * 60)
    print("🤖 CrewAI Demo 03: 层级 Crew — 经理带队")
    print("=" * 60)

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("✅ 最终结果:")
    print(result.raw)
    print("=" * 60)


if __name__ == "__main__":
    main()
