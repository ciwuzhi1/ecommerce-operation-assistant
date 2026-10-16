import { ArrowLeft, Download, FileSpreadsheet, Upload } from "lucide-react";
import Link from "next/link";

import { PerformanceImportCenterPanel, ProductImportPanel, SkuInventoryImportPanel } from "@/components/product-import-panel";

const templates = [
  {
    title: "商品档案模板",
    description: "用于导入店铺商品、平台、价格、受众、卖点和平台商品 ID。",
    href: "/workspace/templates/products",
  },
  {
    title: "SKU 库存模板",
    description: "用于导入 SKU 编码、规格、初始库存、预警线、仓位和平台 SKU ID。",
    href: "/workspace/templates/sku-inventory",
  },
  {
    title: "经营数据模板",
    description: "用于导入曝光、点击、成交、花费、成交额等投放复盘数据。",
    href: "/workspace/templates/performance-records",
  },
  {
    title: "字段映射模板",
    description: "用于把淘宝、天猫、拼多多、京东、抖音等平台字段映射到系统字段。",
    href: "/workspace/templates/field-mapping",
  },
];

/** 渲染导入页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default function ImportCenterPage() {
  return (
    <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div>
          <Link
            href="/"
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            返回工作台
          </Link>
        </div>

        <header className="rounded-md border border-slate-200 bg-white p-5">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-slate-950 text-white">
              <Upload className="h-6 w-6" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-medium text-cyan-700">Data Import</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-normal text-slate-950">导入中心</h1>
              <p className="mt-2 text-sm text-slate-500">
                汇总商品、SKU 库存、经营数据和平台字段映射模板，后续承接导入预览和错误行提示。
              </p>
            </div>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-2">
          {templates.map((template) => (
            <div key={template.href} className="rounded-md border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan-50 text-cyan-700">
                    <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">{template.title}</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{template.description}</p>
                  </div>
                </div>
                <Link
                  href={template.href}
                  className="inline-flex h-9 shrink-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  <Download className="h-3.5 w-3.5" aria-hidden="true" />
                  下载
                </Link>
              </div>
            </div>
          ))}
        </section>

        <ProductImportPanel />
        <SkuInventoryImportPanel />
        <PerformanceImportCenterPanel />

        <section className="rounded-md border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-950">已接入能力</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <StatusCard title="经营数据 CSV" status="已支持预览" />
            <StatusCard title="字段映射模板" status="已提供" />
            <StatusCard title="商品/SKU 导入预览" status="已接入" />
          </div>
        </section>
      </div>
    </main>
  );
}

/** 渲染 StatusCard 组件，集中展示状态卡片所需的数据、状态和操作入口。 */
function StatusCard({ title, status }: { title: string; status: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-2 text-sm text-slate-500">{status}</p>
    </div>
  );
}
