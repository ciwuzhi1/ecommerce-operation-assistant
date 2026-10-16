from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.routes.auth import require_ad_confirmation_permission, require_edit_permission, require_view_permission
from app.db.session import get_db
from app.models import (
    AdExperiment,
    AdRecommendation,
    Competitor,
    CompetitorMonitor,
    CompetitorMonitorSnapshot,
    CreativePlan,
    CreativePlanType,
    GenerationJob,
    GenerationJobKind,
    GenerationJobStatus,
    GeneratedAsset,
    InventoryMovement,
    PerformanceRecord,
    PlatformProductMapping,
    Product,
    ProductDiagnosis,
    ProductSku,
    PublicLinkParseTask,
    PromotionLink,
    ReviewReport,
    Store,
    User,
)
from app.schemas import (
    AdExperimentCreate,
    AdExperimentDashboardRead,
    AdExperimentRead,
    AdExperimentUpdate,
    AdRecommendationConfirmationUpdate,
    AdRecommendationRead,
    CompetitorCreate,
    CompetitorMonitorCreate,
    CompetitorMonitorRead,
    CompetitorMonitorSnapshotRead,
    CompetitorRead,
    CompetitorUrlImport,
    CreativePlanCreate,
    CreativePlanRead,
    CreativePlanUpdate,
    GeneratedAssetUpdate,
    GenerationJobRead,
    InventoryMovementCreate,
    InventoryMovementRead,
    PerformanceRecordBulkCreate,
    PerformanceRecordCreate,
    PerformanceRecordRead,
    PlatformProductMappingCreate,
    PlatformProductMappingRead,
    PromotionLinkCreate,
    PromotionLinkRead,
    ProductCreate,
    ProductDiagnosisRead,
    ProductDiagnosisUpdate,
    ProductDetail,
    ProductRead,
    ProductSkuCreate,
    ProductSkuDetail,
    ProductSkuUpdate,
    ProductUpdate,
    PublicLinkParseTaskRead,
    ReviewReportCreate,
    ReviewReportRead,
    ReviewReportUpdate,
)
from app.services.ad_experiment_stats import build_ad_experiment_dashboard
from app.services.competitor_monitoring import next_check_time, run_competitor_monitor
from app.services.generation_jobs import (
    cancel_generation_job_record,
    dispatch_generation_job,
    enqueue_generation_job,
    retry_generation_job_record,
)
from app.services.generated_assets import sync_generated_assets_from_creative_plans
from app.services.inventory import InventoryAdjustmentError, adjust_inventory, create_inventory_item_for_sku
from app.services.link_extraction import LinkExtractionError, fetch_competitor_profile
from app.services.promotion_links import (
    build_promotion_link_payloads,
    enrich_tracking_fields,
    make_short_code,
)
from app.services.public_link_parse_tasks import enqueue_competitor_import_task, run_public_link_parse_task
from app.services.ad_experiments import build_ad_experiment_payload
from app.services.ad_recommendations import generate_ad_recommendation as build_ad_recommendation
from app.services.creative_plans import generate_main_image_plans, generate_video_script_plans
from app.services.diagnosis import generate_product_diagnosis as build_product_diagnosis
from app.services.review import enrich_performance_metrics, generate_review as build_review_report

router = APIRouter(prefix="/products", tags=["products"])

SessionDep = Annotated[Session, Depends(get_db)]


def get_product_or_404(db: Session, product_id: int) -> Product:
    """处理获取商品or404接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    product = db.get(Product, product_id)
    workspace_id = db.info.get("workspace_id")
    if product is None or (workspace_id is not None and product.workspace_id != workspace_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def ensure_creative_plan_belongs_to_product(
    db: Session,
    product_id: int,
    creative_plan_id: int | None,
) -> None:
    """处理确保创意方案belongsto商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if creative_plan_id is None:
        return

    creative_plan = db.get(CreativePlan, creative_plan_id)
    if creative_plan is None or creative_plan.product_id != product_id:
        # 交叉归属校验防止把其他商品的素材、链接或实验数据误绑定进当前单品复盘。
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Creative plan {creative_plan_id} does not belong to this product",
        )


