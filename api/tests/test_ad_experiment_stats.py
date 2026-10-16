from datetime import date
from decimal import Decimal

from app.models import AdExperiment, PerformanceRecord, Product
from app.services.ad_experiment_stats import build_ad_experiment_dashboard


def test_build_ad_experiment_dashboard_summarizes_records_by_experiment() -> None:
    """验证“构建投放实验看板summarizesrecordsby实验”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    scale_experiment = AdExperiment(
        id=1,
        product_id=1,
        name="放量观察实验",
        objective="验证高 ROI 素材",
        status="active",
        daily_budget=Decimal("300.00"),
    )
    pause_experiment = AdExperiment(
        id=2,
        product_id=1,
        name="低效承接实验",
        objective="验证链接承接",
        status="active",
        daily_budget=Decimal("200.00"),
    )
    product = Product(id=1, name="控油气垫")
    product.ad_experiments = [scale_experiment, pause_experiment]
    product.performance_records = [
        PerformanceRecord(
            product_id=1,
            ad_experiment_id=1,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 1),
            impressions=1000,
            clicks=60,
            conversions=10,
            spend=Decimal("100"),
            revenue=Decimal("420"),
        ),
        PerformanceRecord(
            product_id=1,
            ad_experiment_id=1,
            period_start=date(2026, 5, 2),
            period_end=date(2026, 5, 2),
            impressions=1000,
            clicks=50,
            conversions=8,
            spend=Decimal("100"),
            revenue=Decimal("360"),
        ),
        PerformanceRecord(
            product_id=1,
            ad_experiment_id=2,
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 1),
            impressions=800,
            clicks=16,
            conversions=1,
            spend=Decimal("80"),
            revenue=Decimal("40"),
        ),
    ]

    dashboard = build_ad_experiment_dashboard(product)

    assert dashboard["total_experiments"] == 2
    assert dashboard["active_experiments"] == 2
    assert dashboard["measured_experiments"] == 2
    assert dashboard["overall_roi"] == Decimal("820") / Decimal("280")
    assert dashboard["best_experiment"]["ad_experiment_id"] == 1
    assert dashboard["best_experiment"]["decision"] == "scale"
    assert dashboard["rows"][0]["period_start"] == date(2026, 5, 1)
    assert dashboard["rows"][0]["period_end"] == date(2026, 5, 2)
    assert dashboard["rows"][1]["decision"] == "pause"


def test_build_ad_experiment_dashboard_marks_unmeasured_experiment() -> None:
    """验证“构建投放实验看板marksunmeasured实验”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    experiment = AdExperiment(
        id=1,
        product_id=1,
        name="待回填实验",
        objective="验证新素材",
        status="draft",
    )
    product = Product(id=1, name="控油气垫")
    product.ad_experiments = [experiment]
    product.performance_records = []

    dashboard = build_ad_experiment_dashboard(product)

    assert dashboard["measured_experiments"] == 0
    assert dashboard["overall_roi"] is None
    assert dashboard["best_experiment"] is None
    assert dashboard["rows"][0]["decision"] == "needs_data"
