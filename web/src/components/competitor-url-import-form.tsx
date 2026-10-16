import { ScanSearch } from "lucide-react";

type CompetitorUrlImportFormProps = {
  canEdit?: boolean;
  productId: number;
};

const platforms = [
  { label: "抖音电商", value: "douyin" },
  { label: "淘宝", value: "taobao" },
  { label: "天猫", value: "tmall" },
  { label: "拼多多", value: "pinduoduo" },
  { label: "京东", value: "jd" },
  { label: "TikTok Shop", value: "tiktok_shop" },
  { label: "Amazon", value: "amazon" },
  { label: "其他", value: "other" },
] as const;

/** 渲染 CompetitorUrlImportForm 组件，集中展示竞品URL导入表单所需的数据、状态和操作入口。 */
export function CompetitorUrlImportForm({ canEdit = true, productId }: CompetitorUrlImportFormProps) {
  if (!canEdit) {
    return (
      <div>
        <h2 className="text-base font-semibold text-slate-950">鍒涘缓绔炲搧瑙ｆ瀽浠诲姟</h2>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          当前账号为只读权限，不能创建解析任务。
        </p>
      </div>
    );
  }

  return (
    <form action={`/products/${productId}/competitors/import-url`} method="post" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 text-white">
          <ScanSearch className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">创建竞品解析任务</h2>
          <p className="text-sm text-slate-500">提交公开商品页，后台解析标题、价格、主图和卖点关键词</p>
        </div>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">竞品链接</span>
        <input
          name="url"
          required
          type="url"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          placeholder="https://..."
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">平台</span>
        <select
          name="platform"
          defaultValue="douyin"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
        >
          {platforms.map((platform) => (
            <option key={platform.value} value={platform.value}>
              {platform.label}
            </option>
          ))}
        </select>
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <ScanSearch className="h-4 w-4" aria-hidden="true" />
        创建解析任务
      </button>
    </form>
  );
}
