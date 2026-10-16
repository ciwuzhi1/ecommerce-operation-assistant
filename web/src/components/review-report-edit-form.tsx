import type { ReviewReport } from "@/types";

type ReviewReportEditFormProps = {
  productId: number;
  report: ReviewReport;
};

/** 渲染 ReviewReportEditForm 组件，集中展示复盘报告编辑表单所需的数据、状态和操作入口。 */
export function ReviewReportEditForm({ productId, report }: ReviewReportEditFormProps) {
  return (
    <form
      action={`/products/${productId}/review-reports/${report.id}/update`}
      method="post"
      className="mt-4 grid gap-3 border-t border-slate-200 pt-4"
    >
      {/* 复盘是周期性经营记录，允许人工修正日期和行动项，后续分析才不会被一次 AI 总结锁死。 */}
      <div className="grid gap-3 md:grid-cols-2">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">周期开始</span>
          <input
            name="period_start"
            type="date"
            defaultValue={report.period_start}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-slate-500">周期结束</span>
          <input
            name="period_end"
            type="date"
            defaultValue={report.period_end}
            className="h-10 rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
          />
        </label>
      </div>

      <label className="grid gap-1.5">
        <span className="text-xs font-medium text-slate-500">复盘总结</span>
        <textarea
          name="summary"
          defaultValue={report.summary}
          rows={3}
          className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
        />
      </label>

      <div className="grid gap-3 md:grid-cols-2">
        <ListField label="复盘洞察" name="insights" items={report.insights} />
        <ListField label="下一步动作" name="next_actions" items={report.next_actions} />
      </div>

      <button
        type="submit"
        className="inline-flex h-10 w-fit items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        保存复盘
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
        rows={5}
        className="resize-y rounded-md border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-slate-400"
      />
    </label>
  );
}
