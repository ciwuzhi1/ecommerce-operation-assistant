from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Platform(StrEnum):
    # 平台枚举保持多平台扩展，业务代码不能把商品、店铺或 SKU 概念绑定到单一平台。
    DOUYIN = "douyin"
    TAOBAO = "taobao"
    TMALL = "tmall"
    PINUODUODU = "pinduoduo"
    JD = "jd"
    TIKTOK_SHOP = "tiktok_shop"
    AMAZON = "amazon"
    OTHER = "other"


class CreativePlanType(StrEnum):
    MAIN_IMAGE = "main_image"
    VIDEO_SCRIPT = "video_script"
    TITLE = "title"
    DETAIL = "detail"


class CreativePlanStatus(StrEnum):
    # 创意方案状态只表达运营筛选结果，是否真正投放仍由人工确认和实验记录决定。
    DRAFT = "draft"
    SELECTED = "selected"
    ARCHIVED = "archived"


class GenerationJobKind(StrEnum):
    MAIN_IMAGE_ASSET = "main_image_asset"
    VIDEO_ASSET = "video_asset"


class GenerationJobStatus(StrEnum):
    # 生成任务状态覆盖队列生命周期，便于前端展示等待、执行、失败、取消和重试边界。
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    RESUME_QUEUED = "resume_queued"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentReviewDecision(StrEnum):
    APPROVE = "approve"
    EDIT_AND_APPROVE = "edit_and_approve"
    REJECT = "reject"


class WorkspaceStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AgentConversationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgentTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AgentRiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class AgentMemoryStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OutboxEventStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


