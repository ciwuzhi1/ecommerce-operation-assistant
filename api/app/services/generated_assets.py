from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreativePlan, GeneratedAsset


def create_generated_asset(
    db: Session,
    creative_plan: CreativePlan,
    asset_type: str,
    asset: dict,
    generation_job_id: int | None = None,
) -> GeneratedAsset:
    """创建生成素材；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    existing = db.scalars(
        select(GeneratedAsset).where(GeneratedAsset.url == asset["url"])
    ).first()
    if existing is not None:
        # 素材 URL 是同步去重边界，避免同一生成结果在素材库里重复出现。
        return existing

    # 只把可审核、可归因的字段提升成列，其他供应商返回信息放入 metadata 保留但不参与业务判断。
    generated_asset = GeneratedAsset(
        product_id=creative_plan.product_id,
        creative_plan_id=creative_plan.id,
        generation_job_id=generation_job_id,
        asset_type=asset_type,
        title=creative_plan.title,
        url=asset["url"],
        model=_optional_str(asset.get("model")),
        size=_optional_str(asset.get("size")),
        duration=_optional_int(asset.get("duration")),
        status=_optional_str(asset.get("status")) or "待评估",
        asset_version=_optional_int(asset.get("asset_version")) or 1,
        usage_contexts=asset.get("usage_contexts") if isinstance(asset.get("usage_contexts"), list) else [],
        rating=_optional_int(asset.get("rating")),
        tags=asset.get("tags") if isinstance(asset.get("tags"), list) else [],
        note=_optional_str(asset.get("note")),
        asset_metadata={key: value for key, value in asset.items() if key not in _asset_columns()},
    )
    db.add(generated_asset)
    return generated_asset


def sync_generated_assets_from_creative_plans(db: Session, product_id: int) -> int:
    """同步生成素材from创意plans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    creative_plans = db.scalars(
        select(CreativePlan).where(CreativePlan.product_id == product_id)
    ).all()
    created = 0

    # 兼容早期把生成结果直接塞进 creative_plan.content 的数据，迁移到统一素材库后可审核和归因。
    for creative_plan in creative_plans:
        for asset in _assets_from_content(creative_plan.content, "generated_images"):
            before = _count_assets(db, asset["url"])
            create_generated_asset(db, creative_plan, "image", asset)
            created += 1 if before == 0 else 0
        for asset in _assets_from_content(creative_plan.content, "generated_videos"):
            before = _count_assets(db, asset["url"])
            create_generated_asset(db, creative_plan, "video", asset)
            created += 1 if before == 0 else 0

    return created


def _assets_from_content(content: dict | None, key: str) -> list[dict]:
    """素材from内容，统一主流程中的格式、默认值和异常边界。"""
    value = (content or {}).get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict) and isinstance(item.get("url"), str)]


def _count_assets(db: Session, url: str) -> int:
    """统计素材，统一主流程中的格式、默认值和异常边界。"""
    return 1 if db.scalars(select(GeneratedAsset.id).where(GeneratedAsset.url == url)).first() else 0


def _asset_columns() -> set[str]:
    """素材columns，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return {
        "duration",
        "asset_version",
        "model",
        "note",
        "rating",
        "size",
        "status",
        "tags",
        "url",
        "usage_contexts",
    }


def _optional_str(value: object) -> str | None:
    """可选str，统一主流程中的格式、默认值和异常边界。"""
    return value if isinstance(value, str) and value else None


def _optional_int(value: object) -> int | None:
    """可选int，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
