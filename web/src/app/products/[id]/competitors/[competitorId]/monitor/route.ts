import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string; competitorId: string }>;
};

/** 处理商品/competitors/monitor请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, { params }: RouteContext) {
  const { id, competitorId } = await params;
  const formData = await request.formData();
  const intervalDays = Number(formData.get("interval_days") ?? 1);

  await fetch(`${API_BASE_URL}/api/v1/products/${id}/competitors/${competitorId}/monitor`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      interval_days: Number.isFinite(intervalDays) && intervalDays > 0 ? intervalDays : 1,
      note: formData.get("note")?.toString() || null,
    }),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=overview&monitor=created`);
}


