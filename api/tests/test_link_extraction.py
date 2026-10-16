from decimal import Decimal
from ipaddress import ip_address

from app.services.link_extraction import _is_blocked_address, extract_competitor_profile


def test_extract_competitor_profile_from_meta_and_text() -> None:
    """验证“提取竞品资料frommetaand文本”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    html = """
    <html>
      <head>
        <title>轻薄控油气垫 - 官方旗舰店</title>
        <meta property="og:title" content="轻薄控油气垫 便携不卡粉">
        <meta name="description" content="月销1万+，主打控油、便携、不脱妆">
        <meta property="og:image" content="/cover.jpg">
      </head>
      <body>到手价 ¥39.90 已售2万+ 清爽持妆</body>
    </html>
    """

    profile = extract_competitor_profile(html, "https://example.com/item/1")

    assert profile.name == "轻薄控油气垫 便携不卡粉"
    assert profile.title == "轻薄控油气垫 便携不卡粉"
    assert profile.price == Decimal("39.90")
    assert profile.sales_hint == "月销1万+"
    assert profile.main_image == "https://example.com/cover.jpg"
    assert "控油" in profile.selling_points
    assert "便携" in profile.selling_points
    assert "不卡粉" in profile.selling_points


def test_link_extraction_blocks_risky_local_addresses() -> None:
    """验证“链接extractionblocksriskylocaladdresses”场景，确保重构后仍满足预期业务与安全边界。"""
    assert _is_blocked_address(ip_address("127.0.0.1"))
    assert _is_blocked_address(ip_address("10.1.2.3"))
    assert _is_blocked_address(ip_address("172.16.1.2"))
    assert _is_blocked_address(ip_address("192.168.1.2"))
    assert _is_blocked_address(ip_address("::1"))


def test_link_extraction_allows_development_proxy_address() -> None:
    """验证“链接extractionallowsdevelopmentproxy地址”场景，确保重构后仍满足预期业务与安全边界。"""
    assert not _is_blocked_address(ip_address("198.18.0.24"))


def test_platform_adapter_cleans_taobao_title() -> None:
    """验证“平台adaptercleanstaobaotitle”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    html = """
    <html>
      <head>
        <title>Lightweight foundation-Taobao</title>
        <meta property="og:title" content="Lightweight foundation-淘宝网">
        <meta property="og:image" content="https://img.example.com/cover.jpg">
      </head>
      <body>price: 59.90</body>
    </html>
    """

    profile = extract_competitor_profile(html, "https://item.taobao.com/item.htm?id=1")

    assert profile.title == "Lightweight foundation"
    assert profile.name == "Lightweight foundation"
    assert profile.main_image == "https://img.example.com/cover.jpg"
