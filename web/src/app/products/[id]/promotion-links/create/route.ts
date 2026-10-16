import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const promotionLinkSchema = z.object({
  label: z.string().min(1),
  link_type: z.string().optional(),
  note: z.string().optional(),
  scenario: z.string().optional(),
  status: z.string().optional(),
  url: z.string().url(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/推广links/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = promotionLinkSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/promotion-links`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      ...values,
      link_type: values.link_type || "landing",
      note: values.note || null,
      scenario: values.scenario || null,
      status: values.status || "active",
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=links&links=failed`);
  }

  redirect(`/products/${id}?tab=links&links=created`);
}


