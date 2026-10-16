import {
  ArrowRight,
  Bot,
  Boxes,
  Building2,
  ClipboardList,
  Database,
  Download,
  FileText,
  ImageIcon,
  Megaphone,
  Package,
  Settings,
  Store as StoreIcon,
} from "lucide-react";
import Link from "next/link";

import { ProductCreateForm } from "@/components/product-create-form";
import { StoreCreateForm } from "@/components/store-create-form";
import { getCurrentUser, getProducts, getStores } from "@/lib/api";
import { getAuthToken } from "@/lib/session";
import type { Platform, Product, Store } from "@/types";

const platformLabels: Record<Platform, string> = {
  douyin: "抖音",
  taobao: "淘宝",
  tmall: "天猫",
  pinduoduo: "拼多多",
  jd: "京东",
  tiktok_shop: "TikTok",
  amazon: "Amazon",
  other: "其他",
};

const platformFilters: Array<{ value: "all" | Platform; label: string }> = [
  { value: "all", label: "全部平台" },
  { value: "douyin", label: "抖音" },
  { value: "taobao", label: "淘宝" },
  { value: "tmall", label: "天猫" },
  { value: "pinduoduo", label: "拼多多" },
  { value: "jd", label: "京东" },
];

const workflow = [
  { title: "建店建档", icon: Building2, tone: "bg-sky-100 text-sky-700", href: "/" },
  { title: "导入数据", icon: ClipboardList, tone: "bg-cyan-100 text-cyan-700", href: "/imports" },
  { title: "补商品信息", icon: ImageIcon, tone: "bg-emerald-100 text-emerald-700", href: "/?workflow=product" },
  { title: "投放建议", icon: Megaphone, tone: "bg-amber-100 text-amber-700", href: "/?workflow=ads" },
  { title: "周期复盘", icon: FileText, tone: "bg-rose-100 text-rose-700", href: "/?workflow=review" },
];

type HomeProps = {
  searchParams?: Promise<{ platform?: string; store?: string; demo?: string }>;
};

