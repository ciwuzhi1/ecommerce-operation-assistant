import { API_BASE_URL } from "@/lib/api";

/** 处理Workspace/templates/经营数据记录读取请求：转发认证与 Workspace 上下文，并返回后端强类型响应。 */
export async function GET() {
  const response = await fetch(`${API_BASE_URL}/api/v1/workspace/templates/performance-records.csv`, {
    cache: "no-store",
  });

  if (!response.ok) {
    return new Response("Template not available", { status: 502 });
  }

  return new Response(await response.text(), {
    headers: {
      "Content-Disposition": 'attachment; filename="performance-records-template.csv"',
      "Content-Type": "text/csv; charset=utf-8",
    },
  });
}
