import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { extractAgentErrorCode } from "@/lib/agent-error";
import { workspaceAuthHeaders } from "@/lib/session";

type RouteContext = { params: Promise<{ taskId: string }> };

/** 处理Agent/任务/取消请求：读取表单和路径参数，调用后端 API，并按结果重定向回任务中心。 */
export async function POST(request: Request, context: RouteContext) {
  const { taskId } = await context.params;
  const formData = await request.formData();
  const workspaceId = Number(formData.get("workspace_id"));
  const valid = Number.isInteger(workspaceId) && workspaceId > 0 && /^\d+$/.test(taskId);
  let result = "failed";
  if (valid) {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/agent/tasks/${taskId}/cancel`,
      { method: "POST", headers: await workspaceAuthHeaders(workspaceId) },
    );
    result = response.ok ? "cancelled" : await extractAgentErrorCode(response);
  }
  const target = new URL("/agent", request.url);
  if (valid) target.searchParams.set("workspace", String(workspaceId));
  target.searchParams.set("result", result);
  target.hash = "task-center";
  return NextResponse.redirect(target, 303);
}
