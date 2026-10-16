import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const mappingCreateSchema = z.object({
  store_id: z.string().optional(),
  sku_id: z.string().optional(),
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  external_product_id: z.string().min(1),
  external_sku_id: z.string().optional(),
  listing_url: z.string().optional(),
  status: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/平台mappings/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = mappingCreateSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/platform-mappings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      store_id: toOptionalNumber(values.store_id),
      sku_id: toOptionalNumber(values.sku_id),
      platform: values.platform,
      external_product_id: values.external_product_id.trim(),
      external_sku_id: emptyToNull(values.external_sku_id),
      listing_url: emptyToNull(values.listing_url),
      status: emptyToNull(values.status),
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&mapping=failed`);
  }

  redirect(`/products/${id}?tab=overview&mapping=created`);
}

/** 空状态到null，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function emptyToNull(value?: string): string | null {
  return value && value.trim() ? value.trim() : null;
}

/** 到optional数值，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toOptionalNumber(value?: string): number | null {
  if (!value || !value.trim()) {
    return null;
  }
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : null;
}
