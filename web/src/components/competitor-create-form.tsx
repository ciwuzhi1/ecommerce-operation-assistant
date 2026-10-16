import { LinkIcon, Plus } from "lucide-react";

type CompetitorCreateFormProps = {
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

/** 渲染 CompetitorCreateForm 组件，集中展示竞品创建表单所需的数据、状态和操作入口。 */
export function CompetitorCreateForm({ canEdit = true, productId }: CompetitorCreateFormProps) {
  if (!canEdit) {
    return <ReadOnlyFormNote title="娣诲姞绔炲搧" />;
  }

  return (
    <form action={`/products/${productId}/competitors/create`} method="post" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-sky-600 text-white">
          <LinkIcon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">添加竞品</h2>
          <p className="text-sm text-slate-500">先录入 3-10 个竞品，后面用于 AI 对比分析</p>
        </div>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">竞品名称</span>
        <input
          name="name"
          required
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="例如：同类爆款饼干"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">平台</span>
          <select
            name="platform"
            defaultValue="douyin"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          >
            {platforms.map((platform) => (
              <option key={platform.value} value={platform.value}>
                {platform.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">售价</span>
          <input
            name="price"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
            placeholder="39.90"
            inputMode="decimal"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">竞品链接</span>
        <input
          name="url"
          type="url"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="https://..."
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">标题/销量提示</span>
        <input
          name="title"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="可粘贴商品标题或销量提示"
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">卖点关键词</span>
        <textarea
          name="selling_points"
          className="mt-2 min-h-20 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="用逗号或换行分隔，例如：低价、大规格、买一送一"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        添加竞品
      </button>
    </form>
  );
}

/** 渲染 ReadOnlyFormNote 组件，集中展示读取only表单note所需的数据、状态和操作入口。 */
function ReadOnlyFormNote({ title }: { title: string }) {
  return (
    <div>
      <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
        当前账号为只读权限，不能新增或导入数据。
      </p>
    </div>
  );
}
