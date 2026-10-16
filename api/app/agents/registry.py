from dataclasses import dataclass
from typing import Final

from app.models import AgentRiskLevel


COORDINATOR_AGENT: Final = "ecommerce_operations_agent"
MARKET_INTELLIGENCE_AGENT: Final = "market_intelligence_agent"
PRODUCT_STRATEGY_AGENT: Final = "product_strategy_agent"
CREATIVE_STRATEGY_AGENT: Final = "creative_strategy_agent"
CONTENT_PRODUCTION_AGENT: Final = "content_production_agent"
GROWTH_EXPERIMENT_AGENT: Final = "growth_experiment_agent"
PERFORMANCE_REVIEW_AGENT: Final = "performance_review_agent"
INVENTORY_OPERATIONS_AGENT: Final = "inventory_operations_agent"
QUALITY_COMPLIANCE_AGENT: Final = "quality_compliance_agent"


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    version: str
    description: str
    tool_allowlist: frozenset[str]


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    risk_level: AgentRiskLevel
    description: str
    idempotent: bool = True
    owner_only: bool = False


@dataclass(frozen=True)
class WorkflowDefinition:
    key: str
    version: str
    title: str
    description: str
    agents: tuple[str, ...]
    required_context_any: tuple[str, ...]
    default_risk_level: AgentRiskLevel
    enabled: bool = True

    @property
    def version_manifest(self) -> dict:
        """version清单，只从版本化注册表解析职责、工具白名单和工作流定义。"""
        return {
            "workflow": {"key": self.key, "version": self.version},
            "agents": {agent: AGENT_REGISTRY[agent].version for agent in self.agents},
            "policies": {"risk_policy": "1.0.0", "tool_gateway": "1.0.0"},
        }


TOOL_REGISTRY: Final[dict[str, ToolDefinition]] = {
    "product.read": ToolDefinition("product.read", AgentRiskLevel.R0, "读取商品与经营上下文"),
    "store.read": ToolDefinition("store.read", AgentRiskLevel.R0, "读取店铺组合与经营上下文"),
    "competitor.read": ToolDefinition("competitor.read", AgentRiskLevel.R0, "读取竞品与监控快照"),
    "competitor.monitor.run": ToolDefinition(
        "competitor.monitor.run", AgentRiskLevel.R1, "生成竞品监控快照"
    ),
    "diagnosis.draft": ToolDefinition("diagnosis.draft", AgentRiskLevel.R1, "生成商品诊断草稿"),
    "creative.plan.draft": ToolDefinition(
        "creative.plan.draft", AgentRiskLevel.R1, "生成可编辑创意方案"
    ),
    "content.image.generate": ToolDefinition(
        "content.image.generate", AgentRiskLevel.R1, "调用图片供应商生成候选素材"
    ),
    "content.video.generate": ToolDefinition(
        "content.video.generate", AgentRiskLevel.R1, "调用视频供应商生成候选素材"
    ),
    "promotion.link.draft": ToolDefinition(
        "promotion.link.draft", AgentRiskLevel.R1, "生成推广链接配置草稿"
    ),
    "ad.recommendation.draft": ToolDefinition(
        "ad.recommendation.draft", AgentRiskLevel.R1, "生成投放建议草稿"
    ),
    "ad.experiment.create": ToolDefinition(
        "ad.experiment.create", AgentRiskLevel.R2, "创建正式投放实验"
    ),
    "performance.review.draft": ToolDefinition(
        "performance.review.draft", AgentRiskLevel.R1, "生成周期经营复盘草稿"
    ),
    "inventory.read": ToolDefinition("inventory.read", AgentRiskLevel.R0, "读取 SKU 与库存状态"),
    "inventory.advice.draft": ToolDefinition(
        "inventory.advice.draft", AgentRiskLevel.R1, "生成库存建议草稿"
    ),
    "inventory.adjust": ToolDefinition(
        "inventory.adjust",
        AgentRiskLevel.R3,
        "写入真实库存调整流水",
        owner_only=True,
    ),
    "artifact.persist": ToolDefinition(
        "artifact.persist", AgentRiskLevel.R2, "采用草稿并写入正式业务对象"
    ),
}


