"""
Temporal Activities —— 实际执行业务逻辑
======================================

Activity 是 Temporal 中"真正干活"的地方。

关键设计原则:
  1. Workflow 不直接调用 LLM / 数据库 / 外部 API —— 这些都在 Activity 里
  2. Activity 可以有副作用（调用 API、发邮件、付款）
  3. Temporal 保证 Activity "至少执行一次"，所以 Activity 必须是幂等的
  4. Activity 可以配置独立的超时、重试策略（见 temporal_workflow.py）

为什么 LangGraph Agent 要包在 Activity 里？
  - LangGraph 调用 LLM 是"非确定性"的（网络延迟、LLM 响应变化）
  - Temporal Workflow 要求确定性（同样的输入必须产生同样的执行路径）
  - 把 LLM 调用放在 Activity 中，Temporal 可以重试、超时、失败隔离

Activity 的幂等性怎么保证？
  - Temporal 的 Activity 可能被重试（比如 Worker 崩溃后重新调度）
  - 副作用操作（如 process_payment）使用 workflow_id 作为幂等键
  - 外部系统需实现："相同的 workflow_id 不重复执行"
"""
import os
from temporalio import activity

# ── 安全导入 ──────────────────────────────────────────────────
# activity.imports_passed_through() 允许 Activity 导入业务模块
# 因为 Activity 可以执行副作用（调用 LLM、API 等）
with activity.imports_passed_through():
    from langgraph_invoice_agent import run_invoice_agent


# =============================================================================
# Activity 1: 调用 LangGraph Agent 分析发票
# =============================================================================
@activity.defn
async def analyze_invoice(raw_text: str) -> dict:
    """
    Activity: 运行 LangGraph 发票分析 Agent

    职责:
      - 接收原始发票文本
      - 调用 LangGraph Agent 提取结构化字段
      - 返回分析结果（成功/失败、是否需要审批、异常标记等）

    幂等性:
      - 本 Activity 是纯函数（输入文本 → 输出结果）
      - 多次执行结果一致（temperature=0 + 确定性 prompt）
      - 即使重试也不会产生副作用

    失败场景:
      - OpenAI API 超时 → Temporal 自动重试（指数退避）
      - LLM 返回无效 JSON → LangGraph 内部捕获，返回 error
      - 网络故障 → Temporal 重试

    为什么 Activity 可以是 async？
      - Temporal 支持 async Activity，可以并发执行多个 Activity
      - 但本 Activity 内部调用的是同步 LLM API（run_invoice_agent）
      - 未来如果换成异步 LLM SDK（如 ainvoke），无需改架构
    """
    activity.logger.info(f"[Activity] 开始分析发票: {raw_text[:50]}...")

    # 调用 LangGraph Agent（同步调用，在 async Activity 中）
    result = run_invoice_agent(raw_text)

    activity.logger.info(
        f"[Activity] 分析结果: success={result['success']}, "
        f"needs_approval={result.get('needs_approval')}"
    )
    return result


# =============================================================================
# Activity 2: 通知审批人
# =============================================================================
@activity.defn
async def notify_approver(payload: dict) -> None:
    """
    Activity: 通知财务审批人有待审批的发票

    职责:
      - 向审批人发送通知（本 Demo 打印到控制台）
      - 实际生产环境: 发邮件 / 发飞书 / 发钉钉 / 发短信

    幂等性注意:
      - 通知可以重复发送（审批人收到两次通知不会出错）
      - 但如果接入付费短信，建议用 workflow_id 去重

    参数结构:
      {
          "workflow_id": str,
          "summary": str,      # 一句话摘要
          "flags": list[str],  # 异常标记
          "amount": float      # 金额
      }
    """
    workflow_id = payload["workflow_id"]
    amount = payload["amount"]
    flags = payload["flags"]
    summary = payload["summary"]

    # ── 控制台通知（生产环境替换为真实通知渠道）──
    print("\n" + "=" * 60)
    print("🚨 待审批通知")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   金额: ¥{amount:.2f}")
    print(f"   摘要: {summary}")
    if flags:
        print(f"   ⚠️ 异常标记: {', '.join(flags)}")
    print(f"\n   审批命令: python client.py approve {workflow_id}")
    print("=" * 60 + "\n")

    activity.logger.info(f"[Activity] 已通知审批人: {workflow_id}")


