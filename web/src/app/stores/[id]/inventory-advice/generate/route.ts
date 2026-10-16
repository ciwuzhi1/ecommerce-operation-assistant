import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理stores/库存建议/生成请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/stores/${id}/inventory-advice`, {
    method: "POST",
    headers: await authHeaders(),
  });

  if (!response.ok) {
    return NextResponse.json({ error: "Failed to generate inventory advice" }, { status: response.status });
  }

  return NextResponse.json(await response.json());
}
