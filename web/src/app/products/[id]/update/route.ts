import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const productUpdateSchema = z.object({
  name: z.string().min(1),
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  category: z.string().optional(),
  price: z.string().optional(),
  cost: z.string().optional(),
  target_audience: z.string().optional(),
  selling_points: z.string().optional(),
  product_url: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = productUpdateSchema.parse(Object.fromEntries(formData.entries()));
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({
      name: values.name,
      platform: values.platform,
      category: emptyToNull(values.category),
      price: emptyToNull(values.price),
      cost: emptyToNull(values.cost),
      target_audience: emptyToNull(values.target_audience),
      selling_points: formLines(values.selling_points),
      product_url: emptyToNull(values.product_url),
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&product=failed`);
  }

  redirect(`/products/${id}?tab=overview&product=saved`);
}

/** 空状态到null，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function emptyToNull(value?: string): string | null {
  return value && value.trim() ? value.trim() : null;
}

/** 表单lines，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function formLines(value?: string): string[] {
  return (value ?? "")
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}


