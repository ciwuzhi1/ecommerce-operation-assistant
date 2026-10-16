import ipaddress
import re
import socket
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx


class LinkExtractionError(RuntimeError):
    pass


@dataclass
class LinkProfile:
    name: str
    title: str | None
    price: Decimal | None
    sales_hint: str | None
    main_image: str | None
    selling_points: list[str]

    def model_payload(self) -> dict:
        """模型载荷；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        return {
            "name": self.name,
            "title": self.title,
            "price": self.price,
            "sales_hint": self.sales_hint,
            "main_image": self.main_image,
            "selling_points": self.selling_points,
        }


@dataclass(frozen=True)
class PlatformExtractionAdapter:
    name: str
    host_keywords: tuple[str, ...]
    title_separators: tuple[str, ...]
    image_meta_keys: tuple[str, ...] = ("og:image", "twitter:image")

    def matches(self, page_url: str) -> bool:
        # 只根据域名选择轻量解析规则，避免把多平台逻辑写死成某一个平台的结构。
        """matches；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        hostname = (urlparse(page_url).hostname or "").lower()
        return any(keyword in hostname for keyword in self.host_keywords)

    def clean_title(self, raw_title: str | None) -> str | None:
        """清理title；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
        title = _clean_text(raw_title)
        if not title:
            return None
        for separator in self.title_separators:
            if separator in title:
                title = title.split(separator, 1)[0].strip()
        return title or None

    def main_image(self, parser: "ProductPageParser", page_url: str) -> str | None:
        """主流程图片；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
        for key in self.image_meta_keys:
            image = _absolute_url(parser.meta.get(key), page_url)
            if image:
                return image
        return None


PLATFORM_ADAPTERS = (
    PlatformExtractionAdapter(
        name="douyin",
        host_keywords=("douyin.com", "jinritemai.com"),
        title_separators=(" - 抖音", "_抖音", "| 抖音"),
    ),
    PlatformExtractionAdapter(
        name="taobao",
        host_keywords=("taobao.com", "tmall.com"),
        title_separators=("-淘宝网", "-天猫", "_淘宝", "_天猫"),
    ),
    PlatformExtractionAdapter(
        name="pinduoduo",
        host_keywords=("yangkeduo.com", "pinduoduo.com"),
        title_separators=("-拼多多", "_拼多多"),
    ),
    PlatformExtractionAdapter(
        name="amazon",
        host_keywords=("amazon.",),
        title_separators=(": Amazon", " | Amazon"),
    ),
)

DEFAULT_ADAPTER = PlatformExtractionAdapter(
    name="generic",
    host_keywords=(),
    title_separators=("-", "_", "|", "—"),
)


