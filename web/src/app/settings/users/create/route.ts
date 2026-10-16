import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理模型设置/users/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const response = await fetch(`${API_BASE_URL}/api/v1/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      email: formData.get("email")?.toString() ?? "",
      display_name: formData.get("display_name")?.toString() ?? "",
      role: formData.get("role")?.toString() ?? "operator",
      status: "active",
      password: formData.get("password")?.toString() || null,
    }),
  });

  revalidatePath("/settings");
  redirect(`/settings?user=${response.ok ? "created" : "failed"}`);
}

