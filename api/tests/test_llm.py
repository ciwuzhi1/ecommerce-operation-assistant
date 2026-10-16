"""T-02 统一文本调用的单元测试（不发起真实网络请求）。"""
from app.services.llm import LLMNotConfiguredError, _chat_completion_url, _extract_message_content


def test_chat_completion_url_accepts_base_url() -> None:
    """给定基础地址，应追加 /chat/completions。"""
    assert (
        _chat_completion_url("https://api.deepseek.com")
        == "https://api.deepseek.com/chat/completions"
    )


def test_chat_completion_url_accepts_full_endpoint() -> None:
    """给定已含补全路径的地址，不应重复追加。"""
    assert (
        _chat_completion_url("https://api.deepseek.com/chat/completions")
        == "https://api.deepseek.com/chat/completions"
    )


def test_extract_message_content() -> None:
    """给定标准响应，应取出首条消息内容。"""
    response_json = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    assert _extract_message_content(response_json) == '{"ok": true}'


def test_extract_message_content_rejects_missing_choices() -> None:
    """给定缺少 choices 的响应，应抛 LLMResponseError。"""
    import pytest

    from app.services.llm import LLMResponseError

    with pytest.raises(LLMResponseError):
        _extract_message_content({})


def test_extract_message_content_rejects_empty_content() -> None:
    """给定空内容，应抛 LLMResponseError。"""
    import pytest

    from app.services.llm import LLMResponseError

    with pytest.raises(LLMResponseError):
        _extract_message_content({"choices": [{"message": {"content": "   "}}]})


def test_not_configured_raises_before_network() -> None:
    """给定未配置的模型，应在发起请求前抛出未配置错误（PRD FR-05）。"""
    import pytest

    from app.services.llm import create_json_chat_completion

    class _Unconfigured:
        llm_base_url = None
        llm_api_key = None
        llm_model = None

    with pytest.raises(LLMNotConfiguredError):
        create_json_chat_completion([], settings=_Unconfigured())
