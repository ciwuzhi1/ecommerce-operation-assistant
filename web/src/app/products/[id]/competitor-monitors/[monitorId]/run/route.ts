import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string; monitorId: string }>;
};

/** 处理商品/竞品monitors/运行请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(_request: Request, { params }: RouteContext) {
  const { id, monitorId } = await params;

  await fetch(`${API_BASE_URL}/api/v1/products/${id}/competitor-monitors/${monitorId}/run`, {
    method: "POST",
    headers: await authHeaders(),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=overview&monitor=checked`);
}