class ProductPageParser(HTMLParser):
    def __init__(self) -> None:
        """初始化 ProductPageParser 的依赖与运行状态，避免执行阶段临时拼装共享资源。"""
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """处理starttag；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
        attrs_dict = {key.lower(): value for key, value in attrs if value}
        if tag.lower() == "title":
            self._in_title = True
            return

        if tag.lower() != "meta":
            return

        key = attrs_dict.get("property") or attrs_dict.get("name")
        content = attrs_dict.get("content")
        if key and content:
            self.meta[key.lower()] = content.strip()

    def handle_endtag(self, tag: str) -> None:
        """处理endtag；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        """处理数据；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
        if self._in_title:
            self.title += data


SELLING_POINT_KEYWORDS = [
    "便携",
    "控油",
    "不粘",
    "不掉色",
    "不脱妆",
    "不拔干",
    "不闷痘",
    "不假白",
    "不结块",
    "不卡粉",
    "买一送一",
    "低脂",
    "低糖",
    "保湿",
    "修护",
    "免洗",
    "冰感",
    "净肤",
    "加量",
    "包邮",
    "去屑",
    "大容量",
    "大规格",
    "天然",
    "官方",
    "小巧",
    "平价",
    "强韧",
    "快干",
    "抗皱",
    "持久",
    "持妆",
    "控温",
    "敏感肌",
    "无糖",
    "正品",
    "温和",
    "清爽",
    "滋润",
    "爆款",
    "轻薄",
    "速干",
    "防晒",
    "高颜值",
]

PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*([0-9]+(?:\.[0-9]{1,2})?)"),
    re.compile(r'"(?:salePrice|price|currentPrice)"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?'),
    re.compile(r"(?:到手价|券后价|秒杀价|活动价|售价|价格)\s*[:：]?\s*([0-9]+(?:\.[0-9]{1,2})?)"),
]

SALES_HINT_PATTERN = re.compile(
    r"((?:月销|已售|销量|售出|累计评价|评价)\s*[:：]?\s*[0-9,.万wW+＋]+)",
)


def fetch_competitor_profile(url: str) -> LinkProfile:
    """获取竞品资料；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    _validate_public_url(url)
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=12,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            },
        ) as client:
            # 仅抓取公开 HTML，不携带用户 Cookie 或平台登录态，符合“有限链接解析”的产品边界。
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LinkExtractionError(f"链接抓取失败：{exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise LinkExtractionError("当前链接返回的不是 HTML 页面")

    return extract_competitor_profile(response.text, str(response.url))


def extract_competitor_profile(html: str, page_url: str) -> LinkProfile:
    """提取竞品资料；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parser = ProductPageParser()
    # 解析上限控制在页面头部和首屏文本，避免把整站大页面当作爬虫任务处理。
    parser.feed(html[:1_000_000])
    adapter = _adapter_for_url(page_url)

    title = adapter.clean_title(
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.meta.get("title")
        or parser.title
    )
    description = _clean_text(
        parser.meta.get("og:description")
        or parser.meta.get("description")
        or parser.meta.get("twitter:description")
        or ""
    )
    main_image = adapter.main_image(parser, page_url)
    visible_text = _strip_html(html[:350_000])
    text_pool = " ".join([title or "", description or "", visible_text])

    return LinkProfile(
        name=_product_name(title, page_url),
        title=title,
        price=_extract_price(text_pool),
        sales_hint=_extract_sales_hint(text_pool),
        main_image=main_image,
        selling_points=_extract_selling_points(text_pool),
    )


def _validate_public_url(url: str) -> None:
    """校验公开链接URL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LinkExtractionError("只支持 http/https 商品链接")

    hostname = parsed.hostname
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise LinkExtractionError("不允许解析本机地址")

    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise LinkExtractionError("域名解析失败") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        # SSRF 防护：用户提交的公开链接不得解析到本机、内网、链路本地或保留地址。
        if _is_blocked_address(ip):
            raise LinkExtractionError("不允许解析内网或保留地址")


def _is_blocked_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判断blocked地址，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    blocked_networks = [
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("fc00::/7"),
        ipaddress.ip_network("fe80::/10"),
    ]
    return any(ip in network for network in blocked_networks) or ip.is_multicast or ip.is_unspecified


def _adapter_for_url(page_url: str) -> PlatformExtractionAdapter:
    """adapterforURL，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for adapter in PLATFORM_ADAPTERS:
        if adapter.matches(page_url):
            return adapter
    return DEFAULT_ADAPTER


def _product_name(title: str | None, page_url: str) -> str:
    """商品name，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if title:
        cleaned = re.split(r"[-_|—]", title, maxsplit=1)[0].strip()
        if cleaned:
            return cleaned[:80]

    hostname = urlparse(page_url).hostname or "未知竞品"
    return f"{hostname} 竞品"


def _extract_price(text: str) -> Decimal | None:
    """提取价格，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    for pattern in PRICE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            return Decimal(match.group(1)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            continue
    return None


def _extract_sales_hint(text: str) -> str | None:
    """提取saleshint，统一主流程中的格式、默认值和异常边界。"""
    match = SALES_HINT_PATTERN.search(text)
    if not match:
        return None
    return _clean_text(match.group(1))[:120]


def _extract_selling_points(text: str) -> list[str]:
    """提取sellingpoints，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    found = []
    for keyword in SELLING_POINT_KEYWORDS:
        if keyword in text and keyword not in found:
            found.append(keyword)
        if len(found) >= 8:
            break
    return found


def _absolute_url(value: str | None, page_url: str) -> str | None:
    """absoluteURL，统一主流程中的格式、默认值和异常边界。"""
    if not value:
        return None
    return urljoin(page_url, value.strip())


def _strip_html(html: str) -> str:
    """striphtml，统一主流程中的格式、默认值和异常边界。"""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return _clean_text(text) or ""


def _clean_text(value: str | None) -> str | None:
    """清理文本，统一主流程中的格式、默认值和异常边界。"""
    if not value:
        return None
    text = unescape(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None
