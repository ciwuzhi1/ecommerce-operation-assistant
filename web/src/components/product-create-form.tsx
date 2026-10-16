import { Plus, Sparkles } from "lucide-react";
import type { Store } from "@/types";

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

type ProductCreateFormProps = {
  stores?: Store[];
};

/** 渲染 ProductCreateForm 组件，集中展示商品创建表单所需的数据、状态和操作入口。 */
export function ProductCreateForm({ stores = [] }: ProductCreateFormProps) {
  return (
    <form action="/products/create" method="post" className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-600 text-white">
          <Sparkles className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-950">新建单品</h2>
          <p className="text-sm text-slate-500">先把一个商品跑完整运营链路</p>
        </div>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">商品名称</span>
        <input
          name="name"
          required
          className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          placeholder="例如：低糖燕麦饼干"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">所属店铺</span>
          <select
            name="store_id"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          >
            <option value="">暂不绑定</option>
            {stores.map((store) => (
              <option key={store.id} value={store.id}>
                {store.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">平台</span>
          <select
            name="platform"
            defaultValue="douyin"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          >
            {platforms.map((platform) => (
              <option key={platform.value} value={platform.value}>
                {platform.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">类目</span>
          <input
            name="category"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
            placeholder="食品 / 家居 / 美妆"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">售价</span>
          <input
            name="price"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
            placeholder="29.90"
            inputMode="decimal"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">目标人群</span>
          <input
            name="target_audience"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
            placeholder="年轻上班族"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">核心卖点</span>
        <textarea
          name="selling_points"
          className="mt-2 min-h-24 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          placeholder="用逗号或换行分隔，例如：低糖、饱腹、独立包装"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        创建商品
      </button>
    </form>
  );
}
