import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import Product, ProductDiagnosis
from app.services.llm import (
    LLMNotConfiguredError,
    LLMResponseError,
    create_json_chat_completion,
)


class MainImagePlanOutput(BaseModel):
    title: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    layout: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    sub_headline: str = Field(min_length=1)
    visual_focus: str = Field(min_length=1)
    proof_points: list[str] = Field(default_factory=list)
    suitable_audience: str = Field(min_length=1)
    image_prompt: str = Field(min_length=1)


class MainImagePlansOutput(BaseModel):
    plans: list[MainImagePlanOutput] = Field(min_length=3, max_length=6)


class VideoScriptSceneOutput(BaseModel):
    shot: str = Field(min_length=1)
    visual: str = Field(min_length=1)
    voiceover: str = Field(min_length=1)


class VideoScriptPlanOutput(BaseModel):
    title: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    duration_seconds: int = Field(ge=15, le=60)
    scenes: list[VideoScriptSceneOutput] = Field(min_length=4, max_length=8)
    selling_point_proof: list[str] = Field(default_factory=list)
    cta: str = Field(min_length=1)
    video_prompt: str = Field(min_length=1)


class VideoScriptPlansOutput(BaseModel):
    scripts: list[VideoScriptPlanOutput] = Field(min_length=3, max_length=5)


def generate_main_image_plans(product: Product, diagnosis: ProductDiagnosis | None) -> list[dict]:
    """生成主流程图片plans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    try:
        return generate_llm_main_image_plans(product, diagnosis)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 主图方案是运营工作流入口，模型不可用时仍返回可编辑的规则方案，避免流程停在空白页。
        fallback_plans = generate_rule_based_main_image_plans(product, diagnosis)
        for plan in fallback_plans:
            plan["source"] = "rules"
            plan["fallback_reason"] = str(exc)
        return fallback_plans


def generate_llm_main_image_plans(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict[str, Any]]:
    """生成llm主流程图片plans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed, raw_response = create_json_chat_completion(
        _build_main_image_messages(product, diagnosis),
        max_tokens=2600,
        temperature=0.35,
    )
    output = MainImagePlansOutput.model_validate(parsed)
    usage = raw_response.get("usage", {})
    model = raw_response.get("model")

    plans: list[dict[str, Any]] = []
    for plan in output.plans:
        payload = plan.model_dump()
        # 保存模型和用量用于质量复盘；方案内容仍是结构化字段，便于人工改文案和布局。
        payload["source"] = "llm"
        payload["llm_model"] = model
        payload["llm_usage"] = usage
        plans.append(payload)
    return plans


