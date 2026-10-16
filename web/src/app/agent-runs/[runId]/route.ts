import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

/** 处理Agent运行读取请求：转发认证与 Workspace 上下文，并返回后端强类型响应。 */
export async function GET(_request: Request, context: RouteContext) {
  const { runId } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/agent-runs/${runId}`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
  });
}
