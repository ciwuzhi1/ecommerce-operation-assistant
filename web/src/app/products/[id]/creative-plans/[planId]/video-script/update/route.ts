import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";
import type { ProductDetail } from "@/types";

type RouteContext = {
  params: Promise<{ id: string; planId: string }>;
};

/** 处理商品/创意plans/视频script/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, planId } = await context.params;
  const formData = await request.formData();
  const productResponse = await fetch(`${API_BASE_URL}/api/v1/products/${id}`, {
    cache: "no-store",
  });

  if (!productResponse.ok) {
    redirect(`/products/${id}?tab=video&edit=failed`);
  }

  const product = (await productResponse.json()) as ProductDetail;
  const script = product.creative_plans.find((item) => String(item.id) === planId);
  if (!script) {
    redirect(`/products/${id}?tab=video&edit=failed`);
  }

  const title = formValue(formData, "title") || script.title;
  const angle = formValue(formData, "angle");
  const durationSeconds = Number(formValue(formData, "duration_seconds"));
  const content = {
    ...script.content,
    angle,
    hook: formValue(formData, "hook"),
    duration_seconds: Number.isFinite(durationSeconds)
      ? durationSeconds
      : script.content.duration_seconds,
    scenes: parseScenes(formValue(formData, "scenes_json"), script.content.scenes),
    selling_point_proof: formLines(formData, "selling_point_proof"),
    cta: formValue(formData, "cta"),
    video_prompt: formValue(formData, "video_prompt"),
    reference_images: formLines(formData, "reference_images"),
    subtitle_lines: formLines(formData, "subtitle_lines"),
    voiceover_text: formValue(formData, "voiceover_text"),
    edit_notes: formValue(formData, "edit_notes"),
    edited_by_user: true,
  };

  const response = await fetch(
    `${API_BASE_URL}/api/v1/products/${id}/creative-plans/${planId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      ...(await authHeaders()),
    },
      body: JSON.stringify({
        title,
        rationale: angle || script.rationale,
        content,
      }),
    },
  );

  if (!response.ok) {
    redirect(`/products/${id}?tab=video&edit=failed`);
  }

  redirect(`/products/${id}?tab=video&edit=saved`);
}

/** 表单值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function formValue(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === "string" ? value.trim() : "";
}

/** 表单lines，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function formLines(formData: FormData, key: string): string[] {
  return formValue(formData, key)
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** 解析scenes，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function parseScenes(rawValue: string, fallback: unknown): unknown {
  try {
    const parsed = JSON.parse(rawValue);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}


