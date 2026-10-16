import type { CreativePlan } from "@/types";

type MainImagePlanEditFormProps = {
  productId: number;
  plan: CreativePlan;
};

/** 渲染 MainImagePlanEditForm 组件，集中展示主图图片方案编辑表单所需的数据、状态和操作入口。 */
export function MainImagePlanEditForm({ productId, plan }: MainImagePlanEditFormProps) {
  return (
    <form
      action={`/products/${productId}/creative-plans/${plan.id}/main-image/update`}
      method="post"
      className="mt-4 grid gap-3 border-t border-slate-200 pt-4"
    >
      {/* AI 生成的主图方案必须允许人工改文案、布局和 prompt，保存后仍回写为结构化 content。 */}
      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">方案标题</span>
        <input
          name="title"
          defaultValue={plan.title}
          className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">主文案</span>
          <input
            name="headline"
            defaultValue={planText(plan.content, "headline")}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">副文案</span>
          <input
            name="sub_headline"
            defaultValue={planText(plan.content, "sub_headline")}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
      </div>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">测试角度</span>
        <textarea
          name="angle"
          defaultValue={planText(plan.content, "angle")}
          rows={2}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">画面布局</span>
        <textarea
          name="layout"
          defaultValue={planText(plan.content, "layout")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">视觉重点</span>
        <textarea
          name="visual_focus"
          defaultValue={planText(plan.content, "visual_focus")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">证明点</span>
        <textarea
          name="proof_points"
          defaultValue={planList(plan.content, "proof_points").join("\n")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">图片生成提示词</span>
        <textarea
          name="image_prompt"
          defaultValue={planText(plan.content, "image_prompt")}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-fit items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        保存修改
      </button>
    </form>
  );
}

/** 方案文本，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planText(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

/** 方案列表，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  // content 可能来自旧数据或人工编辑，读取列表字段时做类型收窄，坏值只显示为空。
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
