import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理商品/生成任务jobs/取消请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; jobId: string }> },
) {
  const { id, jobId } = await params;
  const formData = await request.formData();
  const tab = String(formData.get("tab") ?? "jobs");

  await fetch(`${API_BASE_URL}/api/v1/products/${id}/generation-jobs/${jobId}/cancel`, {
    method: "POST",
    headers: await authHeaders(),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=${tab}`);
}