def _build_main_image_messages(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict[str, str]]:
    """构建主流程图片消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是一个资深电商主图策划和投放素材策略专家。"
                "你擅长把商品卖点、竞品差异和用户痛点转成设计师可执行的主图方案。"
                "你必须只输出合法 json，不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请生成 4 个商品主图方案，用于电商详情页首屏、搜索列表或信息流素材测试。"
                "输出 json 必须严格符合以下结构：\n"
                "{\n"
                '  "plans": [\n'
                "    {\n"
                '      "title": "方案标题",\n'
                '      "angle": "这个方案的测试角度",\n'
                '      "layout": "画面布局，说明商品、人物、文案、标签分别放哪里",\n'
                '      "headline": "主文案，尽量短",\n'
                '      "sub_headline": "副文案",\n'
                '      "visual_focus": "视觉重点和拍摄/设计要求",\n'
                '      "proof_points": ["证明点1", "证明点2"],\n'
                '      "suitable_audience": "适合的人群或场景",\n'
                '      "image_prompt": "后续给图片生成模型用的中文画面提示词"\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- 4 个方案角度必须明显不同，避免同质化。\n"
                "- 主文案适合放在主图上，不要太长，不要堆砌抽象形容词。\n"
                "- 布局和视觉重点必须可交给设计师或图片生成模型执行。\n"
                "- 不要使用夸大、绝对化、违规医疗功效或无法证明的表达。\n\n"
                f"商品、竞品和诊断信息 json：{_creative_context_payload(product, diagnosis)}"
            ),
        },
    ]


def generate_rule_based_main_image_plans(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict]:
    """生成rulebased主流程图片plans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    focus_points = _focus_points(product, diagnosis)
    audience = product.target_audience or "目标用户"
    category = product.category or "商品"
    price_text = f"{product.price}" if product.price is not None else "当前售价"

    templates = [
        {
            "title": f"{focus_points[0]}场景首屏",
            "angle": "用具体使用场景承接用户需求，适合作为第一张点击测试图。",
            "layout": "左侧放商品清晰主体，右侧放大场景文案；底部用 2-3 个小标签补充利益点。",
            "headline": f"{focus_points[0]}，{audience}也能轻松用",
            "sub_headline": f"{category} · 到手价 {price_text}",
            "visual_focus": f"突出“{focus_points[0]}”对应的使用结果，画面保持干净、明亮、可快速识别。",
            "proof_points": _proof_points(product, focus_points[:2]),
            "suitable_audience": audience,
        },
        {
            "title": "竞品对比利益点",
            "angle": "把用户最关心的差异点做成一眼能懂的对比，适合测试转化效率。",
            "layout": "上方一句强利益标题，中间用左右对比结构，下方放商品和价格利益点。",
            "headline": f"别只看同款，重点看{focus_points[0]}",
            "sub_headline": "把差异点放在首屏，减少用户理解成本",
            "visual_focus": "用对比表、勾叉符号或前后效果承接差异化表达。",
            "proof_points": _proof_points(product, focus_points),
            "suitable_audience": audience,
        },
        {
            "title": "痛点结果型主图",
            "angle": "先点出用户顾虑，再给出商品结果，适合投放素材和搜索场景。",
            "layout": "顶部痛点短句，中间商品大图，右下角用结果型标签做强化。",
            "headline": f"想要{focus_points[0]}，先看这一款",
            "sub_headline": _diagnosis_pain_point(diagnosis),
            "visual_focus": "避免堆字，用 1 个主结果 + 2 个辅助卖点完成表达。",
            "proof_points": _proof_points(product, focus_points[:3]),
            "suitable_audience": audience,
        },
        {
            "title": "价格理由型主图",
            "angle": "当价格低于或接近竞品时，用价值组合解释为什么值得点。",
            "layout": "价格/权益放左上角，商品主体居中，卖点标签围绕主体分布。",
            "headline": f"{price_text} 先试这一套",
            "sub_headline": f"{'、'.join(focus_points[:3])}",
            "visual_focus": "价格信息要醒目，但不要压过商品主体和核心卖点。",
            "proof_points": _proof_points(product, focus_points),
            "suitable_audience": audience,
        },
    ]

    return templates


def _creative_context_payload(product: Product, diagnosis: ProductDiagnosis | None) -> str:
    # Prompt 只包含商品、竞品和诊断上下文，不注入平台账号授权信息或敏感配置。
    """创意上下文载荷，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    payload = {
        "product": {
            "name": product.name,
            "platform": product.platform,
            "category": product.category,
            "price": str(product.price) if product.price is not None else None,
            "cost": str(product.cost) if product.cost is not None else None,
            "target_audience": product.target_audience,
            "selling_points": product.selling_points,
            "product_url": product.product_url,
            "images": product.images,
        },
        "competitors": [
            {
                "name": competitor.name,
                "platform": competitor.platform,
                "price": str(competitor.price) if competitor.price is not None else None,
                "sales_hint": competitor.sales_hint,
                "title": competitor.title,
                "selling_points": competitor.selling_points,
                "review_keywords": competitor.review_keywords,
            }
            for competitor in product.competitors
        ],
        "diagnosis": None
        if diagnosis is None
        else {
            "source": diagnosis.source,
            "positioning": diagnosis.positioning,
            "price_band": diagnosis.price_band,
            "audience_insights": diagnosis.audience_insights,
            "pain_points": diagnosis.pain_points,
            "selling_point_analysis": diagnosis.selling_point_analysis,
            "risks": diagnosis.risks,
            "recommendations": diagnosis.recommendations,
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_video_script_plans(product: Product, diagnosis: ProductDiagnosis | None) -> list[dict]:
    """生成视频scriptplans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    try:
        return generate_llm_video_script_plans(product, diagnosis)
    except (LLMNotConfiguredError, LLMResponseError, ValidationError) as exc:
        # 视频脚本需要能被运营和拍摄人员继续编辑，规则兜底也保持分镜结构。
        fallback_scripts = generate_rule_based_video_script_plans(product, diagnosis)
        for script in fallback_scripts:
            script["source"] = "rules"
            script["fallback_reason"] = str(exc)
        return fallback_scripts


