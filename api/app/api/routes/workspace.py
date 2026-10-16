from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import require_edit_permission
from app.db.session import get_db
from app.models import (
    AdExperiment,
    AdRecommendation,
    Competitor,
    CompetitorMonitor,
    CreativePlan,
    CreativePlanStatus,
    CreativePlanType,
    GeneratedAsset,
    GenerationJob,
    GenerationJobEvent,
    GenerationJobKind,
    GenerationJobStatus,
    PerformanceRecord,
    PlatformAccount,
    Platform,
    Product,
    ProductDiagnosis,
    ProductSku,
    PromotionLink,
    ReviewReport,
    Store,
    User,
)
from app.schemas import CompetitorMonitorSchedulerRunResult, DemoWorkspaceRead, GenerationJobTimeoutSweepResult
from app.schemas import ProductImportRequest, ProductImportResult
from app.schemas import PerformanceImportRequest, PerformanceImportResult
from app.schemas import SkuInventoryImportRequest, SkuInventoryImportResult
from app.services.inventory import create_inventory_item_for_sku
from app.services.competitor_monitor_scheduler import run_due_competitor_monitors
from app.services.generation_jobs import mark_stale_running_generation_jobs
from app.services.performance_import import import_performance_records, preview_performance_import
from app.services.product_import import import_products, preview_product_import
from app.services.review import enrich_performance_metrics
from app.services.sku_inventory_import import import_sku_inventory, preview_sku_inventory_import


router = APIRouter(prefix="/workspace", tags=["workspace"])
SessionDep = Annotated[Session, Depends(get_db)]


PERFORMANCE_TEMPLATE = """product_name,external_product_id,period_start,period_end,impressions,clicks,conversions,spend,revenue,notes
低糖燕麦饼干,demo-oat-cookie,2026-05-01,2026-05-07,12000,420,38,860.00,3420.00,首周冷启动
"""

PRODUCT_TEMPLATE = """store_name,platform,name,category,price,cost,target_audience,selling_points,external_product_id,platform_status
抖音演示店,douyin,低糖燕麦饼干,食品,29.90,12.50,关注控糖和代餐的上班族,"低糖;饱腹;独立包装",demo-oat-cookie,online
"""

SKU_INVENTORY_TEMPLATE = """product_name,sku_code,sku_name,price,cost,initial_quantity,warning_threshold,location,external_sku_id
低糖燕麦饼干,OAT-12,12 包装,29.90,12.50,100,20,A-01,demo-oat-12
"""

FIELD_MAPPING_TEMPLATE = """source_field,target_field,required,description
商品名称,name,yes,商品档案名称
平台,platform,yes,"douyin/taobao/tmall/pinduoduo/jd 等"
售价,price,no,商品或 SKU 售价
曝光,impressions,no,经营数据曝光量
点击,clicks,no,经营数据点击量
成交,conversions,no,经营数据成交数
"""


@router.get("/templates/performance-records.csv")
def download_performance_template() -> Response:
    """处理下载经营数据模板接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return Response(
        content=PERFORMANCE_TEMPLATE,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="performance-records-template.csv"'},
    )


@router.get("/templates/products.csv")
def download_product_template() -> Response:
    """处理下载商品模板接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return _csv_response(PRODUCT_TEMPLATE, "products-template.csv")


@router.get("/templates/sku-inventory.csv")
def download_sku_inventory_template() -> Response:
    """处理下载SKU库存模板接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return _csv_response(SKU_INVENTORY_TEMPLATE, "sku-inventory-template.csv")


@router.get("/templates/field-mapping.csv")
def download_field_mapping_template() -> Response:
    """处理下载字段mapping模板接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return _csv_response(FIELD_MAPPING_TEMPLATE, "field-mapping-template.csv")


def _csv_response(content: str, filename: str) -> Response:
    """处理csvresponse接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/imports/products", response_model=ProductImportResult)
def import_product_csv(
    payload: ProductImportRequest,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> ProductImportResult:
    # commit=false 只做预览，commit=true 才写库，表格导入必须保留人工确认步骤。
    """处理导入商品csv接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if payload.commit:
        rows = import_products(db, payload.csv_text)
    else:
        _parsed_rows, rows = preview_product_import(payload.csv_text)

    return ProductImportResult(
        commit=payload.commit,
        total_rows=len(rows),
        valid_rows=sum(1 for row in rows if row.status in {"valid", "created"}),
        created_count=sum(1 for row in rows if row.status == "created"),
        error_count=sum(1 for row in rows if row.status == "error"),
        rows=rows,
    )


