import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdExperiment, CreativePlan, GeneratedAsset, PerformanceRecord, Product, PromotionLink
from app.schemas import PerformanceImportRowResult
from app.services.review import enrich_performance_metrics


@dataclass
class ParsedPerformanceRow:
    row_number: int
    product: Product
    period_start: date
    period_end: date
    creative_plan_id: int | None
    ad_experiment_id: int | None
    promotion_link_id: int | None
    generated_asset_id: int | None
    impressions: int | None
    clicks: int | None
    ctr: Decimal | None
    conversions: int | None
    conversion_rate: Decimal | None
    spend: Decimal | None
    revenue: Decimal | None
    roi: Decimal | None
    notes: str | None


HEADER_ALIASES = {
    "product_name": "product_name",
    "商品名称": "product_name",
    "external_product_id": "external_product_id",
    "平台商品id": "external_product_id",
    "period_start": "period_start",
    "start_date": "period_start",
    "start": "period_start",
    "日期": "period_start",
    "开始日期": "period_start",
    "period_end": "period_end",
    "end_date": "period_end",
    "end": "period_end",
    "结束日期": "period_end",
    "creative_plan_id": "creative_plan_id",
    "plan_id": "creative_plan_id",
    "ad_experiment_id": "ad_experiment_id",
    "experiment_id": "ad_experiment_id",
    "generated_asset_id": "generated_asset_id",
    "asset_id": "generated_asset_id",
    "promotion_link_id": "promotion_link_id",
    "promotion_tracking_code": "promotion_tracking_code",
    "tracking_code": "promotion_tracking_code",
    "eo_tracking_code": "promotion_tracking_code",
    "impressions": "impressions",
    "exposure": "impressions",
    "曝光": "impressions",
    "clicks": "clicks",
    "click": "clicks",
    "点击": "clicks",
    "ctr": "ctr",
    "conversions": "conversions",
    "conversion": "conversions",
    "成交": "conversions",
    "conversion_rate": "conversion_rate",
    "cvr": "conversion_rate",
    "spend": "spend",
    "cost": "spend",
    "花费": "spend",
    "revenue": "revenue",
    "sales": "revenue",
    "成交额": "revenue",
    "roi": "roi",
    "notes": "notes",
    "note": "notes",
    "备注": "notes",
}


def preview_performance_import(
    db: Session,
    csv_text: str,
) -> tuple[list[ParsedPerformanceRow], list[PerformanceImportRowResult]]:
    """预览经营数据导入；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows: list[ParsedPerformanceRow] = []
    results: list[PerformanceImportRowResult] = []

    # 经营数据导入先预览校验，确保实验、素材、链接归属正确后再真正入库。
    for row_number, row in _read_csv_rows(csv_text):
        parsed, errors, product_name, period_start, period_end = _parse_row(db, row_number, row)
        if errors:
            results.append(
                PerformanceImportRowResult(
                    row_number=row_number,
                    status="error",
                    errors=errors,
                    product_name=product_name,
                    period_start=period_start,
                    period_end=period_end,
                )
            )
            continue

        assert parsed is not None
        parsed_rows.append(parsed)
        results.append(
            PerformanceImportRowResult(
                row_number=row_number,
                status="valid",
                product_id=parsed.product.id,
                product_name=parsed.product.name,
                period_start=parsed.period_start,
                period_end=parsed.period_end,
            )
        )

    return parsed_rows, results


def import_performance_records(db: Session, csv_text: str) -> list[PerformanceImportRowResult]:
    """导入经营数据records；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows, results = preview_performance_import(db, csv_text)
    parsed_by_row = {row.row_number: row for row in parsed_rows}

    # 提交时会补算 CTR、转化率和 ROI，但不覆盖用户显式导入的指标，保留平台报表口径。
    for result in results:
        parsed = parsed_by_row.get(result.row_number)
        if parsed is None:
            continue

        payload = enrich_performance_metrics(
            {
                "creative_plan_id": parsed.creative_plan_id,
                "ad_experiment_id": parsed.ad_experiment_id,
                "promotion_link_id": parsed.promotion_link_id,
                "generated_asset_id": parsed.generated_asset_id,
                "period_start": parsed.period_start,
                "period_end": parsed.period_end,
                "impressions": parsed.impressions,
                "clicks": parsed.clicks,
                "ctr": parsed.ctr,
                "conversions": parsed.conversions,
                "conversion_rate": parsed.conversion_rate,
                "spend": parsed.spend,
                "revenue": parsed.revenue,
                "roi": parsed.roi,
                "notes": parsed.notes,
            }
        )
        record = PerformanceRecord(product_id=parsed.product.id, **payload)
        db.add(record)
        db.flush()
        result.status = "created"
        result.record_id = record.id

    db.commit()
    return results


