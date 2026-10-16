from secrets import token_urlsafe
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from app.models import Product


def build_promotion_link_payloads(product: Product) -> list[dict[str, str | None]]:
    """构建推广链接payloads；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    base_url = product.product_url or _platform_search_url(product)
    # 默认生成几类承接入口，帮助后续按素材/场景归因；不会自动创建广告计划。
    payloads = [
        {
            "label": "商品承接页",
            "url": base_url,
            "link_type": "landing",
            "scenario": "自然流量/直播口播",
            "status": "active",
            "note": "优先用于商品卡、直播间口播和私域转发，承接用户直接下单。",
        },
        {
            "label": "短视频投放链接",
            "url": _with_tracking(base_url, "short_video"),
            "link_type": "tracking",
            "scenario": "短视频投放",
            "status": "active",
            "note": "用于信息流短视频素材，后续可按素材版本继续细分 utm_content。",
        },
        {
            "label": "主图测试链接",
            "url": _with_tracking(base_url, "main_image"),
            "link_type": "tracking",
            "scenario": "主图 A/B 测试",
            "status": "active",
            "note": "用于主图方向测试，便于和素材评分、CTR、ROI 做回看。",
        },
    ]

    if not product.product_url:
        payloads[0]["note"] = "当前商品未填写商品链接，系统先生成平台搜索链接作为临时承接入口。"

    return payloads


def enrich_tracking_fields(
    payload: dict[str, str | None],
    *,
    product_id: int,
    short_code: str | None = None,
    tracking_code: str | None = None,
) -> dict[str, str | None]:
    """补充追踪fields；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    next_payload = dict(payload)
    link_type = next_payload.get("link_type") or "landing"
    campaign = _campaign_from_payload(next_payload)
    code = tracking_code or make_tracking_code(product_id, campaign)

    # 自有 tracking_code 和 UTM 同时写入，既方便系统内回填，也兼容平台/三方报表导出。
    next_payload["tracking_code"] = code
    next_payload["short_code"] = short_code or make_short_code()
    next_payload["tracking_url"] = _with_tracking(
        next_payload["url"] or "",
        campaign,
        tracking_code=code,
        content=next_payload.get("label"),
        medium="short_link" if link_type == "tracking" else "ops_link",
    )
    return next_payload


def make_short_code() -> str:
    """生成短链code；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    return token_urlsafe(6).replace("-", "").replace("_", "")[:8]


def make_tracking_code(product_id: int, campaign: str) -> str:
    """生成追踪code；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    return f"p{product_id}-{campaign}-{token_urlsafe(6).replace('-', '').replace('_', '')[:8]}"


def _platform_search_url(product: Product) -> str:
    # 没有商品 URL 时退到平台搜索页，只作为临时承接入口，运营仍应补真实商品链接。
    """平台searchURL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    keyword = quote(product.name)
    if product.platform == "taobao":
        return f"https://s.taobao.com/search?q={keyword}"
    if product.platform == "tmall":
        return f"https://list.tmall.com/search_product.htm?q={keyword}"
    if product.platform == "amazon":
        return f"https://www.amazon.com/s?k={keyword}"
    if product.platform == "tiktok_shop":
        return f"https://www.tiktok.com/search?q={keyword}"
    if product.platform == "pinduoduo":
        return f"https://mobile.yangkeduo.com/search_result.html?search_key={keyword}"
    return f"https://www.douyin.com/search/{keyword}"


def _campaign_from_payload(payload: dict[str, str | None]) -> str:
    """campaignfrom载荷，统一主流程中的格式、默认值和异常边界。"""
    scenario = payload.get("scenario") or payload.get("label") or "general"
    parsed_url = urlparse(payload.get("url") or "")
    query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    if query.get("utm_campaign"):
        return _slug(query["utm_campaign"])
    return _slug(scenario)


def _slug(value: str) -> str:
    """slug，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    result = []
    for char in value.lower():
        if char.isascii() and char.isalnum():
            result.append(char)
        elif char in {"-", "_"}:
            result.append("_")
        elif result and result[-1] != "_":
            result.append("_")
    slug = "".join(result).strip("_")
    return slug or "general"


def _with_tracking(
    url: str,
    campaign: str,
    *,
    tracking_code: str | None = None,
    content: str | None = None,
    medium: str = "ai_ops",
) -> str:
    """with追踪，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    # 保留原始 query 并追加归因参数，避免覆盖商家已有的活动参数。
    query.update(
        {
            "utm_source": "ecommerce_operation_assistant",
            "utm_medium": medium,
            "utm_campaign": campaign,
        }
    )
    if content:
        query["utm_content"] = _slug(content)
    if tracking_code:
        query["eo_tracking_code"] = tracking_code
    return urlunparse(parsed._replace(query=urlencode(query)))
