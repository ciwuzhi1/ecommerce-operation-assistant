import json
from types import SimpleNamespace

import httpx
import pytest

from app.services import image_generation as image
from app.services import video_generation as video


@pytest.mark.parametrize("duration,frames", [(5, 121), (10, 241)])
def test_video_submit_contract(monkeypatch, duration, frames):
    captured = {}
    def post(**kwargs):
        captured.update(kwargs)
        return {"code": 10000, "data": {"task_id": "test-task"}}
    monkeypatch.setattr(video, "_post_jimeng_video_json", post)
    settings = SimpleNamespace(video_model="jimeng_t2v_v30", video_duration=duration, video_size="1280*720")
    assert video.create_jimeng_video_task("低糖燕麦饼干特写", settings) == "test-task"
    assert captured["action"] == "CVSync2AsyncSubmitTask"
    assert captured["payload"] == {
        "req_key": "jimeng_t2v_v30", "prompt": "低糖燕麦饼干特写",
        "seed": -1, "frames": frames, "aspect_ratio": "16:9",
    }


@pytest.mark.parametrize("duration", [0, 2, 6, 30])
def test_video_rejects_invalid_duration(duration):
    with pytest.raises(video.VideoGenerationError):
        video._duration_to_frames(duration)


def test_text_to_video_rejects_reference_images():
    settings = SimpleNamespace(video_model="jimeng_t2v_v30", video_duration=5, video_size="1280*720")
    with pytest.raises(video.VideoGenerationError, match="文生视频"):
        video.create_jimeng_video_task("商品", settings, {"reference_images": ["https://example.com/a.png"]})


def test_image_submit_and_query_contract(monkeypatch):
    calls = []
    def post(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "CVSync2AsyncSubmitTask":
            return {"code": 10000, "data": {"task_id": "image-task"}}
        return {"code": 10000, "data": {"status": "done", "image_urls": ["https://example.com/a.png"]}}
    monkeypatch.setattr(image, "_post_jimeng_json", post)
    settings = SimpleNamespace(image_model="jimeng_t2i_v30", image_size="1024*1024",
                               image_poll_max_attempts=1, image_poll_interval_seconds=5)
    task_id = image._create_jimeng_image_task("低糖燕麦饼干", settings)
    result = image._poll_jimeng_image_task(task_id, settings)
    assert calls[0]["payload"]["req_key"] == "jimeng_t2i_v30"
    assert calls[0]["payload"]["width"] == 1024
    assert calls[0]["payload"]["height"] == 1024
    assert calls[1]["action"] == "CVSync2AsyncGetResult"
    assert json.loads(calls[1]["payload"]["req_json"]) == {"return_url": True}
    assert image._extract_jimeng_image_url(result) == "https://example.com/a.png"


@pytest.mark.parametrize("module,method,prefix,error", [
    (image, "_post_jimeng_json", "image", image.ImageGenerationError),
    (video, "_post_jimeng_video_json", "video", video.VideoGenerationError),
])
@pytest.mark.parametrize("body", [
    {"code": 50413, "data": None, "message": "Post Text Risk Not Pass"},
    {"code": 50413, "data": {"status": "done"}},
    {"data": {"status": "done"}},
])
def test_outer_code_checked_before_data(monkeypatch, module, method, prefix, error, body):
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(module.httpx, "Client", Client)
    settings = SimpleNamespace(**{
        prefix + "_api_key": "test-ak:test-sk",
        prefix + "_base_url": "https://visual.volcengineapi.com",
    })
    with pytest.raises(error):
        getattr(module, method)(settings=settings, action="CVSync2AsyncGetResult", payload={}, timeout=1)
