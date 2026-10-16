import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/推广links/生成请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/promotion-links/generate`, {
    method: "POST",
    headers: await authHeaders(),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=links&links=failed`);
  }

  redirect(`/products/${id}?tab=links&links=generated`);
}


