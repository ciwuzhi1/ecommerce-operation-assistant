import { redirect } from "next/navigation";
import { z } from "zod";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

const movementSchema = z.object({
  movement_type: z.enum(["inbound", "outbound", "adjustment", "lock", "release"]),
  quantity: z.string().optional(),
  reason: z.string().optional(),
  operator_name: z.string().optional(),
});

type RouteContext = {
  params: Promise<{ id: string; skuId: string }>;
};

/** 处理商品/skus/库存movements/创建请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id, skuId } = await context.params;
  const formData = await request.formData();
  const values = movementSchema.parse(Object.fromEntries(formData.entries()));
  const quantity = toNonNegativeInt(values.quantity);

  // 浏览器表单只提交正数数量；这里按动作类型转换为库存数量或锁定数量的 delta。
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/skus/${skuId}/inventory-movements`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      movement_type: values.movement_type,
      quantity_delta: quantityDelta(values.movement_type, quantity),
      locked_delta: lockedDelta(values.movement_type, quantity),
      reason: values.reason && values.reason.trim() ? values.reason.trim() : null,
      operator_name: values.operator_name && values.operator_name.trim() ? values.operator_name.trim() : null,
    }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=overview&inventory=failed`);
  }

  redirect(`/products/${id}?tab=overview&inventory=updated`);
}

/** quantitydelta，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function quantityDelta(movementType: string, quantity: number): number {
  // 入库/盘点影响真实库存，锁定/释放只影响占用量，避免前端重复扣减。
  if (movementType === "inbound" || movementType === "adjustment") {
    return quantity;
  }
  if (movementType === "outbound") {
    return -quantity;
  }
  return 0;
}

/** lockeddelta，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function lockedDelta(movementType: string, quantity: number): number {
  // 锁定为正、释放为负；后端会继续校验锁定库存不能超过总库存。
  if (movementType === "lock") {
    return quantity;
  }
  if (movementType === "release") {
    return -quantity;
  }
  return 0;
}

/** 到nonnegativeint，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toNonNegativeInt(value?: string): number {
  const number = Number(value ?? 0);
  return Number.isFinite(number) && number > 0 ? Math.floor(number) : 0;
}
