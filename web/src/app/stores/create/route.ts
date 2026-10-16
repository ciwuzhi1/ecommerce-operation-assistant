import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const createStoreSchema = z.object({
  name: z.string().min(1),
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  owner_name: z.string().optional(),
});

/** 处理stores/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const values = createStoreSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(`${API_BASE_URL}/api/v1/stores`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      ...values,
      owner_name: values.owner_name || null,
    }),
  });

  if (!response.ok) {
    redirect("/?store=failed");
  }

  redirect("/?store=created");
}
