import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理商品/投放实验/生成请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/ad-experiments/generate`, {
    method: "POST",
    headers: await authHeaders(),
  });

  revalidatePath(`/products/${id}`);
  redirect(`/products/${id}?tab=ads&experiment=${response.ok ? "generated" : "failed"}`);
}