def ensure_promotion_link_belongs_to_product(
    db: Session,
    product_id: int,
    promotion_link_id: int | None,
) -> None:
    """处理确保推广链接belongsto商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if promotion_link_id is None:
        return

    promotion_link = db.get(PromotionLink, promotion_link_id)
    if promotion_link is None or promotion_link.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Promotion link {promotion_link_id} does not belong to this product",
        )


def ensure_competitor_belongs_to_product(
    db: Session,
    product_id: int,
    competitor_id: int,
) -> Competitor:
    """处理确保竞品belongsto商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competitor not found",
        )
    return competitor


def ensure_ad_experiment_belongs_to_product(
    db: Session,
    product_id: int,
    ad_experiment_id: int | None,
) -> None:
    """处理确保投放实验belongsto商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if ad_experiment_id is None:
        return

    ad_experiment = db.get(AdExperiment, ad_experiment_id)
    if ad_experiment is None or ad_experiment.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ad experiment {ad_experiment_id} does not belong to this product",
        )


def ensure_generated_asset_belongs_to_product(
    db: Session,
    product_id: int,
    generated_asset_id: int | None,
) -> None:
    """处理确保生成素材belongsto商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if generated_asset_id is None:
        return

    generated_asset = db.get(GeneratedAsset, generated_asset_id)
    if generated_asset is None or generated_asset.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generated asset {generated_asset_id} does not belong to this product",
        )


def ensure_store_exists(db: Session, store_id: int | None) -> None:
    """处理确保店铺exists接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if store_id is None:
        return
    store = db.get(Store, store_id)
    workspace_id = db.info.get("workspace_id")
    if store is None or (workspace_id is not None and store.workspace_id != workspace_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Store not found")


def get_sku_or_404(db: Session, product_id: int, sku_id: int) -> ProductSku:
    """处理获取SKUor404接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    sku = db.get(ProductSku, sku_id)
    if sku is None or sku.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found")
    return sku


def resolve_promotion_tracking_code(
    db: Session,
    product_id: int,
    promotion_tracking_code: str | None,
) -> int | None:
    """处理解析推广追踪code接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if not promotion_tracking_code:
        return None

    promotion_link = db.scalars(
        select(PromotionLink).where(
            PromotionLink.product_id == product_id,
            PromotionLink.tracking_code == promotion_tracking_code,
        )
    ).first()
    if promotion_link is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Promotion tracking code {promotion_tracking_code} does not belong to this product",
        )
    return promotion_link.id


@router.get("", response_model=list[ProductRead])
def list_products(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Product]:
    """处理查询products接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = select(Product)
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Product.workspace_id == workspace_id)
    statement = statement.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Product:
    """处理创建商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    ensure_store_exists(db, payload.store_id)
    product = Product(
        workspace_id=db.info.get("workspace_id"),
        **payload.model_dump(mode="json"),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
) -> Product:
    """处理获取商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.competitors),
            selectinload(Product.competitor_monitors).selectinload(
                CompetitorMonitor.snapshots
            ),
            selectinload(Product.skus).selectinload(ProductSku.inventory_item),
            selectinload(Product.skus).selectinload(ProductSku.inventory_movements),
            selectinload(Product.platform_mappings),
            selectinload(Product.creative_plans),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.creative_plan
            ),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.ad_experiment
            ),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.promotion_link
            ),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.generated_asset
            ),
            selectinload(Product.review_reports),
            selectinload(Product.ad_recommendations),
            selectinload(Product.ad_experiments),
            selectinload(Product.promotion_links),
            selectinload(Product.generated_assets),
            selectinload(Product.diagnoses),
            selectinload(Product.generation_jobs).selectinload(GenerationJob.events),
            selectinload(Product.public_link_parse_tasks),
        )
    )
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Product.workspace_id == workspace_id)
    product = db.scalars(statement).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Product:
    """处理更新商品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    product = get_product_or_404(db, product_id)
    ensure_store_exists(db, payload.store_id)
    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.post(
    "/{product_id}/skus",
    response_model=ProductSkuDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_product_sku(
    product_id: int,
    payload: ProductSkuCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ProductSku:
    """处理创建商品SKU接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    # SKU 与库存档案同时创建，保证后续多平台映射和库存预警都有稳定落点。
    sku_payload = payload.model_dump(
        mode="json",
        exclude={"initial_quantity", "warning_threshold", "location"},
    )
    sku = ProductSku(product_id=product_id, **sku_payload)
    db.add(sku)
    db.flush()
    create_inventory_item_for_sku(
        db,
        sku,
        initial_quantity=payload.initial_quantity,
        warning_threshold=payload.warning_threshold,
        location=payload.location,
    )
    db.commit()
    db.refresh(sku)
    return sku


