import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

/** 处理Agent运行/复核请求：转发认证与原始 JSON 载荷，并原样返回后端响应。 */
export async function POST(request: Request, context: RouteContext) {
  const { runId } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/agent-runs/${runId}/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: await request.text(),
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
  });
}
