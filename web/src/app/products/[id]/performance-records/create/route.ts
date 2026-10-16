import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const performanceRecordSchema = z.object({
  ad_experiment_id: z.string().optional(),
  creative_plan_id: z.string().optional(),
  generated_asset_id: z.string().optional(),
  promotion_link_id: z.string().optional(),
  period_start: z.string().min(1),
  period_end: z.string().min(1),
  impressions: z.string().optional(),
  clicks: z.string().optional(),
  conversions: z.string().optional(),
  spend: z.string().optional(),
  revenue: z.string().optional(),
  notes: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string }>;
};

/** 处理商品/经营数据记录/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const values = performanceRecordSchema.parse(Object.fromEntries(formData.entries()));

  const payload = {
    ad_experiment_id: toNumber(values.ad_experiment_id),
    creative_plan_id: toNumber(values.creative_plan_id),
    generated_asset_id: toNumber(values.generated_asset_id),
    promotion_link_id: toNumber(values.promotion_link_id),
    period_start: values.period_start,
    period_end: values.period_end,
    impressions: toNumber(values.impressions),
    clicks: toNumber(values.clicks),
    conversions: toNumber(values.conversions),
    spend: emptyToNull(values.spend),
    revenue: emptyToNull(values.revenue),
    notes: values.notes || null,
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/performance-records`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=review&performance=failed`);
  }

  redirect(`/products/${id}?tab=review`);
}

/** 空状态到null，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function emptyToNull(value?: string): string | null {
  return value && value.trim() ? value.trim() : null;
}

/** 到数值，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toNumber(value?: string): number | null {
  if (!value || !value.trim()) {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}


