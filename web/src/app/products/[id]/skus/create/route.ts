import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const skuCreateSchema = z.object({
  sku_code: z.string().min(1),
  name: z.string().min(1),
  price: z.string().optional(),
  cost: z.string().optional(),
  initial_quantity: z.string().optional(),
  warning_threshold: z.string().optional(),
  location: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/skus/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = skuCreateSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/skus`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      sku_code: values.sku_code,
      name: values.name,
      price: emptyToNull(values.price),
      cost: emptyToNull(values.cost),
      initial_quantity: toNonNegativeInt(values.initial_quantity),
      warning_threshold: toNonNegativeInt(values.warning_threshold),
      location: emptyToNull(values.location),
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&sku=failed`);
  }

  redirect(`/products/${id}?tab=overview&sku=created`);
}

/** 空状态到null，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function emptyToNull(value?: string): string | null {
  return value && value.trim() ? value.trim() : null;
}

/** 到nonnegativeint，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toNonNegativeInt(value?: string): number {
  const number = Number(value ?? 0);
  return Number.isFinite(number) && number > 0 ? Math.floor(number) : 0;
}
