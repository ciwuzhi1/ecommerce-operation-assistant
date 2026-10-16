import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string; reportId: string }>;
};

/** 处理商品/复盘reports/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, reportId } = await context.params;
  const formData = await request.formData();
  const response = await fetch(
    `${API_BASE_URL}/api/v1/products/${id}/review-reports/${reportId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      ...(await authHeaders()),
    },
      body: JSON.stringify({
        period_start: formValue(formData, "period_start"),
        period_end: formValue(formData, "period_end"),
        summary: formValue(formData, "summary"),
        insights: formLines(formData, "insights"),
        next_actions: formLines(formData, "next_actions"),
      }),
    },
  );

  if (!response.ok) {
    redirect(`/products/${id}?tab=review&edit=failed`);
  }

  redirect(`/products/${id}?tab=review&edit=saved`);
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


