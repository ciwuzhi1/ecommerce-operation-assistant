import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理Workspace/demodata请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST() {
  const response = await fetch(`${API_BASE_URL}/api/v1/workspace/demo-data`, {
    method: "POST",
    headers: await authHeaders(),
  });

  if (!response.ok) {
    redirect("/?demo=failed");
  }

  redirect("/?demo=created");
}
