import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const stocktakeSchema = z.object({
  current_quantity: z.string(),
  target_quantity: z.string(),
  reason: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string; skuId: string }>;
};

/** 处理商品/skus/库存movements/盘点请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, skuId } = await context.params;
  const formData = await request.formData();
  const values = stocktakeSchema.parse(Object.fromEntries(formData.entries()));
  const currentQuantity = toNonNegativeInt(values.current_quantity);
  const targetQuantity = toNonNegativeInt(values.target_quantity);

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/skus/${skuId}/inventory-movements`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      movement_type: "adjustment",
      quantity_delta: targetQuantity - currentQuantity,
      locked_delta: 0,
      reason: values.reason && values.reason.trim() ? values.reason.trim() : "库存盘点",
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&inventory=failed`);
  }

  redirect(`/products/${id}?tab=overview&inventory=stocktaken`);
}

/** 到nonnegativeint，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toNonNegativeInt(value?: string): number {
  const number = Number(value ?? 0);
  return Number.isFinite(number) && number > 0 ? Math.floor(number) : 0;
}
