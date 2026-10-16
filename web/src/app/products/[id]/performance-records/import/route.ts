import { redirect } from "next/navigation";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

type RouteContext = {
  params: Promise<{ id: string }>;
};

type ImportedPerformanceRecord = {
  ad_experiment_id?: number | null;
  creative_plan_id?: number | null;
  generated_asset_id?: number | null;
  promotion_link_id?: number | null;
  promotion_tracking_code?: string | null;
  period_start: string;
  period_end: string;
  impressions?: number | null;
  clicks?: number | null;
  ctr?: string | null;
  conversions?: number | null;
  conversion_rate?: string | null;
  spend?: string | null;
  revenue?: string | null;
  roi?: string | null;
  notes?: string | null;
};

const headerAliases: Record<string, keyof ImportedPerformanceRecord> = {
  period_start: "period_start",
  start_date: "period_start",
  start: "period_start",
  日期: "period_start",
  开始日期: "period_start",
  period_end: "period_end",
  end_date: "period_end",
  end: "period_end",
  结束日期: "period_end",
  creative_plan_id: "creative_plan_id",
  plan_id: "creative_plan_id",
  ad_experiment_id: "ad_experiment_id",
  experiment_id: "ad_experiment_id",
  generated_asset_id: "generated_asset_id",
  asset_id: "generated_asset_id",
  promotion_link_id: "promotion_link_id",
  promotion_tracking_code: "promotion_tracking_code",
  tracking_code: "promotion_tracking_code",
  eo_tracking_code: "promotion_tracking_code",
  impressions: "impressions",
  exposure: "impressions",
  曝光: "impressions",
  clicks: "clicks",
  click: "clicks",
  点击: "clicks",
  ctr: "ctr",
  conversions: "conversions",
  conversion: "conversions",
  成交: "conversions",
  conversion_rate: "conversion_rate",
  cvr: "conversion_rate",
  spend: "spend",
  cost: "spend",
  花费: "spend",
  revenue: "revenue",
  sales: "revenue",
  成交额: "revenue",
  roi: "roi",
  notes: "notes",
  note: "notes",
  备注: "notes",
};

/** 处理商品/经营数据记录/导入请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const formData = await request.formData();
  const csvFile = formData.get("csv_file");

  if (!(csvFile instanceof File)) {
    redirect(`/products/${id}?tab=review&import=failed`);
  }

  const records = parsePerformanceCsv(await csvFile.text());
  if (records.length === 0) {
    redirect(`/products/${id}?tab=review&import=empty`);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/products/${id}/performance-records/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ records }),
  });

  if (!response.ok) {
    redirect(`/products/${id}?tab=review&import=failed`);
  }

  redirect(`/products/${id}?tab=review&import=success&count=${records.length}`);
}

/** 解析经营数据CSV，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function parsePerformanceCsv(csvText: string): ImportedPerformanceRecord[] {
  const table = parseCsvTable(csvText.replace(/^\uFEFF/, ""));
  if (table.length < 2) {
    return [];
  }

  const headers = table[0].map((header) => headerAliases[normalizeHeader(header)] ?? null);
  return table
    .slice(1)
    .map((row) => normalizeRow(headers, row))
    .filter((record): record is ImportedPerformanceRecord => record !== null);
}

/** 解析CSVtable，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function parseCsvTable(csvText: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < csvText.length; index += 1) {
    const char = csvText[index];
    const nextChar = csvText[index + 1];

    if (char === '"' && inQuotes && nextChar === '"') {
      cell += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell.trim());
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      row.push(cell.trim());
      if (row.some((value) => value.length > 0)) {
        rows.push(row);
      }
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  row.push(cell.trim());
  if (row.some((value) => value.length > 0)) {
    rows.push(row);
  }

  return rows;
}

/** normalize表头，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function normalizeHeader(header: string): string {
  return header.trim().replace(/\s+/g, "_").toLowerCase();
}

/** normalize行，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function normalizeRow(
  headers: Array<keyof ImportedPerformanceRecord | null>,
  row: string[],
): ImportedPerformanceRecord | null {
  const values: Partial<Record<keyof ImportedPerformanceRecord, string>> = {};

  headers.forEach((header, index) => {
    if (!header) {
      return;
    }
    values[header] = row[index]?.trim() ?? "";
  });

  const periodStart = values.period_start?.trim();
  const periodEnd = values.period_end?.trim() || periodStart;
  if (!periodStart || !periodEnd) {
    return null;
  }

  return {
    ad_experiment_id: toNumber(values.ad_experiment_id),
    creative_plan_id: toNumber(values.creative_plan_id),
    generated_asset_id: toNumber(values.generated_asset_id),
    promotion_link_id: toNumber(values.promotion_link_id),
    promotion_tracking_code: emptyToNull(values.promotion_tracking_code),
    period_start: periodStart,
    period_end: periodEnd,
    impressions: toNumber(values.impressions),
    clicks: toNumber(values.clicks),
    ctr: rateToDecimal(values.ctr),
    conversions: toNumber(values.conversions),
    conversion_rate: rateToDecimal(values.conversion_rate),
    spend: emptyToNull(values.spend),
    revenue: emptyToNull(values.revenue),
    roi: rateToDecimal(values.roi),
    notes: emptyToNull(values.notes),
  };
}

/** 空状态到null，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function emptyToNull(value?: string): string | null {
  return value && value.trim() ? value.trim() : null;
}

/** rate到小数，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function rateToDecimal(value?: string): string | null {
  if (!value || !value.trim()) {
    return null;
  }
  const normalized = value.trim();
  if (!normalized.endsWith("%")) {
    return normalized;
  }

  const number = Number(normalized.slice(0, -1).replace(/,/g, ""));
  if (!Number.isFinite(number)) {
    return null;
  }
  return String(number / 100);
}

/** 到数值，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function toNumber(value?: string): number | null {
  if (!value || !value.trim()) {
    return null;
  }
  const normalized = value.replace(/,/g, "");
  const number = Number(normalized);
  return Number.isFinite(number) ? number : null;
}


