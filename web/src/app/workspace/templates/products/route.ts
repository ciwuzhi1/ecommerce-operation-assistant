import { API_BASE_URL } from "@/lib/api";

/** 处理Workspace/templates/商品读取请求：转发认证与 Workspace 上下文，并返回后端强类型响应。 */
export async function GET() {
  return proxyTemplate("products.csv", "products-template.csv");
}

/** proxytemplate，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
async function proxyTemplate(path: string, filename: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/workspace/templates/${path}`, { cache: "no-store" });
  if (!response.ok) {
    return new Response("Template not available", { status: 502 });
  }
  return new Response(await response.text(), {
    headers: {
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Content-Type": "text/csv; charset=utf-8",
    },
  });
}
