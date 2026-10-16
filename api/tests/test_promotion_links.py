from app.models import Platform, Product
from app.services.promotion_links import build_promotion_link_payloads, enrich_tracking_fields


def test_build_promotion_links_uses_product_url_when_present() -> None:
    """验证“构建推广linksuses商品URLwhenpresent”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    product = Product(
        name="oil control cushion",
        platform=Platform.DOUYIN,
        product_url="https://shop.example.com/item/1",
    )

    links = build_promotion_link_payloads(product)

    assert links[0]["url"] == "https://shop.example.com/item/1"
    assert links[1]["link_type"] == "tracking"
    assert "utm_campaign=short_video" in str(links[1]["url"])
    assert "utm_campaign=main_image" in str(links[2]["url"])


def test_build_promotion_links_falls_back_to_platform_search_url() -> None:
    """验证“构建推广linksfallsbackto平台searchURL”场景，确保重构后仍满足预期业务与安全边界。"""
    product = Product(name="oil control cushion", platform=Platform.TAOBAO)

    links = build_promotion_link_payloads(product)

    assert str(links[0]["url"]).startswith("https://s.taobao.com/search?q=")
    assert links[0]["note"]


def test_enrich_tracking_fields_adds_short_code_and_tracking_url() -> None:
    """验证“补充追踪fieldsadds短链codeand追踪URL”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    payload = {
        "label": "short video tracking link",
        "url": "https://shop.example.com/item/1",
        "link_type": "tracking",
        "scenario": "short_video",
        "status": "active",
        "note": None,
    }

    enriched = enrich_tracking_fields(
        payload,
        product_id=12,
        short_code="abc123",
        tracking_code="track-001",
    )

    assert enriched["short_code"] == "abc123"
    assert enriched["tracking_code"] == "track-001"
    assert "utm_campaign=short_video" in str(enriched["tracking_url"])
    assert "eo_tracking_code=track-001" in str(enriched["tracking_url"])