class ModelTarget(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class UserRole(StrEnum):
    OWNER = "owner"
    OPERATOR = "operator"
    VIEWER = "viewer"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class StoreStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class PlatformAccountStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"


class ProductSkuStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class InventoryMovementType(StrEnum):
    # 库存动作区分真实数量变化和锁定占用，避免订单预占与实际出库被重复扣减。
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    ADJUSTMENT = "adjustment"
    LOCK = "lock"
    RELEASE = "release"


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """enumvalues，集中封装当前模块的输入校验、核心处理和返回值约定。"""
    return [item.value for item in enum_class]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    # Product 是单品运营闭环的核心聚合根，关联诊断、素材、投放、复盘和库存 SKU。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        default=Platform.DOUYIN,
    )
    category: Mapped[str | None] = mapped_column(String(120))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    target_audience: Mapped[str | None] = mapped_column(Text)
    selling_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    product_url: Mapped[str | None] = mapped_column(String(1024))
    # external_product_id/platform_status 保存平台侧标识和状态，便于多平台对账，不承载平台密钥。
    external_product_id: Mapped[str | None] = mapped_column(String(120), index=True)
    platform_status: Mapped[str | None] = mapped_column(String(50))
    images: Mapped[list[str]] = mapped_column(JSON, default=list)

    store: Mapped["Store | None"] = relationship(back_populates="products")
    skus: Mapped[list["ProductSku"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductSku.created_at.desc()",
    )
    platform_mappings: Mapped[list["PlatformProductMapping"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    competitor_monitors: Mapped[list["CompetitorMonitor"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="CompetitorMonitor.created_at.desc()",
    )
    creative_plans: Mapped[list["CreativePlan"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    performance_records: Mapped[list["PerformanceRecord"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    review_reports: Mapped[list["ReviewReport"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    ad_recommendations: Mapped[list["AdRecommendation"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="AdRecommendation.created_at.desc()",
    )
    ad_experiments: Mapped[list["AdExperiment"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="AdExperiment.created_at.desc()",
    )
    promotion_links: Mapped[list["PromotionLink"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PromotionLink.created_at.desc()",
    )
    promotion_link_clicks: Mapped[list["PromotionLinkClick"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )
    generated_assets: Mapped[list["GeneratedAsset"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="GeneratedAsset.created_at.desc()",
    )
    diagnoses: Mapped[list["ProductDiagnosis"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductDiagnosis.created_at.desc()",
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="GenerationJob.created_at.desc()",
    )
    public_link_parse_tasks: Mapped[list["PublicLinkParseTask"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PublicLinkParseTask.created_at.desc()",
    )
    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="AgentRun.created_at.desc()",
    )


class ModelProviderSetting(TimestampMixin, Base):
    __tablename__ = "model_provider_settings"

    # 模型配置按 text/image/video 分目标保存，允许后台替换供应商而不改代码或前端硬编码 key。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    target: Mapped[ModelTarget] = mapped_column(
        Enum(ModelTarget, values_callable=enum_values),
        nullable=False,
        unique=True,
        index=True,
    )
    provider: Mapped[str | None] = mapped_column(String(50))
    base_url: Mapped[str | None] = mapped_column(String(1024))
    api_key: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(50))
    duration: Mapped[int | None]
    workspace_id: Mapped[str | None] = mapped_column(String(120))
    poll_interval_seconds: Mapped[int | None]
    poll_max_attempts: Mapped[int | None]


class User(TimestampMixin, Base):
    __tablename__ = "users"

    # 用户模型只保存角色和密码摘要；具体权限由服务层从角色派生，避免权限布尔值散落写库。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=enum_values),
        default=UserRole.OPERATOR,
        nullable=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, values_callable=enum_values),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    # Workspace 是业务数据、Agent 上下文、记忆和审计的强租户边界。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, values_callable=enum_values),
        default=WorkspaceStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=enum_values),
        default=UserRole.OPERATOR,
        nullable=False,
        index=True,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, values_callable=enum_values),
        default=MembershipStatus.ACTIVE,
        nullable=False,
        index=True,
    )


class Store(TimestampMixin, Base):
    __tablename__ = "stores"

    # Store 表示经营店铺维度，V1 扩展到多平台账号、SKU 和库存时以此做聚合入口。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    status: Mapped[StoreStatus] = mapped_column(
        Enum(StoreStatus, values_callable=enum_values),
        default=StoreStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    external_store_id: Mapped[str | None] = mapped_column(String(120), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list[Product]] = relationship(
        back_populates="store",
        order_by="Product.created_at.desc()",
    )
    platform_accounts: Mapped[list["PlatformAccount"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
    )


class PlatformAccount(TimestampMixin, Base):
    __tablename__ = "platform_accounts"

    # 平台账号只记录授权状态和非敏感 metadata，不保存平台密码、Cookie 或明文 access token。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[PlatformAccountStatus] = mapped_column(
        Enum(PlatformAccountStatus, values_callable=enum_values),
        default=PlatformAccountStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    auth_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text)

    store: Mapped[Store] = relationship(back_populates="platform_accounts")


class ProductSku(TimestampMixin, Base):
    __tablename__ = "product_skus"

    # SKU 是库存和平台映射的最小规格单元，同一商品下可对应多个平台 SKU。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    sku_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[ProductSkuStatus] = mapped_column(
        Enum(ProductSkuStatus, values_callable=enum_values),
        default=ProductSkuStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    product: Mapped[Product] = relationship(back_populates="skus")
    inventory_item: Mapped["InventoryItem | None"] = relationship(
        back_populates="sku",
        cascade="all, delete-orphan",
    )
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="sku",
        order_by="InventoryMovement.created_at.desc()",
    )
    platform_mappings: Mapped[list["PlatformProductMapping"]] = relationship(
        back_populates="sku",
        cascade="all, delete-orphan",
    )


class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"

    # 库存快照只保存当前总量、锁定量和预警线；所有变化原因必须追溯到 InventoryMovement。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id"), nullable=False, unique=True, index=True)
    quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_quantity: Mapped[int] = mapped_column(default=0, nullable=False)
    warning_threshold: Mapped[int] = mapped_column(default=0, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))

    sku: Mapped[ProductSku] = relationship(back_populates="inventory_item")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="inventory_item",
        cascade="all, delete-orphan",
        order_by="InventoryMovement.created_at.desc()",
    )


class InventoryMovement(TimestampMixin, Base):
    __tablename__ = "inventory_movements"

    # 库存流水保留变更前后值，支持人工盘点、导入修正和后续轻量 ERP 对账。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), nullable=False, index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("product_skus.id"), nullable=False, index=True)
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(InventoryMovementType, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    quantity_delta: Mapped[int] = mapped_column(nullable=False)
    locked_delta: Mapped[int] = mapped_column(default=0, nullable=False)
    before_quantity: Mapped[int] = mapped_column(nullable=False)
    after_quantity: Mapped[int] = mapped_column(nullable=False)
    before_locked_quantity: Mapped[int] = mapped_column(nullable=False)
    after_locked_quantity: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(120))
    operator_name: Mapped[str | None] = mapped_column(String(120))

    inventory_item: Mapped[InventoryItem] = relationship(back_populates="movements")
    sku: Mapped[ProductSku] = relationship(back_populates="inventory_movements")


class PlatformProductMapping(TimestampMixin, Base):
    __tablename__ = "platform_product_mappings"

    # 平台映射把内部商品/SKU 与外部平台 ID 解耦，方便淘宝、京东、抖音等平台独立扩展。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id"), index=True)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    external_product_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_sku_id: Mapped[str | None] = mapped_column(String(120), index=True)
    listing_url: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str | None] = mapped_column(String(50))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    store: Mapped[Store | None] = relationship()
    product: Mapped[Product] = relationship(back_populates="platform_mappings")
    sku: Mapped[ProductSku | None] = relationship(back_populates="platform_mappings")


class Competitor(TimestampMixin, Base):
    __tablename__ = "competitors"

    # 竞品资料来自手工录入、表格或有限公开链接解析，不代表平台后台完整经营数据。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        default=Platform.DOUYIN,
    )
    url: Mapped[str | None] = mapped_column(String(1024))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sales_hint: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    main_image: Mapped[str | None] = mapped_column(String(1024))
    selling_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)

    product: Mapped[Product] = relationship(back_populates="competitors")
    monitors: Mapped[list["CompetitorMonitor"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )


class CompetitorMonitor(TimestampMixin, Base):
    __tablename__ = "competitor_monitors"

    # 竞品监控是轻量定期复查入口，只保存任务节奏，不实现大规模爬虫。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(default=1, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    note: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="competitor_monitors")
    competitor: Mapped[Competitor] = relationship(back_populates="monitors")
    snapshots: Mapped[list["CompetitorMonitorSnapshot"]] = relationship(
        back_populates="monitor",
        cascade="all, delete-orphan",
        foreign_keys="CompetitorMonitorSnapshot.monitor_id",
        order_by="CompetitorMonitorSnapshot.checked_at.desc()",
    )
class CompetitorMonitorSnapshot(Base):
    __tablename__ = "competitor_monitor_snapshots"

    # 快照保留每次公开页面解析结果，失败也入库，便于判断是页面变化还是平台限制。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(ForeignKey("competitor_monitors.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id"), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="succeeded", nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sales_hint: Mapped[str | None] = mapped_column(String(255))
    main_image: Mapped[str | None] = mapped_column(String(1024))
    selling_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    changes: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    monitor: Mapped[CompetitorMonitor] = relationship(
        back_populates="snapshots",
        foreign_keys=[monitor_id],
    )
    product: Mapped[Product] = relationship()
    competitor: Mapped[Competitor] = relationship()


class PublicLinkParseTask(TimestampMixin, Base):
    __tablename__ = "public_link_parse_tasks"

    # 公开链接解析任务记录异步状态和重试次数，边界是用户提交的 http/https 商品页。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), default="competitor_import", nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform, values_callable=enum_values),
        default=Platform.DOUYIN,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=3, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="public_link_parse_tasks")


class CreativePlan(TimestampMixin, Base):
    __tablename__ = "creative_plans"

    # 创意方案保存结构化 content，主图、视频脚本和后续标题/详情方案都可复用同一扩展字段。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        index=True,
    )
    type: Mapped[CreativePlanType] = mapped_column(
        Enum(CreativePlanType, values_callable=enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CreativePlanStatus] = mapped_column(
        Enum(CreativePlanStatus, values_callable=enum_values),
        default=CreativePlanStatus.DRAFT,
    )

    product: Mapped[Product] = relationship(back_populates="creative_plans")
    agent_run: Mapped["AgentRun | None"] = relationship(back_populates="creative_plans")
    performance_records: Mapped[list["PerformanceRecord"]] = relationship(
        back_populates="creative_plan",
    )
    generation_jobs: Mapped[list["GenerationJob"]] = relationship(
        back_populates="creative_plan",
    )
    generated_assets: Mapped[list["GeneratedAsset"]] = relationship(
        back_populates="creative_plan",
    )


class PerformanceRecord(TimestampMixin, Base):
    __tablename__ = "performance_records"

    # 经营数据由手工录入或表格导入回填，可关联素材、推广链接和实验以支持复盘归因。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    creative_plan_id: Mapped[int | None] = mapped_column(ForeignKey("creative_plans.id"))
    ad_experiment_id: Mapped[int | None] = mapped_column(ForeignKey("ad_experiments.id"))
    promotion_link_id: Mapped[int | None] = mapped_column(ForeignKey("promotion_links.id"))
    generated_asset_id: Mapped[int | None] = mapped_column(ForeignKey("generated_assets.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    impressions: Mapped[int | None]
    clicks: Mapped[int | None]
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    conversions: Mapped[int | None]
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    spend: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    roi: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    notes: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="performance_records")
    creative_plan: Mapped[CreativePlan | None] = relationship(back_populates="performance_records")
    ad_experiment: Mapped["AdExperiment | None"] = relationship(back_populates="performance_records")
    promotion_link: Mapped["PromotionLink | None"] = relationship(back_populates="performance_records")
    generated_asset: Mapped["GeneratedAsset | None"] = relationship(back_populates="performance_records")


class ReviewReport(TimestampMixin, Base):
    __tablename__ = "review_reports"

    # 复盘报告保存结构化洞察和下一步动作，便于运营编辑，而不是只存一段不可解析文本。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    insights: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_actions: Mapped[list[str]] = mapped_column(JSON, default=list)

    product: Mapped[Product] = relationship(back_populates="review_reports")


class AdRecommendation(TimestampMixin, Base):
    __tablename__ = "ad_recommendations"

    # 投放建议只记录建议内容和人工确认结果，不对接广告平台执行预算或扣费动作。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), default="rules", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    confirmation_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_note: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="ad_recommendations")


class AdExperiment(TimestampMixin, Base):
    __tablename__ = "ad_experiments"

    # 投放实验是计划和数据回填容器，status 表示运营人工维护的实验阶段。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    generated_asset_id: Mapped[int | None] = mapped_column(ForeignKey("generated_assets.id"))
    promotion_link_id: Mapped[int | None] = mapped_column(ForeignKey("promotion_links.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str | None] = mapped_column(Text)
    daily_budget: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    success_metric: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="ad_experiments")
    generated_asset: Mapped["GeneratedAsset | None"] = relationship(back_populates="ad_experiments")
    promotion_link: Mapped["PromotionLink | None"] = relationship(back_populates="ad_experiments")
    performance_records: Mapped[list[PerformanceRecord]] = relationship(
        back_populates="ad_experiment",
    )


class PromotionLink(TimestampMixin, Base):
    __tablename__ = "promotion_links"

    # 推广链接用于承接页和归因参数管理，短链点击只计数，不触发投放或库存动作。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    link_type: Mapped[str] = mapped_column(String(50), default="landing", nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    tracking_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    short_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    tracking_url: Mapped[str | None] = mapped_column(String(2048))
    click_count: Mapped[int] = mapped_column(default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="promotion_links")
    performance_records: Mapped[list[PerformanceRecord]] = relationship(
        back_populates="promotion_link",
    )
    ad_experiments: Mapped[list[AdExperiment]] = relationship(
        back_populates="promotion_link",
    )
    clicks: Mapped[list["PromotionLinkClick"]] = relationship(
        back_populates="promotion_link",
        cascade="all, delete-orphan",
    )


class PromotionLinkClick(Base):
    __tablename__ = "promotion_link_clicks"

    # 点击日志只保留归因所需的 referer/user-agent 摘要，避免采集个人身份信息。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    promotion_link_id: Mapped[int] = mapped_column(
        ForeignKey("promotion_links.id"),
        nullable=False,
        index=True,
    )
    tracking_code: Mapped[str | None] = mapped_column(String(64), index=True)
    referer: Mapped[str | None] = mapped_column(String(2048))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    product: Mapped[Product] = relationship(back_populates="promotion_link_clicks")
    promotion_link: Mapped[PromotionLink] = relationship(back_populates="clicks")


class GeneratedAsset(TimestampMixin, Base):
    __tablename__ = "generated_assets"

    # 生成素材统一进入素材库，status/rating/tags 支持人工审核、复测和投放归因。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    creative_plan_id: Mapped[int] = mapped_column(
        ForeignKey("creative_plans.id"),
        nullable=False,
        index=True,
    )
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"))
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(50))
    duration: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(50), default="待评估", nullable=False)
    asset_version: Mapped[int] = mapped_column(default=1, nullable=False)
    usage_contexts: Mapped[list[str]] = mapped_column(JSON, default=list)
    rating: Mapped[int | None]
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    product: Mapped[Product] = relationship(back_populates="generated_assets")
    creative_plan: Mapped[CreativePlan] = relationship(back_populates="generated_assets")
    generation_job: Mapped["GenerationJob | None"] = relationship(back_populates="generated_asset")
    performance_records: Mapped[list[PerformanceRecord]] = relationship(
        back_populates="generated_asset",
    )
    ad_experiments: Mapped[list[AdExperiment]] = relationship(
        back_populates="generated_asset",
    )


class ProductDiagnosis(TimestampMixin, Base):
    __tablename__ = "product_diagnoses"

    # 商品诊断把 AI/规则输出拆成可编辑字段，raw_output 只保存安全摘要和结构化来源。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    agent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), default="rules", nullable=False)
    positioning: Mapped[str] = mapped_column(Text, nullable=False)
    price_band: Mapped[str] = mapped_column(String(255), nullable=False)
    audience_insights: Mapped[list[str]] = mapped_column(JSON, default=list)
    pain_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    selling_point_analysis: Mapped[list[str]] = mapped_column(JSON, default=list)
    risks: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommendations: Mapped[list[str]] = mapped_column(JSON, default=list)
    raw_output: Mapped[dict] = mapped_column(JSON, default=dict)

    product: Mapped[Product] = relationship(back_populates="diagnoses")
    agent_run: Mapped["AgentRun | None"] = relationship(back_populates="diagnoses")


class AgentConversation(TimestampMixin, Base):
    __tablename__ = "agent_conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AgentConversationStatus] = mapped_column(
        Enum(AgentConversationStatus, values_callable=enum_values),
        default=AgentConversationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    context_scope: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentConversationMessage(TimestampMixin, Base):
    __tablename__ = "agent_conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("agent_conversations.id"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentTask(TimestampMixin, Base):
    __tablename__ = "agent_tasks"

    # Task 表达用户业务目标；Run 只是某个版本和某次重试的技术执行实例。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_conversations.id"),
        index=True,
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    workflow_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    intent: Mapped[str | None] = mapped_column(Text)
    status: Mapped[AgentTaskStatus] = mapped_column(
        Enum(AgentTaskStatus, values_callable=enum_values),
        default=AgentTaskStatus.QUEUED,
        nullable=False,
        index=True,
    )
    risk_level: Mapped[AgentRiskLevel] = mapped_column(
        Enum(AgentRiskLevel, values_callable=enum_values),
        default=AgentRiskLevel.R1,
        nullable=False,
        index=True,
    )
    context_scope: Mapped[dict] = mapped_column(JSON, default=dict)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    version_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    # MySQL 保存用户可见的运行事实；LangGraph checkpoint 只负责技术恢复，不能替代业务审计。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("agent_tasks.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    workflow_key: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    queue_name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, values_callable=enum_values),
        default=AgentRunStatus.QUEUED,
        nullable=False,
        index=True,
    )
    current_agent: Mapped[str | None] = mapped_column(String(100))
    revision_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_revisions: Mapped[int] = mapped_column(default=1, nullable=False)
    budget: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    version_manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_output: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict)
    final_output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    lease_owner: Mapped[str | None] = mapped_column(String(120), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product | None] = relationship(back_populates="agent_runs")
    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_user_id])
    events: Mapped[list["AgentRunEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunEvent.id.asc()",
    )
    reviews: Mapped[list["AgentRunReview"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunReview.id.asc()",
    )
    operations: Mapped[list["AgentRunOperation"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunOperation.id.asc()",
    )
    diagnoses: Mapped[list[ProductDiagnosis]] = relationship(back_populates="agent_run")
    creative_plans: Mapped[list[CreativePlan]] = relationship(back_populates="agent_run")


class AgentRunEvent(TimestampMixin, Base):
    __tablename__ = "agent_run_events"

    # 事件同时服务用户进度、故障定位和评测轨迹，内容必须先脱敏再写入。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    agent_name: Mapped[str | None] = mapped_column(String(100), index=True)
    operation_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str | None] = mapped_column(String(30), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    output_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    span_id: Mapped[str | None] = mapped_column(String(32))

    run: Mapped[AgentRun] = relationship(back_populates="events")


class AgentRunReview(TimestampMixin, Base):
    __tablename__ = "agent_run_reviews"

    # 一个运行只接受一次最终审核决定，避免重复恢复同一 checkpoint 产生冲突。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    reviewed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    decision: Mapped[AgentReviewDecision] = mapped_column(
        Enum(AgentReviewDecision, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    edited_output: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text)

    run: Mapped[AgentRun] = relationship(back_populates="reviews")
    reviewed_by: Mapped[User] = relationship(foreign_keys=[reviewed_by_user_id])


class AgentRunOperation(TimestampMixin, Base):
    __tablename__ = "agent_run_operations"
    __table_args__ = (
        UniqueConstraint("run_id", "operation_key", name="uq_agent_run_operation"),
    )

    # Celery 至少一次投递时，副作用节点先声明幂等操作，再在同一 MySQL 事务内写入成果。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    operation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[AgentRun] = relationship(back_populates="operations")


class AgentApproval(TimestampMixin, Base):
    __tablename__ = "agent_approvals"
    __table_args__ = (
        UniqueConstraint("run_id", "action_key", name="uq_agent_approval_action"),
    )

    # 审批记录是真实权限边界，不能只依赖 Prompt 或前端确认框。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("agent_tasks.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), nullable=False, index=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    risk_level: Mapped[AgentRiskLevel] = mapped_column(
        Enum(AgentRiskLevel, values_callable=enum_values),
        nullable=False,
        index=True,
    )
    status: Mapped[AgentApprovalStatus] = mapped_column(
        Enum(AgentApprovalStatus, values_callable=enum_values),
        default=AgentApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentMemory(TimestampMixin, Base):
    __tablename__ = "agent_memories"

    # 长期记忆只保存用户明确确认的结构化事实，并保留来源、版本和撤销状态。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    scope_id: Mapped[str | None] = mapped_column(String(120), index=True)
    memory_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_reference: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[AgentMemoryStatus] = mapped_column(
        Enum(AgentMemoryStatus, values_callable=enum_values),
        default=AgentMemoryStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEvent(TimestampMixin, Base):
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    status: Mapped[OutboxEventStatus] = mapped_column(
        Enum(OutboxEventStatus, values_callable=enum_values),
        default=OutboxEventStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class GenerationJob(TimestampMixin, Base):
    __tablename__ = "generation_jobs"

    # 生成任务连接创意方案和外部供应商调用，锁字段用于避免多 worker 重复执行同一任务。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    creative_plan_id: Mapped[int] = mapped_column(
        ForeignKey("creative_plans.id"),
        nullable=False,
        index=True,
    )
    kind: Mapped[GenerationJobKind] = mapped_column(
        Enum(GenerationJobKind, values_callable=enum_values),
        nullable=False,
    )
    status: Mapped[GenerationJobStatus] = mapped_column(
        Enum(GenerationJobStatus, values_callable=enum_values),
        default=GenerationJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=3, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="generation_jobs")
    creative_plan: Mapped[CreativePlan] = relationship(back_populates="generation_jobs")
    generated_asset: Mapped[GeneratedAsset | None] = relationship(
        back_populates="generation_job",
    )
    events: Mapped[list["GenerationJobEvent"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="GenerationJobEvent.created_at.desc()",
    )


class GenerationJobEvent(TimestampMixin, Base):
    __tablename__ = "generation_job_events"

    # 任务事件只记录生命周期状态和安全 payload，不保存供应商密钥或完整外部响应。
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("generation_jobs.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[GenerationJobStatus | None] = mapped_column(
        Enum(GenerationJobStatus, values_callable=enum_values),
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    worker_id: Mapped[str | None] = mapped_column(String(120))

    job: Mapped[GenerationJob] = relationship(back_populates="events")
