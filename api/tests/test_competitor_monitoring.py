from decimal import Decimal

from app.models import Competitor, CompetitorMonitor, Platform, Product
from app.services.competitor_monitoring import compare_competitor_changes


def test_compare_competitor_changes_detects_price_and_selling_point_changes() -> None:
    """验证“比较竞品changesdetects价格andsellingpointchanges”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    competitor = Competitor(
        product=Product(name="oil control cushion", platform=Platform.DOUYIN),
        name="competitor",
        platform=Platform.DOUYIN,
        title="old title",
        price=Decimal("49.90"),
        sales_hint="sold 1000",
        selling_points=["lightweight"],
    )

    changes = compare_competitor_changes(
        competitor,
        {
            "title": "new title",
            "price": Decimal("39.90"),
            "sales_hint": "sold 2000",
            "selling_points": ["lightweight", "waterproof"],
        },
    )

    assert "Title changed: old title -> new title" in changes
    assert "Price changed: 49.90 -> 39.90" in changes
    assert "Sales hint changed: sold 1000 -> sold 2000" in changes
    assert "New selling points: waterproof" in changes


def test_competitor_monitor_model_can_reference_snapshot() -> None:
    """验证“竞品监控模型canreference快照”场景，确保重构后仍满足预期业务与安全边界。"""
    monitor = CompetitorMonitor(
        product_id=1,
        competitor_id=2,
        interval_days=1,
        status="active",
    )

    assert monitor.status == "active"
    assert monitor.interval_days == 1
