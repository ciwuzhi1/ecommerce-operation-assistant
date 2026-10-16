import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const statusSchema = z.object({
  status: z.enum(["draft", "selected", "archived"]),
  tab: z.enum(["main-images", "video"]),
});

type RouteContext = {
  params: Promise<{ id: string; planId: string }>;
};

/** 处理商品/创意plans/状态/更新请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, planId } = await context.params;
  const formData = await request.formData();
  const values = statusSchema.parse(Object.fromEntries(formData.entries()));

  const response = await fetch(
    `${API_BASE_URL}/api/v1/products/${id}/creative-plans/${planId}`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      ...(await authHeaders()),
    },
      body: JSON.stringify({
        status: values.status,
      }),
    },
  );

  if (!response.ok) {
    redirect(`/products/${id}?tab=${values.tab}&status=failed`);
  }

  redirect(`/products/${id}?tab=${values.tab}&status=saved`);
}


