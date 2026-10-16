from decimal import Decimal

from app.models import GeneratedAsset, PerformanceRecord, Product, PromotionLink
from app.services.ad_experiments import build_ad_experiment_payload


def test_build_ad_experiment_prefers_best_roi_asset_and_link() -> None:
    """验证“构建投放实验prefers最佳roi素材and链接”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    weak_asset = GeneratedAsset(
        id=1,
        product_id=1,
        creative_plan_id=1,
        asset_type="image",
        title="普通主图",
        url="/uploads/weak.png",
        status="待评价",
    )
    strong_asset = GeneratedAsset(
        id=2,
        product_id=1,
        creative_plan_id=1,
        asset_type="image",
        title="高 ROI 主图",
        url="/uploads/strong.png",
        status="可投放",
    )
    weak_link = PromotionLink(id=1, product_id=1, label="普通链接", url="https://example.com/a")
    strong_link = PromotionLink(id=2, product_id=1, label="高 ROI 链接", url="https://example.com/b")
    product = Product(
        id=1,
        name="控油气垫",
        target_audience="油皮通勤人群",
        selling_points=["控油持妆"],
    )
    product.generated_assets = [weak_asset, strong_asset]
    product.promotion_links = [weak_link, strong_link]
    product.performance_records = [
        PerformanceRecord(
            product_id=1,
            generated_asset_id=1,
            promotion_link_id=1,
            impressions=1000,
            clicks=40,
            spend=Decimal("100"),
            revenue=Decimal("120"),
        ),
        PerformanceRecord(
            product_id=1,
            generated_asset_id=2,
            promotion_link_id=2,
            impressions=1000,
            clicks=70,
            spend=Decimal("100"),
            revenue=Decimal("420"),
        ),
    ]

    payload = build_ad_experiment_payload(product)

    assert payload["generated_asset_id"] == 2
    assert payload["promotion_link_id"] == 2
    assert payload["daily_budget"] == Decimal("300.00")
    assert payload["status"] == "draft"
    assert "人工确认" in payload["note"]
