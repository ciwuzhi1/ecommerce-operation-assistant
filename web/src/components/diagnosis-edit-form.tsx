import type { ProductDiagnosis } from "@/types";

type DiagnosisEditFormProps = {
  diagnosis: ProductDiagnosis;
  productId: number;
};

/** 渲染 DiagnosisEditForm 组件，集中展示商品诊断编辑表单所需的数据、状态和操作入口。 */
export function DiagnosisEditForm({ diagnosis, productId }: DiagnosisEditFormProps) {
  return (
    <form
      action={`/products/${productId}/diagnoses/${diagnosis.id}/update`}
      method="post"
      className="mt-4 grid gap-3 border-t border-slate-200 pt-4"
    >
      {/* 诊断结论来自 AI 或规则初稿，但最终运营判断需要可编辑，避免把模型输出当作不可更改的事实。 */}
      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">定位判断</span>
        <textarea
          name="positioning"
          defaultValue={diagnosis.positioning}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">价格带判断</span>
        <textarea
          name="price_band"
          defaultValue={diagnosis.price_band}
          rows={2}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <ListField label="人群洞察" name="audience_insights" items={diagnosis.audience_insights} />
        <ListField label="用户痛点" name="pain_points" items={diagnosis.pain_points} />
        <ListField label="卖点判断" name="selling_point_analysis" items={diagnosis.selling_point_analysis} />
        <ListField label="风险点" name="risks" items={diagnosis.risks} />
      </div>

      <ListField label="下一步建议" name="recommendations" items={diagnosis.recommendations} />

      <button
        type="submit"
        className="inline-flex h-10 w-fit items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        保存诊断
      </button>
    </form>
  );
}

/** 渲染 ListField 组件，集中展示列表字段所需的数据、状态和操作入口。 */
function ListField({
  label,
  name,
  items,
}: {
  label: string;
  name: string;
  items: string[];
}) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-medium text-slate-500">{label}</span>
      <textarea
        name={name}
        defaultValue={items.join("\n")}
        rows={4}
        className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
      />
    </label>
  );
}
