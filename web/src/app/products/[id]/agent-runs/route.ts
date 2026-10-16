import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/Agent运行读取请求：转发认证与 Workspace 上下文，并返回后端强类型响应。 */
export async function GET(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/agent-runs`, {
    headers: await authHeaders(),
    cache: "no-store",
  });
  return forwardResponse(response);
}

/** 处理商品/Agent运行请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/agent-runs`, {
    method: "POST",
    headers: await authHeaders(),
  });
  return forwardResponse(response);
}

/** 转发响应，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
async function forwardResponse(response: Response) {
  return new Response(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
  });
}
