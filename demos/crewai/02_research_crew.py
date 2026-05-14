"""
CrewAI Demo 02 — 研究型 Crew
一个模拟研究团队：研究员搜索 → 分析师分析 → 写手撰写报告。

运行前设置环境变量:
    export OPENAI_API_KEY="sk-..."
"""
import os

from crewai import Agent, Task, Crew, Process
from crewai_tools import ScrapeWebsiteTool


def main():
    # 工具：网页抓取
    scraper = ScrapeWebsiteTool()

    # Agent 定义
    researcher = Agent(
        role="行业研究员",
        goal="收集 2024-2025 年 AI Agent 框架的最新发展信息",
        backstory="你是一位专注于 AI 行业的资深研究员，能快速从网页提取关键信息。",
        verbose=True,
        tools=[scraper],
        allow_delegation=False,
    )

    analyst = Agent(
        role="数据分析师",
        goal="分析各框架的市场定位和优劣势",
        backstory="你擅长将杂乱的信息整理成结构化的分析结论。",
        verbose=True,
        allow_delegation=False,
    )

    writer = Agent(
        role="报告撰写人",
        goal="撰写一份简洁的市场分析报告",
        backstory="你是顶级咨询公司的顾问，报告要专业、有洞察。",
        verbose=True,
        allow_delegation=False,
    )

    # Task 定义
    task_research = Task(
        description="""
        搜索并整理以下三个 AI Agent 框架的最新信息：
        1. AutoGen (microsoft.github.io/autogen)
        2. CrewAI (docs.crewai.com)
        3. LangGraph (langchain-ai.github.io/langgraph)

        对每个框架收集：最新版本号、发布日期、3 个主要新特性。
        如果无法访问网站，基于你的知识提供信息。
        """,
        expected_output="三个框架的版本信息和特性列表。",
        agent=researcher,
    )

    task_analyze = Task(
        description="""
        基于研究员提供的信息，分析三个框架：
        1. 各自最突出的 2 个优势
        2. 各自最明显的 1 个短板
        3. 最适合的使用场景
        """,
        expected_output="结构化的对比分析表格。",
        agent=analyst,
        context=[task_research],
    )

    task_report = Task(
        description="""
        基于分析师的结论，撰写一份 300 字的市场简报。
        标题要吸引人，正文要有数据支撑的观点。
        """,
        expected_output="一份完整的 300 字市场简报。",
        agent=writer,
        context=[task_analyze],
    )

    # 组装
    crew = Crew(
        agents=[researcher, analyst, writer],
        tasks=[task_research, task_analyze, task_report],
        process=Process.sequential,
        verbose=True,
    )

    print("=" * 60)
    print("🤖 CrewAI Demo 02: 研究型 Crew — 市场分析")
    print("=" * 60)

    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("✅ 最终报告:")
    print(result.raw)
    print("=" * 60)


if __name__ == "__main__":
    main()
