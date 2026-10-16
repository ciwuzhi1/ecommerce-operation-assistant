import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理商品/投放实验/状态请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; experimentId: string }> },
) {
  const { id, experimentId } = await params;
  const formData = await request.formData();
  const nextStatus = String(formData.get("status") ?? "");

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/ad-experiments/${experimentId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify({ status: nextStatus }),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=ads&experiment=${response.ok ? "updated" : "failed"}`);
}