/** 渲染首页页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default async function Home({ searchParams }: HomeProps) {
  const query = searchParams ? await searchParams : {};
  const selectedPlatform = parsePlatform(query.platform);
  const selectedStoreId = parseStoreId(query.store);
  // 首页聚合商品、店铺和当前用户权限；写操作入口只在 canEdit 为 true 时展示。
  const [products, stores, token] = await Promise.all([getProducts(), getStores(), getAuthToken()]);
  const currentUser = token ? await getCurrentUser(token) : null;
  const canEdit = Boolean(currentUser?.permissions.can_edit);

  const storeById = new Map(stores.map((store) => [store.id, store]));
  const productsByStore = countProductsByStore(products);
  const activeStores = stores.filter((store) => store.status === "active").length;
  const platformCount = new Set([...stores.map((store) => store.platform), ...products.map((product) => product.platform)]).size;
  const unboundProducts = products.filter((product) => product.store_id === null).length;
  const workflowItems = buildHomeWorkflow(products, stores, unboundProducts);
  const filteredProducts = products.filter((product) => {
    if (selectedPlatform !== "all" && product.platform !== selectedPlatform) {
      return false;
    }
    if (selectedStoreId !== null && product.store_id !== selectedStoreId) {
      return false;
    }
    return true;
  });

  return (
    <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex justify-end gap-2">
          <Link
            href="/agent"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-cyan-700 px-3 text-sm font-medium text-white hover:bg-cyan-800"
          >
            <Bot className="h-4 w-4" aria-hidden="true" />
            Agent 中心
          </Link>
          {currentUser ? (
            <form action="/logout" method="post" className="inline-flex items-center gap-2">
              <span className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-600">
                {currentUser.display_name}
              </span>
              <button
                type="submit"
                className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                退出
              </button>
            </form>
          ) : (
            <Link
              href="/login"
              className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              登录
            </Link>
          )}
          <Link
            href="/settings"
            className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Settings className="h-4 w-4" aria-hidden="true" />
            模型配置
          </Link>
        </div>

        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-cyan-700">Ecommerce Operation Assistant</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
              多平台店铺运营工作台
            </h1>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:w-[560px] sm:grid-cols-4">
            <MetricCard label="店铺" value={stores.length} />
            <MetricCard label="活跃店铺" value={activeStores} />
            <MetricCard label="商品" value={products.length} />
            <MetricCard label="平台" value={platformCount} />
          </div>
        </header>

        <section className="flex flex-col gap-3 rounded-md border border-slate-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-950">演示和导入</h2>
            <p className="mt-1 text-sm text-slate-500">
              用演示数据快速跑通店铺、库存、投放实验和复盘链路，或下载绩效数据导入模板。
            </p>
            {query.demo === "created" ? (
              <p className="mt-2 text-xs font-medium text-emerald-700">演示数据已准备好。</p>
            ) : null}
            {query.demo === "failed" ? (
              <p className="mt-2 text-xs font-medium text-rose-700">演示数据创建失败，请确认当前账号有编辑权限。</p>
            ) : null}
            {!canEdit ? (
              <p className="mt-2 text-xs font-medium text-amber-700">当前账号为只读权限，只能查看数据，不能创建或导入。</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {canEdit ? (
              <form action="/workspace/demo-data" method="post">
                <button
                  type="submit"
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-slate-950 px-3 text-sm font-medium text-white hover:bg-slate-800"
                >
                  <Database className="h-4 w-4" aria-hidden="true" />
                  生成演示数据
                </button>
              </form>
            ) : null}
            <Link
              href="/workspace/templates/performance-records"
              className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              下载导入模板
            </Link>
            {canEdit ? (
              <Link
                href="/imports"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <Package className="h-4 w-4" aria-hidden="true" />
                导入中心
              </Link>
            ) : null}
          </div>
        </section>

        <section className={`grid gap-6 ${canEdit ? "xl:grid-cols-[360px_1fr]" : ""}`}>
          {canEdit ? (
            <div className="flex flex-col gap-6">
              <div className="rounded-md border border-slate-200 bg-white p-5">
                <StoreCreateForm />
              </div>
              <div className="rounded-md border border-slate-200 bg-white p-5">
                <ProductCreateForm stores={stores} />
              </div>
            </div>
          ) : null}

          <div className="flex flex-col gap-6">
            <section className="rounded-md border border-slate-200 bg-white p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold">店铺视图</h2>
                  <p className="mt-1 text-sm text-slate-500">按平台和店铺归拢商品，先把多平台运营入口铺出来</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {platformFilters.map((platform) => (
                    <Link
                      key={platform.value}
                      href={platform.value === "all" ? "/" : `/?platform=${platform.value}`}
                      className={`inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium ${
                        selectedPlatform === platform.value
                          ? "border-cyan-700 bg-cyan-700 text-white"
                          : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      {platform.label}
                    </Link>
                  ))}
                </div>
              </div>

              <div className="mt-5 grid gap-3 lg:grid-cols-2">
                {stores.length === 0 ? (
                  <div className="rounded-md border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
                    还没有店铺，先在左侧创建一个平台店铺。
                  </div>
                ) : (
                  stores.map((store) => (
                    <StoreSummaryCard
                      key={store.id}
                      store={store}
                      productCount={productsByStore.get(store.id) ?? 0}
                      selected={store.id === selectedStoreId}
                    />
                  ))
                )}
                {unboundProducts > 0 ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-4">
                    <div className="flex items-center gap-3">
                      <Package className="h-5 w-5 text-amber-700" aria-hidden="true" />
                      <div>
                        <p className="text-sm font-semibold text-slate-950">未绑定店铺商品</p>
                        <p className="mt-1 text-xs text-amber-800">{unboundProducts} 个商品需要补店铺归属</p>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>

            <section className="rounded-md border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold">商品池</h2>
                  <p className="mt-1 text-sm text-slate-500">围绕每个商品补竞品、出素材、做投放实验和复盘</p>
                </div>
                <span className="inline-flex h-8 items-center gap-1.5 rounded-md bg-slate-100 px-3 text-xs font-medium text-slate-600">
                  <Boxes className="h-3.5 w-3.5" aria-hidden="true" />
                  {filteredProducts.length} / {products.length}
                </span>
              </div>

              <div className="mt-5 overflow-hidden rounded-md border border-slate-200">
                <div className="hidden grid-cols-[1.3fr_0.9fr_0.8fr_0.7fr_1fr_96px] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500 lg:grid">
                  <span>商品</span>
                  <span>店铺</span>
                  <span>平台</span>
                  <span>售价</span>
                  <span>卖点</span>
                  <span>动作</span>
                </div>

                {filteredProducts.length === 0 ? (
                  <div className="px-4 py-12 text-center text-sm text-slate-500">
                    当前筛选下没有商品，可以新建商品或切换平台。
                  </div>
                ) : (
                  <div className="divide-y divide-slate-200">
                    {filteredProducts.map((product) => (
                      <ProductRow key={product.id} product={product} store={product.store_id ? storeById.get(product.store_id) : null} />
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-5">
          {workflow.map((item) => {
            const Icon = item.icon;
            const workflowItem = workflowItems.get(item.title);
            return (
              <Link
                key={item.title}
                href={workflowItem?.href ?? item.href}
                className="rounded-md border border-slate-200 bg-white p-4 transition hover:border-cyan-200 hover:bg-cyan-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className={`flex h-9 w-9 items-center justify-center rounded-md ${item.tone}`}>
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                    {workflowItem?.count ?? 0}
                  </span>
                </div>
                <h3 className="mt-4 text-sm font-semibold text-slate-950">{item.title}</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">{workflowItem?.hint ?? "查看下一步"}</p>
              </Link>
            );
          })}
        </section>
      </div>
    </main>
  );
}

/** 构建首页工作流，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildHomeWorkflow(products: Product[], stores: Store[], unboundProducts: number): Map<string, { count: number; hint: string; href: string }> {
  // 工作流卡片只用已有数据提示下一步，不自动创建诊断、素材或投放实验。
  const missingSellingPoints = products.filter((product) => product.selling_points.length === 0).length;
  const missingPlatformIds = products.filter((product) => !product.external_product_id).length;
  const productsReadyForOps = products.filter((product) => product.store_id !== null && product.selling_points.length > 0).length;

  return new Map([
    [
      "建店建档",
      {
        count: stores.length + products.length,
        hint: unboundProducts > 0 ? `${unboundProducts} 个商品待绑定店铺` : "店铺和商品入口",
        href: "/",
      },
    ],
    [
      "导入数据",
      {
        count: missingPlatformIds,
        hint: missingPlatformIds > 0 ? `${missingPlatformIds} 个商品待补平台 ID` : "导入商品/SKU/经营数据",
        href: "/imports",
      },
    ],
    [
      "补商品信息",
      {
        count: missingSellingPoints,
        hint: missingSellingPoints > 0 ? `${missingSellingPoints} 个商品待补卖点` : "进入单品运营闭环",
        href: firstProductHref(products, "overview"),
      },
    ],
    [
      "投放建议",
      {
        count: productsReadyForOps,
        hint: productsReadyForOps > 0 ? "从素材和链接生成投放建议" : "先补商品基础信息",
        href: firstProductHref(products, "ads"),
      },
    ],
    [
      "周期复盘",
      {
        count: products.length,
        hint: products.length > 0 ? "回填经营数据后生成复盘" : "先创建商品",
        href: firstProductHref(products, "review"),
      },
    ],
  ]);
}

/** 首个商品链接，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function firstProductHref(products: Product[], tab: string): string {
  return products[0] ? `/products/${products[0].id}?tab=${tab}` : "/";
}

/** 渲染 MetricCard 组件，集中展示指标卡片所需的数据、状态和操作入口。 */
function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