@router.patch(
    "/{product_id}/skus/{sku_id}",
    response_model=ProductSkuDetail,
)
def update_product_sku(
    product_id: int,
    sku_id: int,
    payload: ProductSkuUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ProductSku:
    """处理更新商品SKU接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    sku = get_sku_or_404(db, product_id, sku_id)
    data = payload.model_dump(exclude_unset=True, mode="json")
    for field in ["sku_code", "name", "attributes", "price", "cost", "status"]:
        if field in data:
            setattr(sku, field, data[field])

    if "warning_threshold" in data or "location" in data:
        inventory_item = sku.inventory_item
        if inventory_item is None:
            inventory_item = create_inventory_item_for_sku(db, sku)
        if "warning_threshold" in data:
            inventory_item.warning_threshold = data["warning_threshold"]
        if "location" in data:
            inventory_item.location = data["location"]

    db.commit()
    db.refresh(sku)
    return sku


@router.post(
    "/{product_id}/skus/{sku_id}/inventory-movements",
    response_model=InventoryMovementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_movement(
    product_id: int,
    sku_id: int,
    payload: InventoryMovementCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> InventoryMovement:
    """处理创建库存流水接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    sku = get_sku_or_404(db, product_id, sku_id)
    inventory_item = sku.inventory_item
    if inventory_item is None:
        # 历史或导入数据可能缺库存档案，写流水前先补档，避免直接丢弃运营录入。
        inventory_item = create_inventory_item_for_sku(db, sku)
    try:
        movement = adjust_inventory(
            db,
            inventory_item,
            movement_type=payload.movement_type,
            quantity_delta=payload.quantity_delta,
            locked_delta=payload.locked_delta,
            reason=payload.reason,
            reference_type=payload.reference_type,
            reference_id=payload.reference_id,
            operator_name=payload.operator_name,
        )
    except InventoryAdjustmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(movement)
    return movement


@router.post(
    "/{product_id}/platform-mappings",
    response_model=PlatformProductMappingRead,
    status_code=status.HTTP_201_CREATED,
)
def create_platform_product_mapping(
    product_id: int,
    payload: PlatformProductMappingCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PlatformProductMapping:
    """处理创建平台商品mapping接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    product = get_product_or_404(db, product_id)
    if payload.store_id is not None and product.store_id is not None and payload.store_id != product.store_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapping store does not match product store",
        )
    ensure_store_exists(db, payload.store_id)
    if payload.sku_id is not None:
        get_sku_or_404(db, product_id, payload.sku_id)

    mapping = PlatformProductMapping(product_id=product_id, **payload.model_dump(mode="json"))
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.post(
    "/{product_id}/competitors",
    response_model=CompetitorRead,
    status_code=status.HTTP_201_CREATED,
)
def create_competitor(
    product_id: int,
    payload: CompetitorCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Competitor:
    """处理创建竞品接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    competitor = Competitor(product_id=product_id, **payload.model_dump(mode="json"))
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


@router.post(
    "/{product_id}/competitors/import-url",
    response_model=CompetitorRead,
    status_code=status.HTTP_201_CREATED,
)
def import_competitor_from_url(
    product_id: int,
    payload: CompetitorUrlImport,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> Competitor:
    """处理导入竞品fromURL接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)

    try:
        profile = fetch_competitor_profile(str(payload.url))
    except LinkExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    competitor = Competitor(
        product_id=product_id,
        platform=payload.platform,
        url=str(payload.url),
        review_keywords=[],
        **profile.model_payload(),
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


@router.post(
    "/{product_id}/competitors/import-url-tasks",
    response_model=PublicLinkParseTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_competitor_url_import_task(
    product_id: int,
    payload: CompetitorUrlImport,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PublicLinkParseTask:
    """处理创建竞品URL导入任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    product = get_product_or_404(db, product_id)
    return enqueue_competitor_import_task(db, product, payload)


@router.post(
    "/{product_id}/link-parse-tasks/{task_id}/run",
    response_model=PublicLinkParseTaskRead,
)
def run_link_parse_task_now(
    product_id: int,
    task_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PublicLinkParseTask:
    """同步执行指定商品的公开链接解析任务，供人工调试和受控补偿使用。"""
    # 商品和任务必须同时匹配路径参数，防止借用其他商品的任务 ID 触发跨资源解析。
    get_product_or_404(db, product_id)
    task = db.get(PublicLinkParseTask, task_id)
    if task is None or task.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public link parse task not found")
    return run_public_link_parse_task(db, task)


@router.post(
    "/{product_id}/competitors/{competitor_id}/monitor",
    response_model=CompetitorMonitorRead,
    status_code=status.HTTP_201_CREATED,
)
def create_competitor_monitor(
    product_id: int,
    competitor_id: int,
    payload: CompetitorMonitorCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> CompetitorMonitor:
    """处理创建竞品监控接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    competitor = ensure_competitor_belongs_to_product(db, product_id, competitor_id)
    if not competitor.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Competitor URL is required before enabling monitor",
        )

    existing = db.scalars(
        select(CompetitorMonitor).where(
            CompetitorMonitor.product_id == product_id,
            CompetitorMonitor.competitor_id == competitor_id,
            CompetitorMonitor.status == "active",
        )
    ).first()
    if existing is not None:
        return existing

    monitor = CompetitorMonitor(
        product_id=product_id,
        competitor_id=competitor_id,
        status="active",
        interval_days=payload.interval_days,
        next_check_at=next_check_time(payload.interval_days),
        note=payload.note,
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return monitor


@router.post(
    "/{product_id}/competitor-monitors/{monitor_id}/run",
    response_model=CompetitorMonitorSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def run_competitor_monitor_now(
    product_id: int,
    monitor_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> CompetitorMonitorSnapshot:
    """处理执行竞品监控now接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    monitor = db.get(CompetitorMonitor, monitor_id)
    if monitor is None or monitor.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor monitor not found")
    if monitor.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only active monitors can be checked")

    snapshot = run_competitor_monitor(db, monitor)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.post(
    "/{product_id}/creative-plans",
    response_model=CreativePlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_creative_plan(
    product_id: int,
    payload: CreativePlanCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> CreativePlan:
    """处理创建创意方案接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    creative_plan = CreativePlan(product_id=product_id, **payload.model_dump(mode="json"))
    db.add(creative_plan)
    db.commit()
    db.refresh(creative_plan)
    return creative_plan


@router.patch(
    "/{product_id}/creative-plans/{creative_plan_id}",
    response_model=CreativePlanRead,
)
def update_creative_plan(
    product_id: int,
    creative_plan_id: int,
    payload: CreativePlanUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> CreativePlan:
    """处理更新创意方案接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    creative_plan = db.get(CreativePlan, creative_plan_id)
    if creative_plan is None or creative_plan.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative plan not found")

    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(creative_plan, field, value)

    db.commit()
    db.refresh(creative_plan)
    return creative_plan


@router.patch(
    "/{product_id}/creative-plans/{creative_plan_id}/assets",
    response_model=CreativePlanRead,
)
def update_generated_asset(
    product_id: int,
    creative_plan_id: int,
    payload: GeneratedAssetUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> CreativePlan:
    """处理更新生成素材接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    creative_plan = db.get(CreativePlan, creative_plan_id)
    if creative_plan is None or creative_plan.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative plan not found")

    content = dict(creative_plan.content or {})
    key = "generated_images" if payload.asset_type == "image" else "generated_videos"
    assets = content.get(key, [])
    if not isinstance(assets, list):
        assets = []

    updated = False
    next_assets = []
    for item in assets:
        if not isinstance(item, dict):
            next_assets.append(item)
            continue
        if item.get("url") != payload.url:
            next_assets.append(item)
            continue

        next_item = dict(item)
        for field, value in payload.model_dump(exclude={"url", "asset_type"}, exclude_unset=True).items():
            next_item[field] = value
        next_assets.append(next_item)
        updated = True

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generated asset not found")

    content[key] = next_assets

    generated_asset = db.scalars(
        select(GeneratedAsset).where(
            GeneratedAsset.product_id == product_id,
            GeneratedAsset.url == payload.url,
        )
    ).first()
    if generated_asset is not None:
        for field, value in payload.model_dump(
            exclude={"url", "asset_type"},
            exclude_unset=True,
        ).items():
            setattr(generated_asset, field, value)

    creative_plan.content = content
    db.commit()
    db.refresh(creative_plan)
    return creative_plan


@router.post(
    "/{product_id}/assets/sync",
    status_code=status.HTTP_200_OK,
)
def sync_generated_assets(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> dict[str, int]:
    """处理同步生成素材接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    get_product_or_404(db, product_id)
    created = sync_generated_assets_from_creative_plans(db, product_id)
    db.commit()
    return {"created": created}


@router.post(
    "/{product_id}/creative-plans/{creative_plan_id}/images/generate",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_creative_plan_image(
    product_id: int,
    creative_plan_id: int,
    background_tasks: BackgroundTasks,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> GenerationJob:
    """处理生成创意方案图片接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    creative_plan = db.get(CreativePlan, creative_plan_id)
    if creative_plan is None or creative_plan.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative plan not found")
    if creative_plan.type != CreativePlanType.MAIN_IMAGE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creative plan is not a main image plan")

    job = enqueue_generation_job(
        db,
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        kind=GenerationJobKind.MAIN_IMAGE_ASSET,
    )
    db.commit()
    db.refresh(job)
    # 接口返回 202 和任务记录，实际素材生成异步执行，用户可在工作台中等待、取消或重试。
    dispatch_generation_job(job.id, background_tasks)
    return job


@router.post(
    "/{product_id}/creative-plans/{creative_plan_id}/videos/generate",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_creative_plan_video(
    product_id: int,
    creative_plan_id: int,
    background_tasks: BackgroundTasks,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> GenerationJob:
    """处理生成创意方案视频接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    creative_plan = db.get(CreativePlan, creative_plan_id)
    if creative_plan is None or creative_plan.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative plan not found")
    if creative_plan.type != CreativePlanType.VIDEO_SCRIPT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creative plan is not a video script")

    job = enqueue_generation_job(
        db,
        product_id=product_id,
        creative_plan_id=creative_plan_id,
        kind=GenerationJobKind.VIDEO_ASSET,
    )
    db.commit()
    db.refresh(job)
    dispatch_generation_job(job.id, background_tasks)
    return job


@router.post(
    "/{product_id}/generation-jobs/{job_id}/retry",
    response_model=GenerationJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_generation_job(
    product_id: int,
    job_id: int,
    background_tasks: BackgroundTasks,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> GenerationJob:
    """处理重试生成任务任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    job = db.get(GenerationJob, job_id)
    if job is None or job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found")
    if job.status in {GenerationJobStatus.PENDING, GenerationJobStatus.RUNNING}:
        # 已在队列或执行中的任务保持幂等返回，避免用户重复点击造成多条生成请求。
        return job
    if job.status != GenerationJobStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed jobs can be retried")

    retry_generation_job_record(job)
    db.commit()
    db.refresh(job)
    dispatch_generation_job(job.id, background_tasks)
    return job


@router.post(
    "/{product_id}/generation-jobs/{job_id}/cancel",
    response_model=GenerationJobRead,
)
def cancel_generation_job(
    product_id: int,
    job_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> GenerationJob:
    """处理取消生成任务任务接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    job = db.get(GenerationJob, job_id)
    if job is None or job.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found")
    if not cancel_generation_job_record(job, reason="用户取消生成任务。"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending or running jobs can be cancelled")
    db.commit()
    db.refresh(job)
    return job


@router.post(
    "/{product_id}/creative-plans/main-images/generate",
    response_model=list[CreativePlanRead],
    status_code=status.HTTP_201_CREATED,
)
def generate_main_image_creative_plans(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> list[CreativePlan]:
    """处理生成主流程图片创意plans接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.competitors),
            selectinload(Product.diagnoses),
        )
    )
    product = db.scalars(statement).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    latest_diagnosis = product.diagnoses[0] if product.diagnoses else None
    plan_payloads = generate_main_image_plans(product, latest_diagnosis)
    creative_plans = [
        CreativePlan(
            product_id=product_id,
            type=CreativePlanType.MAIN_IMAGE,
            title=payload["title"],
            content=payload,
            rationale=payload["angle"],
        )
        for payload in plan_payloads
    ]

    db.add_all(creative_plans)
    db.commit()
    for creative_plan in creative_plans:
        db.refresh(creative_plan)
    return creative_plans


@router.post(
    "/{product_id}/creative-plans/video-scripts/generate",
    response_model=list[CreativePlanRead],
    status_code=status.HTTP_201_CREATED,
)
def generate_video_script_creative_plans(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> list[CreativePlan]:
    """处理生成视频script创意plans接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.competitors),
            selectinload(Product.diagnoses),
        )
    )
    product = db.scalars(statement).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    latest_diagnosis = product.diagnoses[0] if product.diagnoses else None
    plan_payloads = generate_video_script_plans(product, latest_diagnosis)
    creative_plans = [
        CreativePlan(
            product_id=product_id,
            type=CreativePlanType.VIDEO_SCRIPT,
            title=payload["title"],
            content=payload,
            rationale=payload["angle"],
        )
        for payload in plan_payloads
    ]

    db.add_all(creative_plans)
    db.commit()
    for creative_plan in creative_plans:
        db.refresh(creative_plan)
    return creative_plans


@router.post(
    "/{product_id}/performance-records",
    response_model=PerformanceRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_performance_record(
    product_id: int,
    payload: PerformanceRecordCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PerformanceRecord:
    """处理创建经营数据记录接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    # 经营数据允许关联素材、实验和链接，但每个外键都必须属于当前商品，保证复盘口径干净。
    ensure_creative_plan_belongs_to_product(db, product_id, payload.creative_plan_id)
    ensure_ad_experiment_belongs_to_product(db, product_id, payload.ad_experiment_id)
    promotion_link_id = payload.promotion_link_id or resolve_promotion_tracking_code(
        db,
        product_id,
        payload.promotion_tracking_code,
    )
    ensure_promotion_link_belongs_to_product(db, product_id, promotion_link_id)
    ensure_generated_asset_belongs_to_product(db, product_id, payload.generated_asset_id)
    record_payload = enrich_performance_metrics(payload.model_dump(mode="python"))
    record_payload["promotion_link_id"] = promotion_link_id
    performance_record = PerformanceRecord(product_id=product_id, **record_payload)
    db.add(performance_record)
    db.commit()
    db.refresh(performance_record)
    return performance_record


@router.post(
    "/{product_id}/performance-records/bulk",
    response_model=list[PerformanceRecordRead],
    status_code=status.HTTP_201_CREATED,
)
def create_performance_records_bulk(
    product_id: int,
    payload: PerformanceRecordBulkCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> list[PerformanceRecord]:
    """处理创建经营数据recordsbulk接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    performance_records: list[PerformanceRecord] = []

    for record in payload.records:
        ensure_creative_plan_belongs_to_product(db, product_id, record.creative_plan_id)
        ensure_ad_experiment_belongs_to_product(db, product_id, record.ad_experiment_id)
        promotion_link_id = record.promotion_link_id or resolve_promotion_tracking_code(
            db,
            product_id,
            record.promotion_tracking_code,
        )
        ensure_promotion_link_belongs_to_product(db, product_id, promotion_link_id)
        ensure_generated_asset_belongs_to_product(db, product_id, record.generated_asset_id)
        record_payload = enrich_performance_metrics(record.model_dump(mode="python"))
        record_payload["promotion_link_id"] = promotion_link_id
        performance_records.append(PerformanceRecord(product_id=product_id, **record_payload))

    db.add_all(performance_records)
    db.commit()
    for performance_record in performance_records:
        db.refresh(performance_record)
    return performance_records


@router.post(
    "/{product_id}/promotion-links",
    response_model=PromotionLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def create_promotion_link(
    product_id: int,
    payload: PromotionLinkCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PromotionLink:
    """处理创建推广链接接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    link_payload = enrich_tracking_fields(
        payload.model_dump(
            mode="json",
            exclude={"tracking_code", "short_code", "tracking_url", "click_count"},
        ),
        product_id=product_id,
        short_code=make_unique_short_code(db),
    )
    promotion_link = PromotionLink(product_id=product_id, **link_payload)
    db.add(promotion_link)
    db.commit()
    db.refresh(promotion_link)
    return promotion_link


@router.post(
    "/{product_id}/promotion-links/generate",
    response_model=list[PromotionLinkRead],
    status_code=status.HTTP_201_CREATED,
)
def generate_promotion_links(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> list[PromotionLink]:
    """处理生成推广links接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    product = get_product_or_404(db, product_id)
    links = [
        PromotionLink(
            product_id=product_id,
            **enrich_tracking_fields(
                payload,
                product_id=product_id,
                short_code=make_unique_short_code(db),
            ),
        )
        for payload in build_promotion_link_payloads(product)
    ]
    db.add_all(links)
    db.commit()
    for link in links:
        db.refresh(link)
    return links


def make_unique_short_code(db: Session) -> str:
    """处理生成unique短链code接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    for _ in range(10):
        short_code = make_short_code()
        exists = db.scalars(
            select(PromotionLink.id).where(PromotionLink.short_code == short_code)
        ).first()
        if exists is None:
            return short_code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate promotion link short code",
    )


@router.post(
    "/{product_id}/ad-recommendations/generate",
    response_model=AdRecommendationRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_ad_recommendation(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> AdRecommendation:
    """处理生成投放建议接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    product = db.scalars(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.creative_plans),
            selectinload(Product.performance_records),
            selectinload(Product.diagnoses),
        )
    ).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # 这里仅生成可编辑的投放建议记录，不对接广告平台，也不自动调整预算。
    payload = build_ad_recommendation(product)
    recommendation = AdRecommendation(product_id=product_id, **payload)
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.patch(
    "/{product_id}/ad-recommendations/{recommendation_id}/confirmation",
    response_model=AdRecommendationRead,
)
def update_ad_recommendation_confirmation(
    product_id: int,
    recommendation_id: int,
    payload: AdRecommendationConfirmationUpdate,
    db: SessionDep,
    current_user: Annotated[User, Depends(require_ad_confirmation_permission)],
) -> AdRecommendation:
    """处理更新投放建议confirmation接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    recommendation = db.get(AdRecommendation, recommendation_id)
    if recommendation is None or recommendation.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad recommendation not found")

    # 只记录人工判断结果，不调用平台投放 API，也不执行预算或扣费动作；这是投放闭环的合规边界。
    recommendation.confirmation_status = payload.confirmation_status
    recommendation.confirmation_note = payload.confirmation_note
    recommendation.confirmed_by_user_id = current_user.id
    recommendation.confirmed_at = datetime.now(UTC)
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.post(
    "/{product_id}/ad-experiments",
    response_model=AdExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ad_experiment(
    product_id: int,
    payload: AdExperimentCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> AdExperiment:
    """处理创建投放实验接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    # 手工创建实验也要校验素材和推广链接归属，避免跨商品复用导致统计失真。
    ensure_generated_asset_belongs_to_product(db, product_id, payload.generated_asset_id)
    ensure_promotion_link_belongs_to_product(db, product_id, payload.promotion_link_id)
    experiment = AdExperiment(product_id=product_id, **payload.model_dump(mode="python"))
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.post(
    "/{product_id}/ad-experiments/generate",
    response_model=AdExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_ad_experiment(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> AdExperiment:
    """处理生成投放实验接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    product = db.scalars(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.generated_assets),
            selectinload(Product.promotion_links),
            selectinload(Product.performance_records),
        )
    ).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # 自动生成的实验保持 draft 状态，只是帮运营准备计划草稿，不会创建真实广告计划。
    payload = build_ad_experiment_payload(product)
    experiment = AdExperiment(product_id=product_id, **payload)
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.patch(
    "/{product_id}/ad-experiments/{experiment_id}",
    response_model=AdExperimentRead,
)
def update_ad_experiment(
    product_id: int,
    experiment_id: int,
    payload: AdExperimentUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_ad_confirmation_permission)],
) -> AdExperiment:
    """处理更新投放实验接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    experiment = db.get(AdExperiment, experiment_id)
    if experiment is None or experiment.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad experiment not found")

    # 实验状态和预算字段属于人工运营决策，复用投放确认权限而不是普通查看权限。
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(experiment, field, value)

    db.commit()
    db.refresh(experiment)
    return experiment


@router.get(
    "/{product_id}/ad-experiments/dashboard",
    response_model=AdExperimentDashboardRead,
)
def get_ad_experiment_dashboard(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_view_permission)],
) -> dict:
    """处理获取投放实验看板接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    product = db.scalars(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.ad_experiments),
            selectinload(Product.performance_records),
        )
    ).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # 看板只读取并汇总回填数据，不写实验状态，避免“系统建议”越权变成自动投放动作。
    return build_ad_experiment_dashboard(product)


@router.post(
    "/{product_id}/review-reports",
    response_model=ReviewReportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review_report(
    product_id: int,
    payload: ReviewReportCreate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ReviewReport:
    """处理创建审核report接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    review_report = ReviewReport(product_id=product_id, **payload.model_dump())
    db.add(review_report)
    db.commit()
    db.refresh(review_report)
    return review_report


@router.patch(
    "/{product_id}/review-reports/{review_report_id}",
    response_model=ReviewReportRead,
)
def update_review_report(
    product_id: int,
    review_report_id: int,
    payload: ReviewReportUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ReviewReport:
    """处理更新审核report接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    review_report = db.get(ReviewReport, review_report_id)
    if review_report is None or review_report.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review report not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review_report, field, value)

    db.commit()
    db.refresh(review_report)
    return review_report


@router.post(
    "/{product_id}/review-reports/generate",
    response_model=ReviewReportRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_review_report(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ReviewReport:
    """处理生成审核report接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.creative_plan
            ),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.ad_experiment
            ),
            selectinload(Product.performance_records).selectinload(
                PerformanceRecord.promotion_link
            ),
            selectinload(Product.diagnoses),
        )
    )
    product = db.scalars(statement).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    try:
        review_payload = build_review_report(product)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    review_report = ReviewReport(product_id=product_id, **review_payload)
    db.add(review_report)
    db.commit()
    db.refresh(review_report)
    return review_report


@router.post(
    "/{product_id}/diagnoses/generate",
    response_model=ProductDiagnosisRead,
    status_code=status.HTTP_201_CREATED,
)
def generate_product_diagnosis(
    product_id: int,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ProductDiagnosis:
    """处理生成商品商品诊断接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.competitors))
    )
    product = db.scalars(statement).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    diagnosis_payload = build_product_diagnosis(product)
    diagnosis = ProductDiagnosis(product_id=product_id, **diagnosis_payload)
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


@router.patch(
    "/{product_id}/diagnoses/{diagnosis_id}",
    response_model=ProductDiagnosisRead,
)
def update_product_diagnosis(
    product_id: int,
    diagnosis_id: int,
    payload: ProductDiagnosisUpdate,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ProductDiagnosis:
    """处理更新商品商品诊断接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    get_product_or_404(db, product_id)
    diagnosis = db.get(ProductDiagnosis, diagnosis_id)
    if diagnosis is None or diagnosis.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis not found")

    for field, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(diagnosis, field, value)

    db.commit()
    db.refresh(diagnosis)
    return diagnosis
