import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import StringIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductSku
from app.schemas import SkuInventoryImportRowResult
from app.services.inventory import create_inventory_item_for_sku


@dataclass
class ParsedSkuInventoryRow:
    row_number: int
    product: Product
    sku_code: str
    sku_name: str
    price: Decimal | None
    cost: Decimal | None
    initial_quantity: int
    warning_threshold: int
    location: str | None


def preview_sku_inventory_import(
    db: Session,
    csv_text: str,
) -> tuple[list[ParsedSkuInventoryRow], list[SkuInventoryImportRowResult]]:
    """预览SKU库存导入；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows: list[ParsedSkuInventoryRow] = []
    results: list[SkuInventoryImportRowResult] = []

    # SKU 库存导入同样先预览，避免错误库存直接写入并影响预警和投放节奏。
    for row_number, row in _read_csv_rows(csv_text):
        parsed, errors, product_name, sku_code, sku_name = _parse_row(db, row_number, row)
        if errors:
            results.append(
                SkuInventoryImportRowResult(
                    row_number=row_number,
                    status="error",
                    errors=errors,
                    product_name=product_name,
                    sku_code=sku_code,
                    sku_name=sku_name,
                )
            )
            continue

        assert parsed is not None
        parsed_rows.append(parsed)
        results.append(
            SkuInventoryImportRowResult(
                row_number=row_number,
                status="valid",
                product_id=parsed.product.id,
                product_name=parsed.product.name,
                sku_code=parsed.sku_code,
                sku_name=parsed.sku_name,
            )
        )

    return parsed_rows, results


def import_sku_inventory(db: Session, csv_text: str) -> list[SkuInventoryImportRowResult]:
    """导入SKU库存；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed_rows, results = preview_sku_inventory_import(db, csv_text)
    parsed_by_row = {row.row_number: row for row in parsed_rows}

    # 导入 SKU 时通过库存服务写初始库存流水，保持手工录入和表格导入的库存口径一致。
    for result in results:
        parsed = parsed_by_row.get(result.row_number)
        if parsed is None:
            continue

        sku = ProductSku(
            product_id=parsed.product.id,
            sku_code=parsed.sku_code,
            name=parsed.sku_name,
            price=parsed.price,
            cost=parsed.cost,
        )
        db.add(sku)
        db.flush()
        create_inventory_item_for_sku(
            db,
            sku,
            initial_quantity=parsed.initial_quantity,
            warning_threshold=parsed.warning_threshold,
            location=parsed.location,
            operator_name="CSV 导入",
        )
        result.status = "created"
        result.sku_id = sku.id
        result.product_id = parsed.product.id

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


def _parse_row(
    db: Session,
    row_number: int,
    row: dict[str, str],
) -> tuple[ParsedSkuInventoryRow | None, list[str], str | None, str | None, str | None]:
    """解析行，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    errors: list[str] = []
    product_name = _value(row, "product_name", "商品名称")
    sku_code = _value(row, "sku_code", "SKU编码")
    sku_name = _value(row, "sku_name", "规格名称")

    if not product_name:
        errors.append("product_name/商品名称 不能为空")
        product = None
    else:
        statement = select(Product).where(Product.name == product_name)
        workspace_id = db.info.get("workspace_id")
        if workspace_id is not None:
            statement = statement.where(Product.workspace_id == workspace_id)
        product = db.scalars(statement).first()
        if product is None:
            errors.append(f"找不到商品：{product_name}")

    if not sku_code:
        errors.append("sku_code/SKU编码 不能为空")
    if not sku_name:
        errors.append("sku_name/规格名称 不能为空")

    if product is not None and sku_code:
        # 同一商品下 SKU 编码必须唯一，避免库存流水写到错误规格。
        existing_sku = db.scalars(
            select(ProductSku).where(ProductSku.product_id == product.id, ProductSku.sku_code == sku_code)
        ).first()
        if existing_sku is not None:
            errors.append(f"商品 {product_name} 已存在 SKU：{sku_code}")

    price = _parse_decimal(_value(row, "price", "售价"), "price", errors)
    cost = _parse_decimal(_value(row, "cost", "成本"), "cost", errors)
    initial_quantity = _parse_int(_value(row, "initial_quantity", "初始库存"), "initial_quantity", errors)
    warning_threshold = _parse_int(_value(row, "warning_threshold", "预警线"), "warning_threshold", errors)

    if errors or product is None or not sku_code or not sku_name:
        return None, errors, product_name or None, sku_code or None, sku_name or None

    return (
        ParsedSkuInventoryRow(
            row_number=row_number,
            product=product,
            sku_code=sku_code,
            sku_name=sku_name,
            price=price,
            cost=cost,
            initial_quantity=initial_quantity,
            warning_threshold=warning_threshold,
            location=_empty_to_none(_value(row, "location", "仓位")),
        ),
        [],
        product_name,
        sku_code,
        sku_name,
    )


def _value(row: dict[str, str], *keys: str) -> str:
    """值，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value.strip()
    return ""


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


def _parse_int(value: str, field: str, errors: list[str]) -> int:
    """解析int，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not value:
        return 0
    try:
        number = int(value)
    except ValueError:
        errors.append(f"{field} 必须是整数")
        return 0
    if number < 0:
        errors.append(f"{field} 不能小于 0")
    return number


def _empty_to_none(value: str) -> str | None:
    """空值tonone，统一主流程中的格式、默认值和异常边界。"""
    return value.strip() if value and value.strip() else None