/** 渲染 StoreSummaryCard 组件，集中展示店铺汇总卡片所需的数据、状态和操作入口。 */
function StoreSummaryCard({
  store,
  productCount,
  selected,
}: {
  store: Store;
  productCount: number;
  selected: boolean;
}) {
  return (
    <div
      className={`rounded-md border px-4 py-4 transition ${
        selected ? "border-cyan-700 bg-cyan-50" : "border-slate-200 bg-white hover:bg-slate-50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-700">
            <StoreIcon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-950">{store.name}</p>
            <p className="mt-1 text-xs text-slate-500">{platformLabels[store.platform]}</p>
          </div>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
          {store.status === "active" ? "启用" : store.status === "paused" ? "暂停" : "关闭"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-slate-500">商品数</p>
          <p className="mt-1 font-semibold text-slate-950">{productCount}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">负责人</p>
          <p className="mt-1 truncate font-semibold text-slate-950">{store.owner_name ?? "-"}</p>
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <Link
          href={`/?store=${store.id}`}
          className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          筛选商品
        </Link>
        <Link
          href={`/stores/${store.id}`}
          className="inline-flex h-8 items-center rounded-md bg-slate-950 px-3 text-xs font-medium text-white hover:bg-slate-800"
        >
          店铺详情
        </Link>
      </div>
    </div>
  );
}

/** 渲染 ProductRow 组件，集中展示商品行所需的数据、状态和操作入口。 */
function ProductRow({ product, store }: { product: Product; store: Store | null | undefined }) {
  return (
    <div className="grid gap-3 px-4 py-4 text-sm lg:min-h-16 lg:grid-cols-[1.3fr_0.9fr_0.8fr_0.7fr_1fr_96px] lg:items-center lg:gap-0 lg:py-3">
      <div>
        <p className="font-medium text-slate-950">{product.name}</p>
        <p className="mt-1 text-xs text-slate-500">{product.category ?? "未分类"}</p>
      </div>
      <span className="text-slate-600">{store?.name ?? "未绑定"}</span>
      <span className="text-slate-600">{platformLabels[product.platform]}</span>
      <span className="font-medium text-slate-800">{product.price ? `¥${product.price}` : "-"}</span>
      <div className="flex flex-wrap gap-1.5">
        {product.selling_points.slice(0, 3).map((point) => (
          <span key={point} className="rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
            {point}
          </span>
        ))}
      </div>
      <Link
        href={`/products/${product.id}`}
        className="inline-flex h-9 w-24 items-center justify-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        进入
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
    </div>
  );
}

/** 统计商品by店铺，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function countProductsByStore(products: Product[]): Map<number, number> {
  return products.reduce((counts, product) => {
    if (product.store_id !== null) {
      counts.set(product.store_id, (counts.get(product.store_id) ?? 0) + 1);
    }
    return counts;
  }, new Map<number, number>());
}

/** 解析平台，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function parsePlatform(value: string | undefined): "all" | Platform {
  // URL 筛选参数做白名单校验，避免无效平台值影响服务端渲染结果。
  if (!value || value === "all") {
    return "all";
  }
  return Object.hasOwn(platformLabels, value) ? (value as Platform) : "all";
}

/** 解析店铺ID，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function parseStoreId(value: string | undefined): number | null {
  if (!value) {
    return null;
  }
  const storeId = Number(value);
  return Number.isInteger(storeId) && storeId > 0 ? storeId : null;
}