def generate_llm_video_script_plans(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict[str, Any]]:
    """生成llm视频scriptplans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    parsed, raw_response = create_json_chat_completion(
        _build_video_script_messages(product, diagnosis),
        max_tokens=3200,
        temperature=0.45,
    )
    output = VideoScriptPlansOutput.model_validate(parsed)
    usage = raw_response.get("usage", {})
    model = raw_response.get("model")

    scripts: list[dict[str, Any]] = []
    for script in output.scripts:
        payload = script.model_dump()
        payload["source"] = "llm"
        payload["llm_model"] = model
        payload["llm_usage"] = usage
        scripts.append(payload)
    return scripts


def _build_video_script_messages(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict[str, str]]:
    """构建视频script消息，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    return [
        {
            "role": "system",
            "content": (
                "你是一个资深电商短视频编导和投放素材策略专家。"
                "你擅长为抖音、小红书、信息流广告生成可拍摄、可测试的带货短视频脚本。"
                "你必须只输出合法 json，不要输出 markdown，不要输出解释性前后缀。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请生成 3 条商品短视频脚本，用于小额投放测试。"
                "输出 json 必须严格符合以下结构：\n"
                "{\n"
                '  "scripts": [\n'
                "    {\n"
                '      "title": "脚本标题",\n'
                '      "angle": "测试角度",\n'
                '      "hook": "开头 3 秒钩子口播",\n'
                '      "duration_seconds": 30,\n'
                '      "scenes": [\n'
                '        {"shot": "0-3s", "visual": "画面说明", "voiceover": "口播文案"}\n'
                "      ],\n"
                '      "selling_point_proof": ["卖点证明1", "卖点证明2"],\n'
                '      "cta": "转化引导",\n'
                '      "video_prompt": "后续给视频生成模型用的中文镜头提示词"\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                "要求：\n"
                "- 所有内容使用简体中文。\n"
                "- 3 条脚本角度必须不同，至少包含痛点钩子、竞品/同类对比、场景种草或测评证明中的三类。\n"
                "- 每条脚本 25 到 45 秒，镜头拆成 4 到 6 段。\n"
                "- visual 要能指导拍摄或视频生成，voiceover 要像真人口播，不要像说明书。\n"
                "- 避免夸大、绝对化、违规医疗功效、无法证明的承诺。\n"
                "- cta 要自然，适合电商商品卡或详情页转化。\n\n"
                f"商品、竞品和诊断信息 json：{_creative_context_payload(product, diagnosis)}"
            ),
        },
    ]


