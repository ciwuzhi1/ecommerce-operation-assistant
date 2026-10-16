import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Platform, Product, Store
from app.schemas import ProductImportRowResult


@dataclass
class ParsedProductRow:
    row_number: int
    store_name: str | None
    platform: Platform
    name: str
    category: str | None
    price: Decimal | None
    cost: Decimal | None
    target_audience: str | None
    selling_points: list[str]
    external_product_id: str | None
    platform_status: str | None


def preview_product_import(csv_text: str) -> tuple[list[ParsedProductRow], list[ProductImportRowResult]]:
    """预览商品导入；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows: list[ParsedProductRow] = []
    results: list[ProductImportRowResult] = []

    # 预览阶段只做校验和标准化，不写数据库，给运营确认导入结果的机会。
    for row_number, row in _read_csv_rows(csv_text):
        parsed, errors = _parse_row(row_number, row)
        if errors:
            results.append(
                ProductImportRowResult(
                    row_number=row_number,
                    status="error",
                    errors=errors,
                    product_name=row.get("name") or row.get("商品名称"),
                    store_name=row.get("store_name") or row.get("店铺"),
                )
            )
            continue

        assert parsed is not None
        parsed_rows.append(parsed)
        results.append(
            ProductImportRowResult(
                row_number=row_number,
                status="valid",
                product_name=parsed.name,
                store_name=parsed.store_name,
                platform=parsed.platform,
            )
        )

    return parsed_rows, results


def import_products(db: Session, csv_text: str) -> list[ProductImportRowResult]:
    """导入products；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows, results = preview_product_import(csv_text)
    parsed_by_row = {row.row_number: row for row in parsed_rows}

    # 提交阶段只导入预览通过的行，错误行保留在结果里提示，不阻断整批可用数据。
    for result in results:
        parsed = parsed_by_row.get(result.row_number)
        if parsed is None:
            continue

        store = _get_or_create_store(db, parsed.store_name, parsed.platform)
        product = Product(
            workspace_id=db.info.get("workspace_id"),
            store_id=store.id if store else None,
            name=parsed.name,
            platform=parsed.platform,
            category=parsed.category,
            price=parsed.price,
            cost=parsed.cost,
            target_audience=parsed.target_audience,
            selling_points=parsed.selling_points,
            external_product_id=parsed.external_product_id,
            platform_status=parsed.platform_status,
        )
        db.add(product)
        db.flush()
        result.status = "created"
        result.product_id = product.id

    db.commit()
    return results


def _read_csv_rows(csv_text: str) -> list[tuple[int, dict[str, str]]]:
    """读取csv行，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    reader = csv.DictReader(StringIO(csv_text.lstrip("\ufeff")))
    rows: list[tuple[int, dict[str, str]]] = []
    for index, row in enumerate(reader, start=2):
        if not row or not any((value or "").strip() for value in row.values()):
            continue
        rows.append((index, {str(key or "").strip(): (value or "").strip() for key, value in row.items()}))
    return rows


def _parse_row(row_number: int, row: dict[str, str]) -> tuple[ParsedProductRow | None, list[str]]:
    """解析行，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    errors: list[str] = []
    name = _value(row, "name", "商品名称")
    platform_value = _value(row, "platform", "平台") or Platform.DOUYIN.value
    platform = _parse_platform(platform_value, errors)
    price = _parse_decimal(_value(row, "price", "售价"), "price", errors)
    cost = _parse_decimal(_value(row, "cost", "成本"), "cost", errors)

    if not name:
        errors.append("name/商品名称 不能为空")

    if errors or platform is None or not name:
        return None, errors

    return (
        ParsedProductRow(
            row_number=row_number,
            store_name=_empty_to_none(_value(row, "store_name", "店铺")),
            platform=platform,
            name=name,
            category=_empty_to_none(_value(row, "category", "类目")),
            price=price,
            cost=cost,
            target_audience=_empty_to_none(_value(row, "target_audience", "目标人群")),
            selling_points=_split_points(_value(row, "selling_points", "卖点")),
            external_product_id=_empty_to_none(_value(row, "external_product_id", "平台商品ID")),
            platform_status=_empty_to_none(_value(row, "platform_status", "平台状态")),
        ),
        [],
    )


def _get_or_create_store(db: Session, store_name: str | None, platform: Platform) -> Store | None:
    """获取or创建店铺，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not store_name:
        return None

    # 同名店铺按平台区分，避免淘宝/抖音等多平台运营数据混到一个店铺档案里。
    statement = select(Store).where(Store.name == store_name, Store.platform == platform)
    workspace_id = db.info.get("workspace_id")
    if workspace_id is not None:
        statement = statement.where(Store.workspace_id == workspace_id)
    store = db.scalars(statement).first()
    if store is not None:
        return store

    store = Store(workspace_id=workspace_id, name=store_name, platform=platform)
    db.add(store)
    db.flush()
    return store


def _value(row: dict[str, str], *keys: str) -> str:
    """值，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value.strip()
    return ""


def _parse_platform(value: str, errors: list[str]) -> Platform | None:
    """解析平台，统一主流程中的格式、默认值和异常边界。"""
    try:
        return Platform(value)
    except ValueError:
        errors.append(f"platform/平台 不支持：{value}")
        return None


def _parse_decimal(value: str, field: str, errors: list[str]) -> Decimal | None:
    """解析小数，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        errors.append(f"{field} 必须是数字")
        return None
    if number < 0:
        errors.append(f"{field} 不能小于 0")
    return number


def _split_points(value: str) -> list[str]:
    """拆分points，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    normalized = value.replace("，", ",").replace("；", ";").replace("\n", ";")
    parts = []
    for chunk in normalized.replace(",", ";").split(";"):
        item = chunk.strip()
        if item:
            parts.append(item)
    return parts


def _empty_to_none(value: str) -> str | None:
    """空值tonone，统一主流程中的格式、默认值和异常边界。"""
    return value.strip() if value and value.strip() else None