# =============================================================================
# Activity 3: 执行付款（有副作用，必须幂等）
# =============================================================================
@activity.defn
async def process_payment(payload: dict) -> None:
    """
    Activity: 执行付款或入账操作

    ⚠️ 这是有副作用的操作，必须幂等！

    为什么必须幂等？
      - Temporal 保证 Activity "至少执行一次"
      - 如果 Worker 在 Activity 执行后崩溃，Temporal 不确定是否成功，会重试
      - 没有幂等保证 = 可能重复付款

    幂等实现方案:
      - 用 workflow_id 作为幂等键
      - 付款系统先查："这个 workflow_id 是否已付款？"
      - 已付款 → 直接返回成功，不重复扣款
      - 未付款 → 执行扣款，记录 workflow_id

    参数结构:
      {
          "workflow_id": str,
          "invoice": dict,              # 发票结构化数据
          "auto_approved": bool,        # 是否系统自动通过
          "approver": str,              # 审批人姓名（人工审批时）
          "notes": str                  # 审批备注
      }
    """
    workflow_id = payload["workflow_id"]
    invoice = payload["invoice"]
    auto_approved = payload.get("auto_approved", False)
    approver = payload.get("approver", "系统")

    # ── 控制台输出（生产环境替换为真实付款 API 调用）──
    print("\n" + "=" * 60)
    print("💰 执行付款")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   供应商: {invoice.get('vendor_name')}")
    print(f"   金额: ¥{invoice.get('amount', 0):.2f}")
    print(f"   审批方式: {'自动' if auto_approved else f'人工 ({approver})'}")
    print("=" * 60 + "\n")

    # 生产环境:
    # payment_api.charge(
    #     idempotency_key=workflow_id,  # ← 关键！防止重复付款
    #     vendor=invoice["vendor_name"],
    #     amount=invoice["amount"],
    #     metadata={"auto_approved": auto_approved, "approver": approver}
    # )

    activity.logger.info(f"[Activity] 付款完成: {workflow_id}")


# =============================================================================
# Activity 4: 记录失败
# =============================================================================
@activity.defn
async def log_failure(payload: dict) -> None:
    """
    Activity: 记录分析失败

    职责:
      - 将失败信息写入日志/数据库/监控系统
      - 供运维人员排查问题

    参数结构:
      {
          "workflow_id": str,
          "stage": str,       # 失败阶段: analysis / approval / payment
          "error": str        # 错误信息
      }
    """
    workflow_id = payload["workflow_id"]
    stage = payload["stage"]
    error = payload["error"]

    print(f"\n❌ Workflow {workflow_id} 在 [{stage}] 阶段失败: {error}\n")

    # 生产环境:
    # - 写入结构化日志（ELK / Datadog / Grafana Loki）
    # - 发送告警（PagerDuty / OpsGenie）
    # - 记录到数据库供后续审计

    activity.logger.error(f"[Activity] 失败记录: {workflow_id} / {stage}: {error}")


# =============================================================================
# Activity 5: 记录拒绝
# =============================================================================
@activity.defn
async def log_rejection(payload: dict) -> None:
    """
    Activity: 记录审批拒绝

    职责:
      - 记录审批人、拒绝原因、时间戳
      - 供审计和后续分析

    参数结构:
      {
          "workflow_id": str,
          "invoice": dict,
          "reason": str       # 拒绝原因
      }
    """
    workflow_id = payload["workflow_id"]
    reason = payload["reason"]

    print(f"\n🚫 Workflow {workflow_id} 审批被拒绝: {reason}\n")

    # 生产环境:
    # - 通知提交人（"你的发票被拒绝了，原因：xxx"）
    # - 记录到拒绝原因库（分析常见拒绝模式）

    activity.logger.info(f"[Activity] 审批拒绝: {workflow_id}: {reason}")


# =============================================================================
# Activity 6: 超时升级
# =============================================================================
@activity.defn
async def escalate_timeout(payload: dict) -> None:
    """
    Activity: 审批超时，升级通知

    职责:
      - 原审批人 48 小时未响应，通知上级或替代审批人
      - 避免流程卡死

    参数结构:
      {
          "workflow_id": str,
          "amount": float      # 金额（用于判断升级策略）
      }

    升级策略示例:
      - 金额 < 10000: 通知部门经理
      - 金额 >= 10000: 通知 CFO
      - 金额 >= 50000: 通知 CEO + 财务委员会
    """
    workflow_id = payload["workflow_id"]
    amount = payload["amount"]

    print("\n" + "=" * 60)
    print("⏰ 审批超时升级")
    print(f"   Workflow ID: {workflow_id}")
    print(f"   金额: ¥{amount:.2f}")
    print(f"   已超过 48 小时未审批，已通知上级")
    print("=" * 60 + "\n")

    # 生产环境:
    # if amount >= 50000:
    #     notify_ceo(workflow_id)
    # else:
    #     notify_manager(workflow_id)

    activity.logger.warning(f"[Activity] 审批超时: {workflow_id}")