@router.post("/imports/sku-inventory", response_model=SkuInventoryImportResult)
def import_sku_inventory_csv(
    payload: SkuInventoryImportRequest,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> SkuInventoryImportResult:
    # SKU 和库存导入影响履约判断，前端可先预览错误行，再由运营确认提交。
    """处理导入SKU库存csv接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if payload.commit:
        rows = import_sku_inventory(db, payload.csv_text)
    else:
        _parsed_rows, rows = preview_sku_inventory_import(db, payload.csv_text)

    return SkuInventoryImportResult(
        commit=payload.commit,
        total_rows=len(rows),
        valid_rows=sum(1 for row in rows if row.status in {"valid", "created"}),
        created_count=sum(1 for row in rows if row.status == "created"),
        error_count=sum(1 for row in rows if row.status == "error"),
        rows=rows,
    )


@router.post("/imports/performance-records", response_model=PerformanceImportResult)
def import_performance_csv(
    payload: PerformanceImportRequest,
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> PerformanceImportResult:
    # 经营数据导入会影响复盘和实验看板，提交前同样支持只校验不落库。
    """处理导入经营数据csv接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    if payload.commit:
        rows = import_performance_records(db, payload.csv_text)
    else:
        _parsed_rows, rows = preview_performance_import(db, payload.csv_text)

    return PerformanceImportResult(
        commit=payload.commit,
        total_rows=len(rows),
        valid_rows=sum(1 for row in rows if row.status in {"valid", "created"}),
        created_count=sum(1 for row in rows if row.status == "created"),
        error_count=sum(1 for row in rows if row.status == "error"),
        rows=rows,
    )


@router.post(
    "/demo-data",
    response_model=DemoWorkspaceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_demo_workspace(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
) -> DemoWorkspaceRead:
    """处理创建demoWorkspace接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    workspace_id = db.info.get("workspace_id")
    statement = select(Store).where(Store.external_store_id == "demo-douyin-store")
    if workspace_id is not None:
        statement = statement.where(Store.workspace_id == workspace_id)
    existing_store = db.scalars(statement).first()
    if existing_store is not None:
        # 演示数据保持幂等，避免用户多次点击后生成重复店铺、SKU 和投放实验。
        return DemoWorkspaceRead(
            store_id=existing_store.id,
            product_ids=[product.id for product in existing_store.products],
            sku_ids=[sku.id for product in existing_store.products for sku in product.skus],
            message="演示数据已存在，已返回现有数据。",
        )

    store = Store(
        workspace_id=workspace_id,
        name="抖音演示店",
        platform=Platform.DOUYIN,
        external_store_id="demo-douyin-store",
        owner_name="运营负责人",
        note="用于 V1 工作台演示的数据，不代表真实经营数据。",
    )
    db.add(store)
    db.flush()

    platform_account = PlatformAccount(
        store=store,
        platform=Platform.DOUYIN,
        account_name="抖音演示账号",
        external_account_id="demo-douyin-account",
        auth_metadata={"授权状态": "演示占位", "说明": "不包含真实 token、cookie 或密码。"},
        note="演示账号只用于展示授权流程边界。",
    )
    db.add(platform_account)

    products = [
        Product(
            workspace_id=workspace_id,
            store=store,
            name="低糖燕麦饼干",
            platform=Platform.DOUYIN,
            category="食品",
            price=Decimal("29.90"),
            cost=Decimal("12.50"),
            target_audience="关注控糖和代餐的上班族",
            selling_points=["低糖", "饱腹", "独立包装"],
            external_product_id="demo-oat-cookie",
            platform_status="online",
        ),
        Product(
            workspace_id=workspace_id,
            store=store,
            name="便携冷萃咖啡液",
            platform=Platform.DOUYIN,
            category="饮品",
            price=Decimal("49.90"),
            cost=Decimal("22.00"),
            target_audience="需要快速提神的办公室人群",
            selling_points=["三秒速溶", "低负担", "适合冰饮"],
            external_product_id="demo-coldbrew",
            platform_status="online",
        ),
    ]
    db.add_all(products)
    db.flush()

    sku_ids: list[int] = []
    for product, sku_code, sku_name, quantity, locked, threshold in [
        (products[0], "OAT-12", "12 包装", 36, 8, 20),
        (products[0], "OAT-24", "24 包装", 12, 2, 15),
        (products[1], "COFFEE-10", "10 条装", 58, 6, 20),
    ]:
        sku = ProductSku(product=product, sku_code=sku_code, name=sku_name, price=product.price, cost=product.cost)
        db.add(sku)
        db.flush()
        item = create_inventory_item_for_sku(
            db,
            sku,
            initial_quantity=quantity,
            warning_threshold=threshold,
            location="演示仓",
            operator_name="系统演示",
        )
        if locked > 0:
            create_inventory_item_lock(db, item, locked)
        sku_ids.append(sku.id)

    competitor = Competitor(
        product=products[0],
        name="竞品 A 控糖饼干",
        platform=Platform.DOUYIN,
        price=Decimal("32.90"),
        sales_hint="近 30 天销量 1w+",
        title="控糖代餐饼干",
        selling_points=["高纤维", "低 GI", "办公室零食"],
        review_keywords=["口感扎实", "包装方便"],
    )
    competitor_monitor = CompetitorMonitor(
        product=products[0],
        competitor=competitor,
        status="active",
        interval_days=1,
        next_check_at=datetime.now(UTC) + timedelta(days=1),
        note="演示监控，不触发真实平台采集。",
    )
    diagnosis = ProductDiagnosis(
        product=products[0],
        source="rules",
        positioning="面向控糖和代餐人群的办公室低糖零食。",
        price_band="中低价位，适合短视频冷启动小预算测试。",
        audience_insights=["上班族下午茶场景明确", "控糖但不想牺牲饱腹感"],
        pain_points=["怕胖", "下午容易饿", "健康零食口感差"],
        selling_point_analysis=["低糖降低负担", "独立包装适合办公室", "饱腹感承接代餐需求"],
        risks=["同类控糖零食竞争强", "需要用真实口感反馈降低疑虑"],
        recommendations=["优先测试办公室下午茶场景主图", "用小预算验证控糖人群点击和 ROI"],
        raw_output={"source": "demo"},
    )
    main_image_plan = CreativePlan(
        product=products[0],
        type=CreativePlanType.MAIN_IMAGE,
        title="控糖代餐场景主图",
        content={
            "headline": "低糖也能吃得满足",
            "visual": "办公桌、咖啡和独立包装饼干",
            "generated_images": [
                {
                    "url": "/uploads/demo-oat-main-image.png",
                    "model": "demo",
                    "size": "1024*1024",
                    "status": "通过",
                    "asset_version": 1,
                    "usage_contexts": ["冷启动", "人群测试"],
                    "rating": 4,
                    "tags": ["办公室", "低糖"],
                    "note": "演示素材，用于素材库和投放归因展示。",
                }
            ],
        },
        rationale="突出上班族真实消费场景，降低健康食品的距离感。",
        status=CreativePlanStatus.SELECTED,
    )
    video_plan = CreativePlan(
        product=products[0],
        type=CreativePlanType.VIDEO_SCRIPT,
        title="下午四点饥饿感短视频",
        content={"hook": "下午四点又饿又怕胖", "script": ["展示办公室场景", "拆开独立包装", "强调低糖饱腹"]},
        rationale="用痛点开场，承接控糖和饱腹利益点。",
    )
    promotion_link = PromotionLink(
        product=products[0],
        label="抖音短视频落地页",
        url="https://example.com/demo/oat-cookie",
        link_type="landing",
        scenario="短视频",
        tracking_code="demo-oat-video",
        short_code="demo-oat",
        tracking_url="/r/demo-oat-video",
        note="演示链接，不会自动投放或扣费。",
    )
    ad_experiment = AdExperiment(
        product=products[0],
        promotion_link=promotion_link,
        name="控糖人群短视频测试",
        objective="验证控糖代餐人群点击和转化表现",
        audience="25-35 岁一二线城市办公室人群",
        daily_budget=Decimal("150.00"),
        status="draft",
        success_metric="ROI >= 3 且转化率 >= 8%",
        hypothesis="下午茶饥饿场景能提升点击率和转化率。",
    )
    db.add_all([competitor, competitor_monitor, diagnosis, main_image_plan, video_plan, promotion_link, ad_experiment])
    db.flush()

    generation_job = GenerationJob(
        product=products[0],
        creative_plan=main_image_plan,
        kind=GenerationJobKind.MAIN_IMAGE_ASSET,
        status=GenerationJobStatus.SUCCEEDED,
        result={"url": "/uploads/demo-oat-main-image.png"},
        attempts=1,
        max_attempts=3,
        started_at=datetime.now(UTC) - timedelta(minutes=8),
        finished_at=datetime.now(UTC) - timedelta(minutes=6),
    )
    db.add(generation_job)
    db.flush()
    db.add_all(
        [
            GenerationJobEvent(
                job=generation_job,
                event_type="queued",
                status=GenerationJobStatus.PENDING,
                message="演示任务已入队。",
            ),
            GenerationJobEvent(
                job=generation_job,
                event_type="succeeded",
                status=GenerationJobStatus.SUCCEEDED,
                message="演示任务执行成功。",
            ),
        ]
    )
    generated_asset = GeneratedAsset(
        product=products[0],
        creative_plan=main_image_plan,
        generation_job=generation_job,
        asset_type="image",
        title="控糖代餐场景主图",
        url="/uploads/demo-oat-main-image.png",
        model="demo",
        size="1024*1024",
        status="通过",
        asset_version=1,
        usage_contexts=["冷启动", "人群测试"],
        rating=4,
        tags=["办公室", "低糖"],
        note="演示素材，用于素材库和投放归因展示。",
    )
    db.add(generated_asset)
    db.flush()
    ad_experiment.generated_asset = generated_asset
    ad_recommendation = AdRecommendation(
        product=products[0],
        source="rules",
        summary="建议用通过审核的办公室场景主图，搭配短视频落地页做 3 天小预算测试。",
        content={
            "objective": "验证控糖代餐人群点击和 ROI",
            "audience_segments": [{"name": "办公室控糖人群", "reason": "场景和卖点匹配"}],
            "budget_plan": {"daily_budget": 150, "days": 3},
            "creative_tests": [{"asset": "控糖代餐场景主图", "hypothesis": "办公室场景提升点击"}],
            "bid_strategy": ["先低预算观察 CTR 和 ROI"],
            "risk_controls": ["不自动投放，预算需人工确认"],
            "next_steps": ["确认建议后生成实验计划", "回填 3 天经营数据后复盘"],
        },
        confirmation_status="confirmed",
        confirmed_by_user_id=1,
        confirmed_at=datetime.now(UTC) - timedelta(minutes=5),
        confirmation_note="演示确认：仅用于小预算测试计划，不执行真实投放。",
    )
    db.add(ad_recommendation)

    today = date.today()
    performance_payload = enrich_performance_metrics(
        {
            "creative_plan_id": main_image_plan.id,
            "ad_experiment_id": ad_experiment.id,
            "promotion_link_id": promotion_link.id,
            "period_start": today - timedelta(days=7),
            "period_end": today - timedelta(days=1),
            "impressions": 12800,
            "clicks": 512,
            "conversions": 46,
            "spend": Decimal("920.00"),
            "revenue": Decimal("3864.00"),
            "notes": "演示数据：用于验证投放实验看板和复盘链路。",
        }
    )
    performance_record = PerformanceRecord(
        product=products[0],
        generated_asset=generated_asset,
        **performance_payload,
    )
    db.add(performance_record)
    review_report = ReviewReport(
        product=products[0],
        period_start=today - timedelta(days=7),
        period_end=today - timedelta(days=1),
        summary="演示复盘：控糖饼干在办公室场景下 ROI 表现较好，可继续复测素材。",
        insights=["ROI 超过 3，具备继续观察价值", "素材和链接已关联，可用于归因面板"],
        next_actions=["保留当前素材结构", "补一个不同利益点版本做复测", "继续保持人工确认预算"],
    )
    db.add(review_report)
    db.commit()

    return DemoWorkspaceRead(
        store_id=store.id,
        product_ids=[product.id for product in products],
        sku_ids=sku_ids,
        message="演示数据创建成功。",
    )


@router.post("/competitor-monitors/run-due", response_model=CompetitorMonitorSchedulerRunResult)
def run_due_competitor_monitor_tasks(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
    limit: int = Query(default=20, ge=1, le=100),
) -> CompetitorMonitorSchedulerRunResult:
    # 手动触发调度只处理到期监控，不创建新的采集规则或扩大抓取范围。
    """处理执行到期竞品监控tasks接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    return run_due_competitor_monitors(db, limit=limit)


@router.post("/generation-jobs/sweep-timeouts", response_model=GenerationJobTimeoutSweepResult)
def sweep_generation_job_timeouts(
    db: SessionDep,
    _current_user: Annotated[User, Depends(require_edit_permission)],
    timeout_minutes: int = Query(default=30, ge=1, le=1440),
) -> GenerationJobTimeoutSweepResult:
    # 超时清理只修复卡住的生成任务状态，不取消供应商侧可能仍在运行的外部任务。
    """处理扫描生成任务任务timeouts接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    processed_count = mark_stale_running_generation_jobs(db, timeout_minutes=timeout_minutes)
    return GenerationJobTimeoutSweepResult(timeout_minutes=timeout_minutes, processed_count=processed_count)


def create_inventory_item_lock(db: Session, item, locked_quantity: int) -> None:
    """处理创建库存条目锁定接口；完成身份、Workspace、资源归属和输入校验后返回结构化结果。"""
    # 先完成认证、Workspace 与资源归属校验，再进入会产生副作用的服务调用。
    from app.models import InventoryMovementType
    from app.services.inventory import adjust_inventory

    adjust_inventory(
        db,
        item,
        movement_type=InventoryMovementType.LOCK,
        locked_delta=locked_quantity,
        reason="演示订单锁定",
        operator_name="系统演示",
    )
