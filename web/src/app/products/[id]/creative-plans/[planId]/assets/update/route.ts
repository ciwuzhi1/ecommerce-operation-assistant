import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理商品/创意plans/素材/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; planId: string }> },
) {
  const { id, planId } = await params;
  const formData = await request.formData();
  const body = {
    url: value(formData, "url"),
    asset_type: value(formData, "asset_type"),
    rating: numberValue(formData, "rating"),
    status: value(formData, "status"),
    asset_version: numberValue(formData, "asset_version"),
    usage_contexts: splitLines(value(formData, "usage_contexts")),
    tags: splitLines(value(formData, "tags")),
    note: value(formData, "note"),
  };

  await fetch(`${API_BASE_URL}/api/v1/products/${id}/creative-plans/${planId}/assets`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=assets`);
}

/** 值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function value(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}

/** 数值值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function numberValue(formData: FormData, name: string) {
  const raw = value(formData, name);
  return raw ? Number(raw) : null;
}

/** 拆分lines，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function splitLines(raw: string) {
  return raw
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}


