from datetime import date, datetime
from decimal import Decimal

from app.models import AdExperiment, PerformanceRecord, Product
from app.services.review import generate_rule_based_review


def test_rule_based_review_mentions_linked_ad_experiment() -> None:
    """验证“rulebased审核mentionslinked投放实验”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    product = Product(id=1, name="控油气垫", selling_points=["控油持妆"])
    experiment = AdExperiment(
        id=1,
        product_id=1,
        name="小预算素材承接实验",
        objective="验证素材和承接页稳定性",
        status="active",
    )
    record = PerformanceRecord(
        product_id=1,
        ad_experiment_id=1,
        period_start=date(2026, 6, 4),
        period_end=date(2026, 6, 4),
        impressions=6800,
        clicks=388,
        ctr=Decimal("0.0571"),
        conversions=24,
        conversion_rate=Decimal("0.0619"),
        spend=Decimal("260.00"),
        revenue=Decimal("957.60"),
        roi=Decimal("3.6831"),
    )
    record.created_at = datetime(2026, 6, 4, 12, 0, 0)
    record.ad_experiment = experiment
    product.performance_records = [record]

    report = generate_rule_based_review(product)

    assert any("小预算素材承接实验" in insight for insight in report["insights"])
    assert any("小预算素材承接实验" in action for action in report["next_actions"])
