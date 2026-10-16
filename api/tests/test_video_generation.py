from app.models import CreativePlan, CreativePlanType
from app.services.video_generation import _video_prompt, _video_workflow


def test_video_workflow_collects_reference_subtitle_and_voiceover_fields() -> None:
    """验证“视频工作流collectsreferencesubtitleandvoiceoverfields”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    plan = CreativePlan(
        type=CreativePlanType.VIDEO_SCRIPT,
        title="demo",
        content={
            "reference_images": ["https://img.example.com/a.png"],
            "subtitle_lines": ["fast oil control", "soft matte finish"],
            "voiceover_text": "Try it before your next commute.",
            "edit_notes": "Cut on product close-up.",
        },
    )

    workflow = _video_workflow(plan)

    assert workflow["mode"] == "image_to_video"
    assert workflow["reference_images"] == ["https://img.example.com/a.png"]
    assert workflow["subtitle_lines"][0] == "fast oil control"
    assert workflow["voiceover_text"] == "Try it before your next commute."


def test_video_prompt_includes_subtitle_and_editing_context() -> None:
    """验证“视频promptincludessubtitleandediting上下文”场景，确保重构后仍满足预期业务与安全边界。"""
    # 按 Arrange、Act、Assert 组织场景，重点检查可观察状态和副作用。
    plan = CreativePlan(
        type=CreativePlanType.VIDEO_SCRIPT,
        title="demo",
        content={
            "subtitle_lines": ["oil control in 3 seconds"],
            "voiceover_text": "Tap before makeup.",
            "edit_notes": "Use quick before-after cut.",
        },
    )

    prompt = _video_prompt(plan)

    assert "Subtitle beats: oil control in 3 seconds" in prompt
    assert "Voiceover: Tap before makeup." in prompt
    assert "Editing notes: Use quick before-after cut." in prompt
