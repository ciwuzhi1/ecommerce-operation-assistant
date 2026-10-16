import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { extractAgentErrorCode } from "@/lib/agent-error";
import { workspaceAuthHeaders } from "@/lib/session";

type RouteContext = { params: Promise<{ memoryId: string }> };

/** 处理Agent/记忆/撤销请求：读取表单和路径参数，调用后端 API，并按结果重定向回记忆区。 */
export async function POST(request: Request, context: RouteContext) {
  const { memoryId } = await context.params;
  const formData = await request.formData();
  const workspaceId = Number(formData.get("workspace_id"));

  const valid =
    Number.isInteger(workspaceId) && workspaceId > 0 && /^\d+$/.test(memoryId);

  let result = "failed";
  if (valid) {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/agent/memories/${memoryId}/revoke`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(await workspaceAuthHeaders(workspaceId)),
        },
      },
    );
    result = response.ok ? "memory-revoked" : await extractAgentErrorCode(response);
  }

  const target = new URL("/agent", request.url);
  if (Number.isInteger(workspaceId) && workspaceId > 0) {
    target.searchParams.set("workspace", String(workspaceId));
  }
  target.searchParams.set("result", result);
  target.hash = "memory";
  return NextResponse.redirect(target, 303);
}