AGENT_REGISTRY: Final[dict[str, AgentDefinition]] = {
    COORDINATOR_AGENT: AgentDefinition(
        COORDINATOR_AGENT,
        "1.0.0",
        "只负责意图识别、受控工作流路由和结果汇总",
        # 结果汇总环节才把各角色草稿采用为正式业务对象（PRD FR-75），
        # 其余角色只产出草稿，不持有写入正式对象的权限。
        frozenset({"artifact.persist"}),
    ),
    MARKET_INTELLIGENCE_AGENT: AgentDefinition(
        MARKET_INTELLIGENCE_AGENT,
        "1.0.0",
        "竞品变化、市场机会和卖点趋势",
        frozenset({"product.read", "store.read", "competitor.read", "competitor.monitor.run"}),
    ),
    PRODUCT_STRATEGY_AGENT: AgentDefinition(
        PRODUCT_STRATEGY_AGENT,
        "1.0.0",
        "商品定位、价格带、人群、卖点和优化动作",
        frozenset({"product.read", "competitor.read", "diagnosis.draft"}),
    ),
    CREATIVE_STRATEGY_AGENT: AgentDefinition(
        CREATIVE_STRATEGY_AGENT,
        "1.0.0",
        "主图、视频脚本、标题与详情策略",
        frozenset({"product.read", "diagnosis.draft", "creative.plan.draft"}),
    ),
    CONTENT_PRODUCTION_AGENT: AgentDefinition(
        CONTENT_PRODUCTION_AGENT,
        "1.0.0",
        "候选素材生产、版本和供应商任务编排",
        frozenset({"product.read", "content.image.generate", "content.video.generate"}),
    ),
    GROWTH_EXPERIMENT_AGENT: AgentDefinition(
        GROWTH_EXPERIMENT_AGENT,
        "1.0.0",
        "推广链接、投放建议和实验假设",
        frozenset(
            {"product.read", "promotion.link.draft", "ad.recommendation.draft", "ad.experiment.create"}
        ),
    ),
    PERFORMANCE_REVIEW_AGENT: AgentDefinition(
        PERFORMANCE_REVIEW_AGENT,
        "1.0.0",
        "经营数据、素材、实验和周期复盘",
        frozenset({"product.read", "store.read", "performance.review.draft"}),
    ),
    INVENTORY_OPERATIONS_AGENT: AgentDefinition(
        INVENTORY_OPERATIONS_AGENT,
        "1.0.0",
        "库存风险、补货、调拨和盘点建议",
        frozenset({"product.read", "store.read", "inventory.read", "inventory.advice.draft", "inventory.adjust"}),
    ),
    QUALITY_COMPLIANCE_AGENT: AgentDefinition(
        QUALITY_COMPLIANCE_AGENT,
        "1.0.0",
        "结构、事实依据、合规、风险和输出质量",
        frozenset(),
    ),
}


