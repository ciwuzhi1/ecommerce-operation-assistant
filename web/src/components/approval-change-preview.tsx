/** 变更预览：展示写入类审批将产生的实际影响。
 *
 * 依据 PRD FR-75～FR-77 与 M-02：库存调整（inventory.adjust）与草稿采用（artifact.persist）
 * 属于不可逆写入，批准前须让审批人看到变更前后对比。
 * 本组件只从审批 request_payload 推导可读的 before / after，不直接透出原始 JSON。
 */

type ChangePreview = {
  actionLabel: string;
  beforeLabel: string;
  beforeValue: string;
  afterLabel: string;
  afterValue: string;
};

/** 渲染审批变更预览；无法推导具体数值时给出不可撤销的通用提示。 */
export function ApprovalChangePreview({ requestPayload }: { requestPayload: Record<string, unknown> }) {
  const preview = deriveChangePreview(requestPayload);
  return (
    <div className="rounded-md border border-rose-200 bg-rose-50/50 p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-900">变更预览</h3>
        <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">
          不可逆写入
        </span>
        {preview ? (
          <span className="ml-auto text-xs font-medium text-slate-500">{preview.actionLabel}</span>
        ) : null}
      </div>
      {preview ? (
        <div className="mt-3 grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <div className="rounded-md bg-white p-3">
            <p className="text-xs text-slate-500">{preview.beforeLabel}</p>
            <p className="mt-1 font-mono text-xl font-semibold text-slate-500">{preview.beforeValue}</p>
          </div>
          <p className="text-center text-lg text-slate-400" aria-hidden="true">
            →
          </p>
          <div className="rounded-md bg-white p-3">
            <p className="text-xs text-slate-500">{preview.afterLabel}</p>
            <p className="mt-1 font-mono text-xl font-semibold text-rose-700">{preview.afterValue}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-xs leading-5 text-slate-600">
          该审批属于写入正式对象的动作，批准后不可撤销；请结合下方「审批内容」核对影响范围。
        </p>
      )}
      <p className="mt-3 text-xs text-slate-500">
        原始载荷字段 {Object.keys(requestPayload).length} 个
      </p>
    </div>
  );
}

/** 由审批载荷推导变更前后；无法识别时返回 null，由调用方给出通用提示。 */
function deriveChangePreview(requestPayload: Record<string, unknown>): ChangePreview | null {
  // 草稿采用（artifact.persist / workflow.accept_result）：把结构化草稿写入正式业务对象。
  const draft = requestPayload.draft_output;
  if (isRecord(draft)) {
    const diagnosisCount = isRecord(draft.diagnosis) ? 1 : 0;
    const planCount = Array.isArray(draft.creative_plans) ? draft.creative_plans.length : 0;
    return {
      actionLabel: "采用草稿为正式业务对象",
      beforeLabel: "正式库现状",
      beforeValue: "未写入",
      afterLabel: "采用后写入",
      afterValue: `诊断 ${diagnosisCount} 条 · 创意方案 ${planCount} 个`,
    };
  }

  // 库存调整（inventory.adjust）：必须展示变更前后数量。
  const before = readNumber(requestPayload, ["before_quantity", "current_quantity", "before"]);
  const after = readNumber(requestPayload, ["after_quantity", "new_quantity", "after"]);
  const delta = readNumber(requestPayload, ["quantity_delta", "delta", "quantity"]);
  if (before !== null || after !== null || delta !== null) {
    const resolvedBefore = before ?? (after !== null && delta !== null ? after - delta : null);
    const resolvedAfter = after ?? (before !== null && delta !== null ? before + delta : null);
    return {
      actionLabel: "库存数量调整",
      beforeLabel: "调整前库存",
      beforeValue: resolvedBefore === null ? "—" : formatNumber(resolvedBefore),
      afterLabel: "调整后库存",
      afterValue: resolvedAfter === null ? formatSigned(delta) : formatNumber(resolvedAfter),
    };
  }

  // 投放实验创建（FR-76）：展示将创建的实验预算。
  const budget = readNumber(requestPayload, ["daily_budget", "budget"]);
  if (budget !== null) {
    return {
      actionLabel: "创建正式投放实验",
      beforeLabel: "正式实验",
      beforeValue: "未创建",
      afterLabel: "创建后预算",
      afterValue: `${formatNumber(budget)} / 天`,
    };
  }

  return null;
}

/** 判断值是否为普通对象（排除数组与 null）。 */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** 从载荷中按候选键读取数字；支持数值与数字字符串，缺失时返回 null。 */
function readNumber(payload: Record<string, unknown>, keys: string[]): number | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

/** 格式化数字，整数不带小数点。 */
function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

/** 只有增量时以带符号形式展示。 */
function formatSigned(delta: number | null): string {
  if (delta === null) {
    return "—";
  }
  return `${delta >= 0 ? "+" : ""}${formatNumber(delta)}`;
}
