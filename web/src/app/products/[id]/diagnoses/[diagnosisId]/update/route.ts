import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";
import type { ProductDetail } from "@/types";

type RouteContext = {
  params: Promise<{ id: string; diagnosisId: string }>;
};

/** 处理商品/diagnoses/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, diagnosisId } = await context.params;
  const formData = await request.formData();
  const productResponse = await fetch(`${API_BASE_URL}/api/v1/products/${id}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });

  if (!productResponse.ok) {
    redirect(`/products/${id}?tab=diagnosis&edit=failed`);
  }

  const product = (await productResponse.json()) as ProductDetail;
  const diagnosis = product.diagnoses.find((item) => String(item.id) === diagnosisId);
  if (!diagnosis) {
    redirect(`/products/${id}?tab=diagnosis&edit=failed`);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/diagnoses/${diagnosisId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({
      positioning: formValue(formData, "positioning"),
      price_band: formValue(formData, "price_band"),
      audience_insights: formLines(formData, "audience_insights"),
      pain_points: formLines(formData, "pain_points"),
      selling_point_analysis: formLines(formData, "selling_point_analysis"),
      risks: formLines(formData, "risks"),
      recommendations: formLines(formData, "recommendations"),
      raw_output: {
        ...diagnosis.raw_output,
        edited_by_user: true,
      },
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=diagnosis&edit=failed`);
  }

  redirect(`/products/${id}?tab=diagnosis&edit=saved`);
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


