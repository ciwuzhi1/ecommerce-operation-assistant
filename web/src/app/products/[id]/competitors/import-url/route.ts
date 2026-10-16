import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const importCompetitorUrlSchema = z.object({
  platform: z.enum(["douyin", "taobao", "tmall", "pinduoduo", "jd", "tiktok_shop", "amazon", "other"]),
  url: z.string().url(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/competitors/导入URL请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = importCompetitorUrlSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/competitors/import-url-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(values),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&competitor_import=failed`);
  }

  redirect(`/products/${id}?tab=overview&competitor_import=queued`);
}


