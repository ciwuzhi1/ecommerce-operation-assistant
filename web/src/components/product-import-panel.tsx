"use client";

import { Loader2, Upload } from "lucide-react";
import { useState } from "react";

type ImportRow = {
  row_number: number;
  status: "valid" | "created" | "error" | string;
  errors: string[];
  product_id: number | null;
  product_name: string | null;
  store_name: string | null;
  sku_code?: string | null;
  sku_name?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  record_id?: number | null;
  platform: string | null;
};

type ImportResult = {
  commit: boolean;
  total_rows: number;
  valid_rows: number;
  created_count: number;
  error_count: number;
  rows: ImportRow[];
};

type CsvImportPanelProps = {
  title: string;
  description: string;
  endpoint: string;
  fileLabel: string;
  itemLabel: string;
};

/** 渲染 CsvImportPanel 组件，集中展示CSV导入面板所需的数据、状态和操作入口。 */
export function CsvImportPanel({
  title,
  description,
  endpoint,
  fileLabel,
  itemLabel,
}: CsvImportPanelProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** 保存本次选择的文件；实际读取动作放到“预览/确认导入”时执行。 */
  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    // 浏览器连续选择同一个文件时，不会再次触发 change；读取完本次文件后清空控件，
    // 这样学生可反复选择同一份 CSV 进行预览和修正。
    input.value = "";
    setResult(null);
    setError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  }

  /** 处理提交导入交互，维护必要状态并把副作用交给受控路由或后端 API。 */
  async function submitImport(commit: boolean) {
    // 导入中心采用“预览 -> 确认导入”两段式，commit=false 不写库，避免表格错误直接污染数据。
    if (!selectedFile) {
      setError("请先选择商品 CSV 文件。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // 不在选文件时异步读取，避免文件读取状态意外把“预览”按钮锁死。
      const csvText = await selectedFile.text();
      if (!csvText.trim()) {
        throw new Error("所选 CSV 文件为空。");
      }
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_text: csvText, commit }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { error?: string } | null;
        throw new Error(`${response.status}: ${payload?.error ?? "导入请求失败"}`);
      }
      // 后端返回逐行结果，前端只展示可导入/错误/已创建状态，不在浏览器端自行修正数据。
      setResult((await response.json()) as ImportResult);
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : "导入请求失败";
      if (message.startsWith("401:")) {
        setError("前端工作台尚未登录。请先在 http://127.0.0.1:3000/login 登录，再返回本页预览。");
      } else if (message.startsWith("403:")) {
        setError("当前工作台账号没有导入权限，请使用具有编辑权限的账号登录。");
      } else {
        setError(`${itemLabel}导入失败：${message}`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="rounded-md border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => submitImport(false)}
            disabled={loading}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            预览
          </button>
          <button
            type="button"
            onClick={() => submitImport(true)}
            disabled={loading || !result || result.valid_rows === 0}
            className="inline-flex h-9 items-center gap-2 rounded-md bg-slate-950 px-3 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            确认导入
          </button>
        </div>
      </div>

      <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center">
        <Upload className="mx-auto h-6 w-6 text-slate-400" aria-hidden="true" />
        <span className="mt-2 block text-sm font-medium text-slate-700">{fileLabel}</span>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={handleFileChange}
          className="mx-auto mt-3 block w-full max-w-md cursor-pointer rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded file:border-0 file:bg-slate-950 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-slate-800"
        />
      </div>

      {selectedFile ? (
        <p className="mt-3 text-sm font-medium text-emerald-700">
          已选择文件：{selectedFile.name}。点击“预览”时才会读取并校验文件内容。
        </p>
      ) : (
        <p className="mt-3 text-sm text-slate-500">选择 CSV 文件后，需要点击“预览”才会发送导入请求。</p>
      )}

      {error ? <p className="mt-4 text-sm font-medium text-rose-700">{error}</p> : null}

      {result ? (
        <div className="mt-5">
          <div className="grid gap-3 md:grid-cols-4">
            <ImportMetric label="总行数" value={result.total_rows} />
            <ImportMetric label="有效行" value={result.valid_rows} />
            <ImportMetric label="已创建" value={result.created_count} />
            <ImportMetric label="错误行" value={result.error_count} />
          </div>
          <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
            <div className="hidden grid-cols-[80px_90px_1fr_1fr_1.5fr] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500 lg:grid">
              <span>行号</span>
              <span>状态</span>
              <span>{itemLabel}</span>
              <span>关联</span>
              <span>错误</span>
            </div>
            <div className="divide-y divide-slate-200">
              {result.rows.map((row) => (
                <div
                  key={row.row_number}
                  className="grid gap-2 px-4 py-3 text-sm lg:grid-cols-[80px_90px_1fr_1fr_1.5fr] lg:items-center"
                >
                  <span className="text-slate-600">{row.row_number}</span>
                  <span className={row.status === "error" ? "font-medium text-rose-700" : "font-medium text-emerald-700"}>
                    {statusLabel(row.status)}
                  </span>
                  <span className="text-slate-900">{row.product_name ?? row.sku_name ?? "-"}</span>
                  <span className="text-slate-600">{relatedText(row)}</span>
                  <span className="text-slate-600">{row.errors.length > 0 ? row.errors.join("；") : "-"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** 渲染 ProductImportPanel 组件，集中展示商品导入面板所需的数据、状态和操作入口。 */
export function ProductImportPanel() {
  return (
    <CsvImportPanel
      title="商品 CSV 导入"
      description="先预览字段和错误行，确认后只导入有效商品行。"
      endpoint="/imports/products"
      fileLabel="选择商品 CSV 文件"
      itemLabel="商品"
    />
  );
}

/** 渲染 SkuInventoryImportPanel 组件，集中展示SKU库存导入面板所需的数据、状态和操作入口。 */
export function SkuInventoryImportPanel() {
  return (
    <CsvImportPanel
      title="SKU 库存 CSV 导入"
      description="按商品名称匹配已有商品，导入 SKU、初始库存、预警线和仓位。"
      endpoint="/imports/sku-inventory"
      fileLabel="选择 SKU 库存 CSV 文件"
      itemLabel="SKU"
    />
  );
}

/** 渲染 PerformanceImportCenterPanel 组件，集中展示经营数据导入中心面板所需的数据、状态和操作入口。 */
export function PerformanceImportCenterPanel() {
  return (
    <CsvImportPanel
      title="经营数据 CSV 导入"
      description="按商品名称或平台商品 ID 匹配商品，预览后导入曝光、点击、成交、花费和成交额。"
      endpoint="/imports/performance-records"
      fileLabel="选择经营数据 CSV 文件"
      itemLabel="经营数据"
    />
  );
}

/** 渲染 ImportMetric 组件，集中展示导入指标所需的数据、状态和操作入口。 */
function ImportMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

/** 把状态状态映射为中文显示文本，保持页面口径一致。 */
function statusLabel(status: string): string {
  if (status === "valid") {
    return "可导入";
  }
  if (status === "created") {
    return "已创建";
  }
  if (status === "error") {
    return "错误";
  }
  return status;
}

/** 关联文本，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function relatedText(row: ImportRow): string {
  if (row.store_name) {
    return row.store_name;
  }
  if (row.sku_code) {
    return row.sku_code;
  }
  if (row.period_start) {
    return `${row.period_start} 至 ${row.period_end ?? row.period_start}`;
  }
  if (row.record_id) {
    return `记录 #${row.record_id}`;
  }
  return "-";
}