def generate_rule_based_video_script_plans(
    product: Product,
    diagnosis: ProductDiagnosis | None,
) -> list[dict]:
    """生成rulebased视频scriptplans；集中执行业务校验、状态变更与持久化，并返回可验证结果。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    focus_points = _focus_points(product, diagnosis)
    audience = product.target_audience or "目标用户"
    pain_point = _diagnosis_pain_point(diagnosis)
    product_name = product.name
    price_text = f"{product.price}" if product.price is not None else "当前价格"

    templates = [
        {
            "title": f"{focus_points[0]}痛点钩子脚本",
            "angle": "先抛出用户高频痛点，再用商品卖点给出解决方案，适合投放冷启动。",
            "hook": f"{audience}出门前最怕的不是麻烦，是东西不好带还不好用。",
            "duration_seconds": 25,
            "scenes": [
                {
                    "shot": "0-3s",
                    "visual": "快速展示用户出门、补用或使用前的困扰场景。",
                    "voiceover": pain_point,
                },
                {
                    "shot": "4-10s",
                    "visual": f"商品特写，镜头对准“{focus_points[0]}”对应的使用细节。",
                    "voiceover": f"{product_name}主打{focus_points[0]}，日常使用更省心。",
                },
                {
                    "shot": "11-18s",
                    "visual": "用手部演示、对比画面或使用前后状态证明效果。",
                    "voiceover": f"再加上{focus_points[1] if len(focus_points) > 1 else focus_points[0]}，不是只看起来好，而是真的方便用。",
                },
                {
                    "shot": "19-25s",
                    "visual": "商品+价格+核心标签收尾，画面保持清晰。",
                    "voiceover": f"{price_text} 先试这一款，适合{audience}。",
                },
            ],
            "selling_point_proof": _proof_points(product, focus_points[:3]),
            "cta": "点击商品卡，先看详情和优惠。",
        },
        {
            "title": "竞品对比型脚本",
            "angle": "把同类商品的共同卖点和本品差异点做成短平快对比，适合搜索和信息流。",
            "hook": f"同样是{product.category or '这类商品'}，为什么我更建议先看这一款？",
            "duration_seconds": 30,
            "scenes": [
                {
                    "shot": "0-4s",
                    "visual": "左右对比开场，一边是普通选择，一边是本品。",
                    "voiceover": "别只看标题相似，真正影响体验的是这些细节。",
                },
                {
                    "shot": "5-12s",
                    "visual": f"放大展示“{focus_points[0]}”的画面证明。",
                    "voiceover": f"第一点，看{focus_points[0]}，这是首屏最值得讲清楚的差异。",
                },
                {
                    "shot": "13-22s",
                    "visual": "叠加 2-3 个卖点标签，配合实拍演示。",
                    "voiceover": f"同时还有{'、'.join(focus_points[1:3] or focus_points[:1])}，适合日常反复使用。",
                },
                {
                    "shot": "23-30s",
                    "visual": "回到商品整体和价格权益画面。",
                    "voiceover": f"预算在 {price_text} 左右，可以先点进来对比一下。",
                },
            ],
            "selling_point_proof": _proof_points(product, focus_points),
            "cta": "点进商品页，对比参数和评价再决定。",
        },
        {
            "title": "场景种草型脚本",
            "angle": "围绕目标人群的一天使用场景展开，适合内容种草和达人口播。",
            "hook": f"如果你也是{audience}，这个小东西可能会让日常轻松一点。",
            "duration_seconds": 35,
            "scenes": [
                {
                    "shot": "0-5s",
                    "visual": f"展示{audience}的高频生活/工作/通勤场景。",
                    "voiceover": "很多东西不是买回来不用，而是场景不够顺手。",
                },
                {
                    "shot": "6-14s",
                    "visual": "商品进入场景，展示取用、打开、使用过程。",
                    "voiceover": f"这款重点解决的是{focus_points[0]}，不用额外增加负担。",
                },
                {
                    "shot": "15-26s",
                    "visual": "连续 2-3 个小镜头展示不同使用时刻。",
                    "voiceover": f"{'、'.join(focus_points[:3])}这几个点，刚好对应日常真实需求。",
                },
                {
                    "shot": "27-35s",
                    "visual": "自然收尾，商品在桌面/包内/手边出现。",
                    "voiceover": "不需要夸张演，真实场景里好用才是复购理由。",
                },
            ],
            "selling_point_proof": _proof_points(product, focus_points[:3]),
            "cta": "先收藏或点商品卡，看是否适合你的使用场景。",
        },
    ]

    return templates


def _focus_points(product: Product, diagnosis: ProductDiagnosis | None) -> list[str]:
    """focuspoints，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    raw_points = []
    if diagnosis is not None:
        differentiated = diagnosis.raw_output.get("differentiated_points", [])
        if isinstance(differentiated, list):
            raw_points.extend(str(point) for point in differentiated if point)

    raw_points.extend(product.selling_points)

    # 优先使用诊断里的差异化点，再补商品卖点，保证生成方案围绕可测试的差异表达。
    unique_points = []
    for point in raw_points:
        if point not in unique_points:
            unique_points.append(point)

    return unique_points or ["核心卖点", "使用效果", "购买理由"]


def _proof_points(product: Product, focus_points: list[str]) -> list[str]:
    """proofpoints，统一主流程中的格式、默认值和异常边界。"""
    # 按“输入归一化 → 业务校验 → 状态或持久化”推进，异常不得留下半完成结果。
    proof_points = [f"围绕“{point}”给出可视化证明" for point in focus_points if point]
    if product.price is not None:
        proof_points.append(f"价格锚点：{product.price}")
    if product.target_audience:
        proof_points.append(f"人群锚点：{product.target_audience}")
    return proof_points[:4]


def _diagnosis_pain_point(diagnosis: ProductDiagnosis | None) -> str:
    """商品诊断painpoint，统一主流程中的格式、默认值和异常边界。"""
    if diagnosis is not None and diagnosis.pain_points:
        return diagnosis.pain_points[0]
    return "把用户顾虑改写成结果承诺，提升首屏理解效率"
