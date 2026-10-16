from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import HTTPException, APIRouter, Depends, Query, Response, status
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
    raise HTTPException(status_code=501, detail="该功能尚未接入，正在开发中。")


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
    raise HTTPException(status_code=501, detail="该功能尚未接入，正在开发中。")


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