WORKFLOW_REGISTRY: Final[dict[str, WorkflowDefinition]] = {
    "product_diagnosis_optimization": WorkflowDefinition(
        "product_diagnosis_optimization",
        "1.0.0",
        "商品诊断与优化",
        "结合商品与竞品上下文生成诊断和可测试创意策略",
        (PRODUCT_STRATEGY_AGENT, CREATIVE_STRATEGY_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id",),
        AgentRiskLevel.R2,
    ),
    "creative_content_production": WorkflowDefinition(
        "creative_content_production",
        "1.0.0",
        "创意与素材生产",
        "从创意策略生成图片、视频和内容候选版本",
        (CREATIVE_STRATEGY_AGENT, CONTENT_PRODUCTION_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id",),
        AgentRiskLevel.R1,
    ),
    "competitor_continuous_monitoring": WorkflowDefinition(
        "competitor_continuous_monitoring",
        "1.0.0",
        "竞品持续监控",
        "采集授权竞品快照并形成结构化变化建议",
        (MARKET_INTELLIGENCE_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id", "store_id"),
        AgentRiskLevel.R1,
    ),
    "growth_ad_experiment_loop": WorkflowDefinition(
        "growth_ad_experiment_loop",
        "1.0.0",
        "投放实验闭环",
        "形成推广链接、投放建议、实验假设和复盘证据链",
        (GROWTH_EXPERIMENT_AGENT, PERFORMANCE_REVIEW_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id",),
        AgentRiskLevel.R2,
    ),
    "periodic_performance_review": WorkflowDefinition(
        "periodic_performance_review",
        "1.0.0",
        "周期经营复盘",
        "汇总周期经营数据并生成可编辑复盘和行动建议",
        (PERFORMANCE_REVIEW_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id", "store_id"),
        AgentRiskLevel.R1,
    ),
    "inventory_operations": WorkflowDefinition(
        "inventory_operations",
        "1.0.0",
        "库存运营",
        "识别缺货和积压风险并生成补货、调拨或盘点建议",
        (INVENTORY_OPERATIONS_AGENT, QUALITY_COMPLIANCE_AGENT),
        ("product_id", "store_id"),
        AgentRiskLevel.R1,
    ),
    "store_portfolio_inspection": WorkflowDefinition(
        "store_portfolio_inspection",
        "1.0.0",
        "店铺组合巡检",
        "跨商品发现市场、经营、素材和库存异常并分派建议任务",
        (
            MARKET_INTELLIGENCE_AGENT,
            PRODUCT_STRATEGY_AGENT,
            PERFORMANCE_REVIEW_AGENT,
            INVENTORY_OPERATIONS_AGENT,
            QUALITY_COMPLIANCE_AGENT,
        ),
        ("store_id",),
        AgentRiskLevel.R1,
    ),
}


WORKFLOW_ALIASES: Final = {"product_operation": "product_diagnosis_optimization"}


def get_workflow(workflow_key: str) -> WorkflowDefinition:
    """获取工作流，只从版本化注册表解析职责、工具白名单和工作流定义。"""
    canonical_key = WORKFLOW_ALIASES.get(workflow_key, workflow_key)
    workflow = WORKFLOW_REGISTRY.get(canonical_key)
    if workflow is None or not workflow.enabled:
        raise KeyError(f"Workflow is not registered or enabled: {workflow_key}")
    return workflow


def route_intent(intent: str) -> WorkflowDefinition:
    """路由intent，依据结构化状态选择下一个已注册节点，避免隐式或无界跳转。"""
    # 节点只通过结构化状态和受控工具交换数据，禁止绕过策略边界写入结果。
    normalized = intent.strip().lower()
    keyword_routes = (
        (("库存", "缺货", "补货", "盘点", "inventory"), "inventory_operations"),
        (("竞品", "对手", "monitor", "competitor"), "competitor_continuous_monitoring"),
        (("投放", "广告", "实验", "推广", "ad "), "growth_ad_experiment_loop"),
        (("复盘", "经营分析", "performance"), "periodic_performance_review"),
        (("店铺巡检", "全店", "组合", "portfolio"), "store_portfolio_inspection"),
        (("图片", "视频", "素材", "脚本", "content"), "creative_content_production"),
    )
    for keywords, workflow_key in keyword_routes:
        if any(keyword in normalized for keyword in keywords):
            return WORKFLOW_REGISTRY[workflow_key]
    return WORKFLOW_REGISTRY["product_diagnosis_optimization"]


def is_workflow_enabled(workspace_settings: dict, workflow_key: str) -> bool:
    """判断工作流enabled，只从版本化注册表解析职责、工具白名单和工作流定义。"""
    if workspace_settings.get("agent_platform_enabled", True) is False:
        return False
    canonical_key = WORKFLOW_ALIASES.get(workflow_key, workflow_key)
    workflow_flags = workspace_settings.get("agent_workflow_flags", {})
    return workflow_flags.get(canonical_key, True) is not False