def _read_csv_rows(csv_text: str) -> list[tuple[int, dict[str, str]]]:
    """读取csv行，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    rows: list[tuple[int, dict[str, str]]] = []
    for index, raw_row in enumerate(reader, start=2):
        if not raw_row or not any((value or "").strip() for value in raw_row.values()):
            continue
        normalized = {
            HEADER_ALIASES.get(str(key or "").strip(), str(key or "").strip()): (value or "").strip()
            for key, value in raw_row.items()
        }
        rows.append((index, normalized))
    return rows


def _parse_row(
    db: Session,
    row_number: int,
    row: dict[str, str],
) -> tuple[ParsedPerformanceRow | None, list[str], str | None, date | None, date | None]:
    """解析行，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    errors: list[str] = []
    product = _resolve_product(db, row, errors)
    period_start = _parse_date(row.get("period_start", ""), "period_start", errors)
    period_end = _parse_date(row.get("period_end", ""), "period_end", errors) or period_start
    product_name = row.get("product_name") or row.get("external_product_id")

    creative_plan_id = _parse_optional_int(row.get("creative_plan_id", ""), "creative_plan_id", errors)
    ad_experiment_id = _parse_optional_int(row.get("ad_experiment_id", ""), "ad_experiment_id", errors)
    promotion_link_id = _parse_optional_int(row.get("promotion_link_id", ""), "promotion_link_id", errors)
    generated_asset_id = _parse_optional_int(row.get("generated_asset_id", ""), "generated_asset_id", errors)
    promotion_tracking_code = row.get("promotion_tracking_code", "")

    if product is not None:
        # 归因字段都必须属于当前商品，防止导入表格手误造成跨商品实验统计污染。
        _ensure_belongs(db, CreativePlan, creative_plan_id, product.id, "creative_plan_id", errors)
        _ensure_belongs(db, AdExperiment, ad_experiment_id, product.id, "ad_experiment_id", errors)
        _ensure_belongs(db, GeneratedAsset, generated_asset_id, product.id, "generated_asset_id", errors)
        if promotion_tracking_code and promotion_link_id is None:
            promotion_link = db.scalars(
                select(PromotionLink).where(
                    PromotionLink.product_id == product.id,
                    PromotionLink.tracking_code == promotion_tracking_code,
                )
            ).first()
            if promotion_link is None:
                errors.append(f"promotion_tracking_code 不属于商品：{promotion_tracking_code}")
            else:
                promotion_link_id = promotion_link.id
        _ensure_belongs(db, PromotionLink, promotion_link_id, product.id, "promotion_link_id", errors)

    impressions = _parse_optional_int(row.get("impressions", ""), "impressions", errors)
    clicks = _parse_optional_int(row.get("clicks", ""), "clicks", errors)
    conversions = _parse_optional_int(row.get("conversions", ""), "conversions", errors)
    ctr = _parse_optional_decimal_or_rate(row.get("ctr", ""), "ctr", errors)
    conversion_rate = _parse_optional_decimal_or_rate(row.get("conversion_rate", ""), "conversion_rate", errors)
    spend = _parse_optional_decimal(row.get("spend", ""), "spend", errors)
    revenue = _parse_optional_decimal(row.get("revenue", ""), "revenue", errors)
    roi = _parse_optional_decimal_or_rate(row.get("roi", ""), "roi", errors)

    if errors or product is None or period_start is None or period_end is None:
        return None, errors, product_name or None, period_start, period_end

    return (
        ParsedPerformanceRow(
            row_number=row_number,
            product=product,
            period_start=period_start,
            period_end=period_end,
            creative_plan_id=creative_plan_id,
            ad_experiment_id=ad_experiment_id,
            promotion_link_id=promotion_link_id,
            generated_asset_id=generated_asset_id,
            impressions=impressions,
            clicks=clicks,
            ctr=ctr,
            conversions=conversions,
            conversion_rate=conversion_rate,
            spend=spend,
            revenue=revenue,
            roi=roi,
            notes=_empty_to_none(row.get("notes", "")),
        ),
        [],
        product.name,
        period_start,
        period_end,
    )


def _resolve_product(db: Session, row: dict[str, str], errors: list[str]) -> Product | None:
    """解析商品，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    product_name = row.get("product_name", "").strip()
    external_product_id = row.get("external_product_id", "").strip()
    if not product_name and not external_product_id:
        errors.append("product_name 或 external_product_id 必须填写一个")
        return None
    statement = select(Product)
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Product.workspace_id == workspace_id)
    if external_product_id:
        statement = statement.where(Product.external_product_id == external_product_id)
    else:
        statement = statement.where(Product.name == product_name)
    product = db.scalars(statement).first()
    if product is None:
        errors.append(f"找不到商品：{external_product_id or product_name}")
    return product


def _ensure_belongs(db: Session, model, item_id: int | None, product_id: int, field: str, errors: list[str]) -> None:
    """确保belongs，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if item_id is None:
        return
    item = db.get(model, item_id)
    if item is None or item.product_id != product_id:
        errors.append(f"{field} 不属于当前商品：{item_id}")


def _parse_date(value: str, field: str, errors: list[str]) -> date | None:
    """解析日期，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        errors.append(f"{field} 不能为空")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} 必须是 YYYY-MM-DD")
        return None


def _parse_optional_int(value: str, field: str, errors: list[str]) -> int | None:
    """解析可选int，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        return None
    normalized = value.replace(",", "")
    try:
        number = int(normalized)
    except ValueError:
        errors.append(f"{field} 必须是整数")
        return None
    if number < 0:
        errors.append(f"{field} 不能小于 0")
    return number


def _parse_optional_decimal(value: str, field: str, errors: list[str]) -> Decimal | None:
    """解析可选小数，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        return None
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        errors.append(f"{field} 必须是数字")
        return None
    if number < 0:
        errors.append(f"{field} 不能小于 0")
    return number


def _parse_optional_decimal_or_rate(value: str, field: str, errors: list[str]) -> Decimal | None:
    """解析可选小数orrate，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("%"):
        # 表格允许运营录入 4% 这类常见报表格式，内部统一换算成 0.0400 参与计算。
        number = _parse_optional_decimal(normalized[:-1], field, errors)
        return number / Decimal("100") if number is not None else None
    return _parse_optional_decimal(normalized, field, errors)


def _empty_to_none(value: str) -> str | None:
    """空值tonone，统一主流程中的格式、默认值和异常边界。"""
    return value.strip() if value and value.strip() else None
