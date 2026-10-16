import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const createProductSchema = z.object({
  store_id: z.string().optional(),
  name: z.string().min(1),
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  category: z.string().optional(),
  price: z.string().optional(),
  target_audience: z.string().optional(),
  selling_points: z.string().optional(),
});

/** 处理商品/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const values = createProductSchema.parse(Object.fromEntries(formData.entries()));

  const payload = {
    ...values,
    store_id: values.store_id ? Number(values.store_id) : null,
    category: values.category || null,
    price: values.price || null,
    target_audience: values.target_audience || null,
    selling_points:
      values.selling_points
        ?.split(/[,，\n]/)
        .map((item) => item.trim())
        .filter(Boolean) ?? [],
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    redirect("/?create=failed");
  }

  redirect("/");
}



