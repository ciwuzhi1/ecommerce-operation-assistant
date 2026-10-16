import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models import AgentApprovalStatus, AgentMemoryStatus, AgentReviewDecision
from app.models import AgentRiskLevel, AgentRunStatus, AgentTaskStatus, MembershipStatus
from app.models import CreativePlanStatus, CreativePlanType, GenerationJobKind
from app.models import GenerationJobStatus, InventoryMovementType, Platform
from app.models import PlatformAccountStatus, ProductSkuStatus, StoreStatus, UserRole, UserStatus
from app.models import WorkspaceStatus


class ProductBase(BaseModel):
    # 商品 schema 覆盖多平台通用字段，平台差异通过 external_* 和 platform_status 扩展。
    store_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    platform: Platform = Platform.DOUYIN
    category: str | None = Field(default=None, max_length=120)
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    target_audience: str | None = None
    selling_points: list[str] = Field(default_factory=list)
    product_url: HttpUrl | None = None
    external_product_id: str | None = Field(default=None, max_length=120)
    platform_status: str | None = Field(default=None, max_length=50)
    images: list[str] = Field(default_factory=list)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    # PATCH schema 所有字段可选，未传字段保持原值，避免编辑表单误清空商品资料。
    name: str | None = Field(default=None, min_length=1, max_length=255)
    store_id: int | None = None
    platform: Platform | None = None
    category: str | None = Field(default=None, max_length=120)
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    target_audience: str | None = None
    selling_points: list[str] | None = None
    product_url: HttpUrl | None = None
    external_product_id: str | None = Field(default=None, max_length=120)
    platform_status: str | None = Field(default=None, max_length=50)
    images: list[str] | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StoreBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    platform: Platform
    status: StoreStatus = StoreStatus.ACTIVE
    external_store_id: str | None = Field(default=None, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    note: str | None = None


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    platform: Platform | None = None
    status: StoreStatus | None = None
    external_store_id: str | None = Field(default=None, max_length=120)
    owner_name: str | None = Field(default=None, max_length=120)
    note: str | None = None


class PlatformAccountBase(BaseModel):
    # 授权 metadata 只用于记录非敏感状态；真实 token 后续应接入密钥管理，不由前端 schema 承载。
    platform: Platform
    account_name: str = Field(min_length=1, max_length=255)
    external_account_id: str | None = Field(default=None, max_length=120)
    status: PlatformAccountStatus = PlatformAccountStatus.ACTIVE
    auth_metadata: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class PlatformAccountCreate(PlatformAccountBase):
    pass


class PlatformAccountRead(PlatformAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    created_at: datetime
    updated_at: datetime


class PlatformAuthorizationStartRequest(BaseModel):
    # 授权类型限定在官方/API/服务商/手工导出，不支持绕登录、验证码或风控的采集方式。
    auth_type: Literal["oauth2", "official_api", "service_provider", "manual_export"] = "oauth2"
    redirect_uri: HttpUrl | None = None
    scopes: list[str] = Field(default_factory=list, max_length=20)
    callback_url: HttpUrl | None = None
    note: str | None = Field(default=None, max_length=500)


class PlatformAuthorizationRead(BaseModel):
    account_id: int
    platform: Platform
    status: Literal["pending", "authorized", "expired", "disabled", "failed"]
    auth_type: str
    state: str | None = None
    authorization_url: str | None = None
    next_action: str
    safety_note: str
    updated_at: datetime


class PlatformAuthorizationCallbackRequest(BaseModel):
    state: str
    status: Literal["authorized", "expired", "disabled", "failed"]
    external_account_id: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(default=None, max_length=500)


class StoreRead(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    platform_accounts: list[PlatformAccountRead] = Field(default_factory=list)


class ProductSkuBase(BaseModel):
    sku_code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    attributes: dict[str, Any] = Field(default_factory=dict)
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    status: ProductSkuStatus = ProductSkuStatus.ACTIVE


class ProductSkuCreate(ProductSkuBase):
    # 创建 SKU 时可带初始库存信息，后端会转为库存档案和流水，而不是直接无痕覆盖数量。
    initial_quantity: int = Field(default=0, ge=0)
    warning_threshold: int = Field(default=0, ge=0)
    location: str | None = Field(default=None, max_length=120)


class ProductSkuUpdate(BaseModel):
    sku_code: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    attributes: dict[str, Any] | None = None
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    status: ProductSkuStatus | None = None
    warning_threshold: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=120)


class ProductSkuRead(ProductSkuBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: int
    quantity: int
    locked_quantity: int
    warning_threshold: int
    location: str | None = None
    created_at: datetime
    updated_at: datetime


class StoreInventoryRow(BaseModel):
    # 店铺库存行是聚合展示模型，available_quantity 由总量减锁定量得到，用于预警和投放节奏判断。
    product_id: int
    product_name: str
    sku_id: int
    sku_code: str
    sku_name: str
    quantity: int
    locked_quantity: int
    available_quantity: int
    warning_threshold: int
    is_low_stock: bool
    location: str | None = None


class StoreInventorySummary(BaseModel):
    store_id: int
    sku_count: int
    total_quantity: int
    total_locked_quantity: int
    total_available_quantity: int
    low_stock_count: int
    rows: list[StoreInventoryRow]


class StoreInventoryMovementRow(BaseModel):
    id: int
    product_id: int
    product_name: str
    sku_id: int
    sku_code: str
    sku_name: str
    movement_type: InventoryMovementType
    quantity_delta: int
    locked_delta: int
    before_quantity: int
    after_quantity: int
    before_locked_quantity: int
    after_locked_quantity: int
    reason: str | None = None
    operator_name: str | None = None
    created_at: datetime


class StoreInventoryAdviceRead(BaseModel):
    source: str
    summary: str
    risks: list[str] = Field(default_factory=list)
    replenishment_actions: list[str] = Field(default_factory=list)
    operation_actions: list[str] = Field(default_factory=list)
    ad_controls: list[str] = Field(default_factory=list)
    raw_output: dict[str, Any] = Field(default_factory=dict)


class InventoryMovementCreate(BaseModel):
    # 库存变更入参保留数量变更和锁定变更两套 delta，调用方必须明确是哪类库存动作。
    movement_type: InventoryMovementType
    quantity_delta: int = 0
    locked_delta: int = 0
    reason: str | None = Field(default=None, max_length=255)
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: str | None = Field(default=None, max_length=120)
    operator_name: str | None = Field(default=None, max_length=120)


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_item_id: int
    sku_id: int
    movement_type: InventoryMovementType
    quantity_delta: int
    locked_delta: int
    before_quantity: int
    after_quantity: int
    before_locked_quantity: int
    after_locked_quantity: int
    reason: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    operator_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductSkuDetail(ProductSkuRead):
    inventory_item: InventoryItemRead | None = None
    inventory_movements: list["InventoryMovementRead"] = Field(default_factory=list)


class PlatformProductMappingBase(BaseModel):
    # 平台映射 schema 允许 store/product/sku 分层绑定，支持未来多店铺多平台同步。
    store_id: int | None = None
    sku_id: int | None = None
    platform: Platform
    external_product_id: str = Field(min_length=1, max_length=120)
    external_sku_id: str | None = Field(default=None, max_length=120)
    listing_url: HttpUrl | None = None
    status: str | None = Field(default=None, max_length=50)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class PlatformProductMappingCreate(PlatformProductMappingBase):
    pass


class PlatformProductMappingRead(PlatformProductMappingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class CompetitorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    platform: Platform = Platform.DOUYIN
    url: HttpUrl | None = None
    price: Decimal | None = Field(default=None, ge=0)
    sales_hint: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    main_image: str | None = Field(default=None, max_length=1024)
    selling_points: list[str] = Field(default_factory=list)
    review_keywords: list[str] = Field(default_factory=list)


class CompetitorCreate(CompetitorBase):
    pass


class CompetitorUrlImport(BaseModel):
    url: HttpUrl
    platform: Platform = Platform.DOUYIN


class CompetitorRead(CompetitorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class PublicLinkParseTaskRead(BaseModel):
    # 解析任务读模型暴露状态和失败原因，方便前端轮询展示，不暴露底层请求细节。
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    task_type: str
    url: str
    platform: Platform
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    next_run_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorMonitorCreate(BaseModel):
    interval_days: int = Field(default=1, ge=1, le=30)
    note: str | None = None


class CompetitorMonitorSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    product_id: int
    competitor_id: int
    checked_at: datetime
    status: str
    title: str | None = None
    price: Decimal | None = None
    sales_hint: str | None = None
    main_image: str | None = None
    selling_points: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class CompetitorMonitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    competitor_id: int
    status: str
    interval_days: int
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    snapshots: list[CompetitorMonitorSnapshotRead] = Field(default_factory=list)


class CompetitorMonitorSchedulerRunResult(BaseModel):
    checked_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    monitor_ids: list[int] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CreativePlanBase(BaseModel):
    # content 是创意方案的结构化扩展区，主图布局、视频分镜和生成 prompt 都放在这里供人工编辑。
    type: CreativePlanType
    title: str = Field(min_length=1, max_length=255)
    content: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None
    status: CreativePlanStatus = CreativePlanStatus.DRAFT


class CreativePlanCreate(CreativePlanBase):
    pass


class CreativePlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: dict[str, Any] | None = None
    rationale: str | None = None
    status: CreativePlanStatus | None = None


class GeneratedAssetUpdate(BaseModel):
    # 素材更新只开放审核与复测相关字段，供应商原始元数据不由前端直接改写。
    url: str = Field(min_length=1)
    asset_type: str = Field(pattern="^(image|video)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    tags: list[str] | None = None
    note: str | None = None
    status: Literal["待评估", "通过", "弃用", "复测"] | None = None
    asset_version: int | None = Field(default=None, ge=1)
    usage_contexts: list[str] | None = None


class GeneratedAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    creative_plan_id: int
    generation_job_id: int | None = None
    asset_type: str
    title: str | None = None
    url: str
    model: str | None = None
    size: str | None = None
    duration: int | None = None
    status: str
    asset_version: int = 1
    usage_contexts: list[str] = Field(default_factory=list)
    rating: int | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None
    asset_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreativePlanRead(CreativePlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    agent_run_id: int | None = None
    created_at: datetime
    updated_at: datetime


class PerformanceRecordBase(BaseModel):
    # 经营记录允许按素材、实验、推广链接做归因；promotion_tracking_code 只用于入参解析，不出现在响应里。
    creative_plan_id: int | None = None
    ad_experiment_id: int | None = None
    promotion_link_id: int | None = None
    promotion_tracking_code: str | None = Field(default=None, max_length=64, exclude=True)
    generated_asset_id: int | None = None
    period_start: date
    period_end: date
    impressions: int | None = Field(default=None, ge=0)
    clicks: int | None = Field(default=None, ge=0)
    ctr: Decimal | None = Field(default=None, ge=0)
    conversions: int | None = Field(default=None, ge=0)
    conversion_rate: Decimal | None = Field(default=None, ge=0)
    spend: Decimal | None = Field(default=None, ge=0)
    revenue: Decimal | None = Field(default=None, ge=0)
    roi: Decimal | None = None
    notes: str | None = None


class PerformanceRecordCreate(PerformanceRecordBase):
    pass


class PerformanceRecordBulkCreate(BaseModel):
    records: list[PerformanceRecordCreate] = Field(min_length=1, max_length=100)


class PerformanceRecordRead(PerformanceRecordBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class ReviewReportBase(BaseModel):
    period_start: date
    period_end: date
    summary: str
    insights: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ReviewReportCreate(ReviewReportBase):
    pass


class ReviewReportUpdate(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    summary: str | None = None
    insights: list[str] | None = None
    next_actions: list[str] | None = None


class ReviewReportRead(ReviewReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class AdRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    source: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    confirmation_status: str
    confirmed_by_user_id: int | None = None
    confirmed_at: datetime | None = None
    confirmation_note: str | None = None
    created_at: datetime
    updated_at: datetime


class AdRecommendationConfirmationUpdate(BaseModel):
    # 投放建议确认只记录人工结论和备注，不携带任何广告平台执行参数。
    confirmation_status: Literal["confirmed", "rejected"]
    confirmation_note: str | None = Field(default=None, max_length=1000)


class AdExperimentBase(BaseModel):
    # 实验 schema 保存计划假设和预算建议，status 仍是人工维护的记录状态。
    generated_asset_id: int | None = None
    promotion_link_id: int | None = None
    name: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1)
    audience: str | None = None
    daily_budget: Decimal | None = Field(default=None, ge=0)
    status: str = Field(default="draft", max_length=50)
    success_metric: str | None = None
    hypothesis: str | None = None
    note: str | None = None


class AdExperimentCreate(AdExperimentBase):
    pass


class AdExperimentUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        max_length=50,
        pattern="^(draft|active|paused|completed|archived)$",
    )
    note: str | None = None


class AdExperimentRead(AdExperimentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class AdExperimentSummaryRead(BaseModel):
    ad_experiment_id: int
    name: str
    status: str
    generated_asset_id: int | None = None
    promotion_link_id: int | None = None
    daily_budget: Decimal | None = None
    record_count: int
    period_start: date | None = None
    period_end: date | None = None
    impressions: int
    clicks: int
    conversions: int
    spend: Decimal
    revenue: Decimal
    ctr: Decimal | None = None
    conversion_rate: Decimal | None = None
    roi: Decimal | None = None
    cpc: Decimal | None = None
    cpa: Decimal | None = None
    decision: str
    decision_reason: str


class AdExperimentDashboardRead(BaseModel):
    # 实验看板是只读汇总结果，用于复盘提示，不会驱动自动暂停或自动加预算。
    product_id: int
    total_experiments: int
    active_experiments: int
    measured_experiments: int
    total_spend: Decimal
    total_revenue: Decimal
    overall_roi: Decimal | None = None
    best_experiment: AdExperimentSummaryRead | None = None
    rows: list[AdExperimentSummaryRead] = Field(default_factory=list)


class PromotionLinkBase(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    link_type: str = Field(default="landing", max_length=50)
    scenario: str | None = Field(default=None, max_length=120)
    status: str = Field(default="active", max_length=50)
    tracking_code: str | None = Field(default=None, max_length=64)
    short_code: str | None = Field(default=None, max_length=32)
    tracking_url: str | None = Field(default=None, max_length=2048)
    click_count: int = Field(default=0, ge=0)
    note: str | None = None


class PromotionLinkCreate(PromotionLinkBase):
    pass


class PromotionLinkRead(PromotionLinkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    created_at: datetime
    updated_at: datetime


class ProductDiagnosisUpdate(BaseModel):
    source: str | None = Field(default=None, max_length=50)
    positioning: str | None = None
    price_band: str | None = None
    audience_insights: list[str] | None = None
    pain_points: list[str] | None = None
    selling_point_analysis: list[str] | None = None
    risks: list[str] | None = None
    recommendations: list[str] | None = None
    raw_output: dict[str, Any] | None = None


class ProductDiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    agent_run_id: int | None = None
    source: str
    positioning: str
    price_band: str
    audience_insights: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    selling_point_analysis: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    raw_output: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime












class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    creative_plan_id: int
    kind: GenerationJobKind
    status: GenerationJobStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    locked_at: datetime | None = None
    locked_by: str | None = None
    next_run_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    events: list["GenerationJobEventRead"] = Field(default_factory=list)


class GenerationJobEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    event_type: str
    status: GenerationJobStatus | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    worker_id: str | None = None
    created_at: datetime
    updated_at: datetime


class GenerationJobTimeoutSweepResult(BaseModel):
    timeout_minutes: int
    processed_count: int


class ProductDetail(ProductRead):
    skus: list[ProductSkuDetail] = Field(default_factory=list)
    platform_mappings: list[PlatformProductMappingRead] = Field(default_factory=list)
    competitors: list[CompetitorRead] = Field(default_factory=list)
    competitor_monitors: list[CompetitorMonitorRead] = Field(default_factory=list)
    creative_plans: list[CreativePlanRead] = Field(default_factory=list)
    performance_records: list[PerformanceRecordRead] = Field(default_factory=list)
    review_reports: list[ReviewReportRead] = Field(default_factory=list)
    ad_recommendations: list[AdRecommendationRead] = Field(default_factory=list)
    ad_experiments: list[AdExperimentRead] = Field(default_factory=list)
    promotion_links: list[PromotionLinkRead] = Field(default_factory=list)
    generated_assets: list[GeneratedAssetRead] = Field(default_factory=list)
    diagnoses: list[ProductDiagnosisRead] = Field(default_factory=list)
    generation_jobs: list[GenerationJobRead] = Field(default_factory=list)
    public_link_parse_tasks: list[PublicLinkParseTaskRead] = Field(default_factory=list)


class TextModelSettingsRead(BaseModel):
    base_url: str = ""
    api_key_masked: str = ""
    has_api_key: bool = False
    model: str = ""


class ImageModelSettingsRead(BaseModel):
    provider: str = ""
    base_url: str = ""
    api_key_masked: str = ""
    has_api_key: bool = False
    model: str = ""
    size: str = "1024*1024"
    workspace_id: str = ""
    poll_interval_seconds: int = 5
    poll_max_attempts: int = 24


class VideoModelSettingsRead(BaseModel):
    provider: str = ""
    base_url: str = ""
    api_key_masked: str = ""
    has_api_key: bool = False
    model: str = ""
    size: str = "1280*720"
    duration: int = 2
    workspace_id: str = ""
    poll_interval_seconds: int = 10
    poll_max_attempts: int = 36


class ModelSettingsRead(BaseModel):
    # 设置读取模型只返回脱敏值和 has_api_key，前端不会拿到明文供应商密钥。
    text: TextModelSettingsRead
    image: ImageModelSettingsRead
    video: VideoModelSettingsRead


class TextModelSettingsUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None


class ImageModelSettingsUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    size: str | None = None
    workspace_id: str | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=1)
    poll_max_attempts: int | None = Field(default=None, ge=1)


class VideoModelSettingsUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    size: str | None = None
    duration: int | None = Field(default=None, ge=1)
    workspace_id: str | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=1)
    poll_max_attempts: int | None = Field(default=None, ge=1)


class ModelSettingsUpdate(BaseModel):
    # 设置更新按 text/image/video 局部提交，未提交目标保持原供应商配置。
    text: TextModelSettingsUpdate | None = None
    image: ImageModelSettingsUpdate | None = None
    video: VideoModelSettingsUpdate | None = None


class ModelSettingsTestRequest(BaseModel):
    target: str = Field(pattern="^(text|image|video)$")


class ModelSettingsTestResult(BaseModel):
    target: str
    ok: bool
    message: str


class UserPermissionsRead(BaseModel):
    # 权限读模型是角色派生结果，帮助前端控制展示，但真正鉴权仍以后端依赖为准。
    can_read: bool
    can_edit: bool
    can_manage_users: bool
    can_confirm_ad_actions: bool


class UserBase(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    role: UserRole = UserRole.OPERATOR
    status: UserStatus = UserStatus.ACTIVE


class UserCreate(UserBase):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    status: UserStatus | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    permissions: UserPermissionsRead
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AuthTokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    status: WorkspaceStatus
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WorkspaceMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    user_id: int
    role: UserRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime


class WorkspaceAccessRead(BaseModel):
    workspace: WorkspaceRead
    membership: WorkspaceMembershipRead




class WorkflowDefinitionRead(BaseModel):
    key: str
    version: str
    title: str
    description: str
    agents: list[str] = Field(default_factory=list)
    required_context_any: list[str] = Field(default_factory=list)
    default_risk_level: AgentRiskLevel
























class DemoWorkspaceRead(BaseModel):
    store_id: int
    product_ids: list[int]
    sku_ids: list[int]
    message: str


def _bounded_agent_json(value: dict[str, Any], *, max_bytes: int = 64 * 1024) -> dict[str, Any]:
    """boundedAgentJSON，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    if len(encoded) > max_bytes:
        raise ValueError(f"Structured Agent payload exceeds {max_bytes} bytes")
    return value


class ProductImportRequest(BaseModel):
    # commit=false 是导入预览，commit=true 才写库，保留运营人工确认导入的边界。
    csv_text: str = Field(min_length=1)
    commit: bool = False


class ProductImportRowResult(BaseModel):
    row_number: int
    status: str
    errors: list[str] = Field(default_factory=list)
    product_id: int | None = None
    product_name: str | None = None
    store_name: str | None = None
    platform: Platform | None = None


class ProductImportResult(BaseModel):
    commit: bool
    total_rows: int
    valid_rows: int
    created_count: int
    error_count: int
    rows: list[ProductImportRowResult]


class SkuInventoryImportRequest(BaseModel):
    csv_text: str = Field(min_length=1)
    commit: bool = False


class SkuInventoryImportRowResult(BaseModel):
    row_number: int
    status: str
    errors: list[str] = Field(default_factory=list)
    product_id: int | None = None
    product_name: str | None = None
    sku_id: int | None = None
    sku_code: str | None = None
    sku_name: str | None = None


class SkuInventoryImportResult(BaseModel):
    commit: bool
    total_rows: int
    valid_rows: int
    created_count: int
    error_count: int
    rows: list[SkuInventoryImportRowResult]


class PerformanceImportRequest(BaseModel):
    # 经营数据导入会影响投放复盘和实验统计，因此同样采用预览/提交两阶段。
    csv_text: str = Field(min_length=1)
    commit: bool = False


class PerformanceImportRowResult(BaseModel):
    row_number: int
    status: str
    errors: list[str] = Field(default_factory=list)
    product_id: int | None = None
    product_name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    record_id: int | None = None


class PerformanceImportResult(BaseModel):
    commit: bool
    total_rows: int
    valid_rows: int
    created_count: int
    error_count: int
    rows: list[PerformanceImportRowResult]


from app.agents.contracts import AgentDraftOutput, ReviewResumePayload


class AgentRunReviewCreate(ReviewResumePayload):
    pass


class AgentRunEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    agent_name: str | None = None
    operation_name: str | None = None
    status: str | None = None
    message: str | None = None
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    output_snapshot: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reviewed_by_user_id: int
    decision: AgentReviewDecision
    edited_output: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: str
    workspace_id: int | None = None
    task_id: int | None = None
    product_id: int | None = None
    requested_by_user_id: int
    workflow_key: str
    workflow_version: str
    attempt: int = 1
    queue_name: str | None = None
    status: AgentRunStatus
    current_agent: str | None = None
    revision_count: int
    max_revisions: int
    budget: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    version_manifest: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    draft_output: dict[str, Any] = Field(default_factory=dict)
    quality_report: dict[str, Any] = Field(default_factory=dict)
    final_output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    timeout_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    events: list[AgentRunEventRead] = Field(default_factory=list)
    reviews: list[AgentRunReviewRead] = Field(default_factory=list)


class AgentRunDraftRead(BaseModel):
    draft_output: AgentDraftOutput


class AgentDefinitionRead(BaseModel):
    key: str
    version: str
    description: str
    tools: list[str] = Field(default_factory=list)


class ToolDefinitionRead(BaseModel):
    key: str
    risk_level: AgentRiskLevel
    description: str
    # 是否有可执行适配：前端据此区分「已可用」与「仅登记未接入」
    executable: bool


class AgentCatalogRead(BaseModel):
    coordinator: AgentDefinitionRead
    agents: list[AgentDefinitionRead]
    tools: list[ToolDefinitionRead] = Field(default_factory=list)
    workflows: list[WorkflowDefinitionRead]


class AgentConversationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    context_scope: dict[str, Any] = Field(default_factory=dict)


class AgentConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by_user_id: int
    title: str
    status: str
    context_scope: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AgentConversationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    structured_content: dict[str, Any] = Field(default_factory=dict)


class AgentConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    workspace_id: int
    author_user_id: int | None = None
    role: str
    content: str
    structured_content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AgentTaskCreate(BaseModel):
    workflow_key: str | None = Field(default=None, max_length=100)
    intent: str | None = Field(default=None, max_length=4000)
    title: str | None = Field(default=None, max_length=255)
    conversation_id: int | None = Field(default=None, gt=0)
    context_scope: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context_scope", "input_payload")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        """校验载荷size，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
        return _bounded_agent_json(value)

    @model_validator(mode="after")
    def validate_workflow_or_intent(self) -> "AgentTaskCreate":
        """校验工作流orintent，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
        if not self.workflow_key and not (self.intent and self.intent.strip()):
            raise ValueError("workflow_key or intent is required")
        return self


class AgentTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    conversation_id: int | None = None
    requested_by_user_id: int
    workflow_key: str
    workflow_version: str
    title: str
    intent: str | None = None
    status: AgentTaskStatus
    risk_level: AgentRiskLevel
    context_scope: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    version_manifest: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    cancelled_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentApprovalDecisionCreate(BaseModel):
    decision: Literal["approve", "edit_and_approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)
    edited_output: dict[str, Any] | None = None
    decision_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("decision_payload", "edited_output")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """校验载荷size，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
        if value is None:
            return None
        return _bounded_agent_json(value, max_bytes=256 * 1024)

    @model_validator(mode="after")
    def validate_edited_output(self) -> "AgentApprovalDecisionCreate":
        """「修改后通过」必须带完整结果，其余决策不得携带（DesignSpec §6 API-07）。"""
        if self.decision == "edit_and_approve":
            if not self.edited_output:
                raise ValueError("edit_and_approve requires a non-empty edited_output")
        elif self.edited_output is not None:
            raise ValueError("edited_output is only allowed for edit_and_approve")
        return self


class AgentApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    task_id: int
    run_id: int
    requested_by_user_id: int
    decided_by_user_id: int | None = None
    action_key: str
    risk_level: AgentRiskLevel
    status: AgentApprovalStatus
    request_payload: dict[str, Any] = Field(default_factory=dict)
    decision_payload: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None
    expires_at: datetime | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentMemoryCreate(BaseModel):
    scope_type: Literal["workspace", "store", "product", "user"]
    scope_id: str | None = Field(default=None, max_length=120)
    memory_key: str = Field(min_length=1, max_length=120)
    schema_version: str = Field(default="1.0", min_length=1, max_length=30)
    content: dict[str, Any]
    source_type: Literal["user_confirmed", "approved_task", "import"]
    source_reference: dict[str, Any] = Field(default_factory=dict)
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("content", "source_reference")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        """校验载荷size，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
        return _bounded_agent_json(value)

    @model_validator(mode="after")
    def validate_effective_window(self) -> "AgentMemoryCreate":
        """校验生效window，把配置或输入约束收敛为下游可直接使用的稳定数据。"""
        # 先处理输入与边界条件，再执行核心逻辑，最后返回稳定且可验证的结果。
        if self.expires_at is not None and self.effective_at is not None:
            if self.expires_at <= self.effective_at:
                raise ValueError("expires_at must be later than effective_at")
        return self


class AgentMemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_by_user_id: int
    scope_type: str
    scope_id: str | None = None
    memory_key: str
    schema_version: str
    content: dict[str, Any]
    source_type: str
    source_reference: dict[str, Any] = Field(default_factory=dict)
    status: AgentMemoryStatus
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
