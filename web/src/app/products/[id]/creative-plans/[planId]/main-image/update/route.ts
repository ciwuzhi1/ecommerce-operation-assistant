import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";
import type { ProductDetail } from "@/types";

type RouteContext = {
  params: Promise<{ id: string; planId: string }>;
};

/** 处理商品/创意plans/主图图片/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, planId } = await context.params;
  const formData = await request.formData();
  const productResponse = await fetch(`${API_BASE_URL}/api/v1/products/${id}`, {
    cache: "no-store",
  });

  if (!productResponse.ok) {
    redirect(`/products/${id}?tab=main-images&edit=failed`);
  }

  const product = (await productResponse.json()) as ProductDetail;
  const plan = product.creative_plans.find((item) => String(item.id) === planId);
  if (!plan) {
    redirect(`/products/${id}?tab=main-images&edit=failed`);
  }

  const title = formValue(formData, "title") || plan.title;
  const angle = formValue(formData, "angle");
  const content = {
    ...plan.content,
    angle,
    headline: formValue(formData, "headline"),
    sub_headline: formValue(formData, "sub_headline"),
    layout: formValue(formData, "layout"),
    visual_focus: formValue(formData, "visual_focus"),
    proof_points: formLines(formData, "proof_points"),
    image_prompt: formValue(formData, "image_prompt"),
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
        rationale: angle || plan.rationale,
        content,
      }),
    },
  );

  if (!response.ok) {
    redirect(`/products/${id}?tab=main-images&edit=failed`);
  }

  redirect(`/products/${id}?tab=main-images&edit=saved`);
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


