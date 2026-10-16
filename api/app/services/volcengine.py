from datetime import UTC, datetime
import hashlib
import hmac
from urllib.parse import urlencode, urlparse


class VolcengineCredentialsError(RuntimeError):
    pass


def parse_access_key_pair(api_key: str | None) -> tuple[str, str]:
    """解析访问keypair；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    if not api_key or ":" not in api_key:
        raise VolcengineCredentialsError(
            "Jimeng provider expects api_key in 'VOLC_ACCESS_KEY:VOLC_SECRET_KEY' format."
        )
    access_key, secret_key = api_key.split(":", 1)
    access_key = access_key.strip()
    secret_key = secret_key.strip()
    if not access_key or not secret_key:
        raise VolcengineCredentialsError(
            "Jimeng provider expects both Volcengine access key and secret key."
        )
    return access_key, secret_key


def signed_json_headers(
    *,
    access_key: str,
    secret_key: str,
    method: str,
    url: str,
    query: dict[str, str],
    body: bytes,
    region: str = "cn-north-1",
    service: str = "cv",
    request_time: datetime | None = None,
) -> dict[str, str]:
    """签名JSONheaders；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    request_time = request_time or datetime.now(UTC)
    x_date = request_time.strftime("%Y%m%dT%H%M%SZ")
    short_date = request_time.strftime("%Y%m%d")
    parsed = urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    canonical_query = urlencode(sorted(query.items()))
    payload_hash = hashlib.sha256(body).hexdigest()
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = (
        "content-type:application/json\n"
        f"host:{host}\n"
        f"x-content-sha256:{payload_hash}\n"
        f"x-date:{x_date}\n"
    )
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri,
            canonical_query,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signature = _signing_signature(secret_key, short_date, region, service, string_to_sign)

    return {
        "Authorization": (
            "HMAC-SHA256 "
            f"Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "Content-Type": "application/json",
        "Host": host,
        "X-Content-Sha256": payload_hash,
        "X-Date": x_date,
    }


def _signing_signature(
    secret_key: str,
    short_date: str,
    region: str,
    service: str,
    string_to_sign: str,
) -> str:
    """signingsignature，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    key = _hmac(secret_key.encode("utf-8"), short_date)
    key = _hmac(key, region)
    key = _hmac(key, service)
    key = _hmac(key, "request")
    return hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    """HMAC，统一主流程中的格式、默认值和异常边界。"""
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
