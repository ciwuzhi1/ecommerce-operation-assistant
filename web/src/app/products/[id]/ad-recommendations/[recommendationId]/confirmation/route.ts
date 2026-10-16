import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理商品/投放建议/确认请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; recommendationId: string }> },
) {
  const { id, recommendationId } = await params;
  const formData = await request.formData();
  const body = {
    confirmation_status: value(formData, "confirmation_status"),
    confirmation_note: value(formData, "confirmation_note") || null,
  };

  // 这里仅转发人工确认结论，不携带任何广告平台预算或投放执行参数。
  await fetch(`${API_BASE_URL}/api/v1/products/${id}/ad-recommendations/${recommendationId}/confirmation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=ads`);
}

/** 值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function value(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}
