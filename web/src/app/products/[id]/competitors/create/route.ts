import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const createCompetitorSchema = z.object({
  name: z.string().min(1),
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  url: z.string().optional(),
  price: z.string().optional(),
  title: z.string().optional(),
  selling_points: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/competitors/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = createCompetitorSchema.parse(Object.fromEntries(formData.entries()));

  const payload = {
    ...values,
    url: values.url || null,
    price: values.price || null,
    title: values.title || null,
    selling_points:
      values.selling_points
        ?.split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean) ?? [],
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/competitors`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&competitor=failed`);
  }

  redirect(`/products/${id}?tab=overview`);
}


