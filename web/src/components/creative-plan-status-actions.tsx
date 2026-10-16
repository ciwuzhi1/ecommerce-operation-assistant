import type { CreativePlan } from "@/types";

type CreativePlanStatusActionsProps = {
  canEdit?: boolean;
  plan: CreativePlan;
  productId: number;
  tab: "main-images" | "video";
};

/** 渲染 CreativePlanStatusActions 组件，集中展示创意方案状态actions所需的数据、状态和操作入口。 */
export function CreativePlanStatusActions({ canEdit = true, plan, productId, tab }: CreativePlanStatusActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className={`rounded-md px-2 py-1 text-xs ${statusClassName(plan.status)}`}>
        {statusLabel(plan.status)}
      </span>
      {!canEdit ? null : (
      // 状态切换只是运营筛选方案，不会自动生成素材或创建投放实验；后端仍会校验编辑权限。
      <form
        action={`/products/${productId}/creative-plans/${plan.id}/status/update`}
        method="post"
        className="flex flex-wrap gap-1"
      >
        <input type="hidden" name="tab" value={tab} />
        {plan.status !== "selected" ? (
          <button
            type="submit"
            name="status"
            value="selected"
            className="h-7 rounded-md bg-emerald-600 px-2.5 text-xs font-medium text-white transition hover:bg-emerald-700"
          >
            选中
          </button>
        ) : null}
        {plan.status !== "archived" ? (
          <button
            type="submit"
            name="status"
            value="archived"
            className="h-7 rounded-md bg-slate-200 px-2.5 text-xs font-medium text-slate-700 transition hover:bg-slate-300"
          >
            归档
          </button>
        ) : null}
        {plan.status !== "draft" ? (
          <button
            type="submit"
            name="status"
            value="draft"
            className="h-7 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-600 transition hover:border-slate-300 hover:bg-white"
          >
            草稿
          </button>
        ) : null}
      </form>
      )}
    </div>
  );
}

/** 把状态状态映射为中文显示文本，保持页面口径一致。 */
function statusLabel(status: CreativePlan["status"]): string {
  const labels: Record<CreativePlan["status"], string> = {
    draft: "草稿",
    selected: "已选中",
    archived: "已归档",
  };
  return labels[status];
}

/** 把状态样式name状态映射为视觉样式，避免组件内散落条件分支。 */
function statusClassName(status: CreativePlan["status"]): string {
  const classes: Record<CreativePlan["status"], string> = {
    draft: "bg-slate-100 text-slate-600",
    selected: "bg-emerald-50 text-emerald-700",
    archived: "bg-slate-200 text-slate-500",
  };
  return classes[status];
}
