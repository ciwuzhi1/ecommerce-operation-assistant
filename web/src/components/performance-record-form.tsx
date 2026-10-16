import { BarChart3, Plus } from "lucide-react";

import type { AdExperiment, CreativePlan, GeneratedAsset, PromotionLink } from "@/types";

type PerformanceRecordFormProps = {
  canEdit?: boolean;
  productId: number;
  creativePlans: CreativePlan[];
  generatedAssets: GeneratedAsset[];
  promotionLinks: PromotionLink[];
  adExperiments: AdExperiment[];
};

/** 渲染 PerformanceRecordForm 组件，集中展示经营数据record表单所需的数据、状态和操作入口。 */
export function PerformanceRecordForm({
  canEdit = true,
  productId,
  creativePlans,
  generatedAssets,
  promotionLinks,
  adExperiments,
}: PerformanceRecordFormProps) {
  if (!canEdit) {
    return (
      <div>
        <h2 className="text-base font-semibold text-slate-950">褰曞叆缁忚惀鏁版嵁</h2>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          当前账号为只读权限，不能录入经营数据。
        </p>
      </div>
    );
  }

  const sortedCreativePlans = [...creativePlans].sort((a, b) => {
    const statusRank = { selected: 0, draft: 1, archived: 2 };
    return statusRank[a.status] - statusRank[b.status] || b.id - a.id;
  });

  return (
    <form action={`/products/${productId}/performance-records/create`} method="post" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-amber-600 text-white">
          <BarChart3 className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">录入经营数据</h2>
          <p className="text-sm text-slate-500">曝光、点击、成交和花费会自动计算 CTR、转化率和 ROI</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">开始日期</span>
          <input
            name="period_start"
            required
            type="date"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">结束日期</span>
          <input
            name="period_end"
            required
            type="date"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">关联素材</span>
        <select
          name="creative_plan_id"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
        >
          <option value="">不关联素材</option>
          {sortedCreativePlans.map((plan) => (
            <option key={plan.id} value={plan.id}>
              {plan.status === "selected" ? "已选中 · " : ""}
              {plan.type === "main_image" ? "主图" : "视频"} · {plan.title}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">关联投放实验</span>
        <select
          name="ad_experiment_id"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
        >
          <option value="">不关联实验</option>
          {adExperiments.map((experiment) => (
            <option key={experiment.id} value={experiment.id}>
              {experiment.status === "active" ? "执行中 · " : ""}
              {experiment.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">关联链接</span>
        <select
          name="promotion_link_id"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
        >
          <option value="">不关联链接</option>
          {promotionLinks.map((link) => (
            <option key={link.id} value={link.id}>
              {link.label} · {link.scenario || link.link_type}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">关联生成素材</span>
        <select
          name="generated_asset_id"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
        >
          <option value="">不关联生成素材</option>
          {generatedAssets.map((asset) => (
            <option key={asset.id} value={asset.id}>
              {asset.asset_type === "video" ? "视频" : "图片"} · {asset.title || asset.url}
            </option>
          ))}
        </select>
      </label>

      <div className="grid gap-4 sm:grid-cols-3">
        <NumberInput name="impressions" label="曝光" placeholder="10000" />
        <NumberInput name="clicks" label="点击" placeholder="420" />
        <NumberInput name="conversions" label="成交" placeholder="18" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <NumberInput name="spend" label="花费" placeholder="300.00" decimal />
        <NumberInput name="revenue" label="成交金额" placeholder="980.00" decimal />
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">备注</span>
        <textarea
          name="notes"
          className="mt-2 min-h-20 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
          placeholder="可记录素材版本、投放人群、活动价等上下文"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        保存数据
      </button>
    </form>
  );
}

/** 渲染 NumberInput 组件，集中展示数值input所需的数据、状态和操作入口。 */
function NumberInput({
  name,
  label,
  placeholder,
  decimal = false,
}: {
  name: string;
  label: string;
  placeholder: string;
  decimal?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        inputMode={decimal ? "decimal" : "numeric"}
        className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-amber-500 focus:ring-4 focus:ring-amber-100"
        placeholder={placeholder}
      />
    </label>
  );
}
