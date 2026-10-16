import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理导入/SKU库存请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request) {
  const payload = await request.json();
  const response = await fetch(`${API_BASE_URL}/api/v1/workspace/imports/sku-inventory`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    return NextResponse.json({ error: payload?.detail ?? "SKU inventory import failed" }, { status: response.status });
  }

  return NextResponse.json(await response.json());
}
