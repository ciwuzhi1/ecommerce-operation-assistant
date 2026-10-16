"use client";

import {
  Bot,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileCheck2,
  LoaderCircle,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { AGENT_ERROR_MESSAGES } from "@/lib/agent-error";
import type { AgentDraftOutput, AgentRun, AgentRunStatus } from "@/types";

type AgentRunPanelProps = {
  productId: number;
  initialRuns: AgentRun[];
  canEdit: boolean;
};

const activeStatuses: AgentRunStatus[] = ["queued", "running", "awaiting_review", "resume_queued"];

const specialistSteps = [
  { key: "product_context_agent", label: "商品上下文", icon: Bot },
  { key: "diagnosis_agent", label: "运营诊断", icon: Sparkles },
  { key: "creative_strategy_agent", label: "创意策略", icon: FileCheck2 },
  { key: "quality_review_agent", label: "质量审核", icon: ShieldCheck },
] as const;

/** 渲染智能体运行面板：启动运行、展示专家协作进度、质量审核、运行轨迹与人工复核入口。 */
export function AgentRunPanel({ productId, initialRuns, canEdit }: AgentRunPanelProps) {
  const [runs, setRuns] = useState(initialRuns);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const latestRun = runs[0] ?? null;
  const [draftJson, setDraftJson] = useState(() => formatDraft(latestRun));
  const latestRunId = latestRun?.id;
  const latestRunStatus = latestRun?.status;

  useEffect(() => {
    if (!latestRunId || !latestRunStatus || !["queued", "running", "resume_queued"].includes(latestRunStatus)) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/agent-runs/${latestRunId}`, { cache: "no-store" });
        if (!response.ok) return;
        const updated = (await response.json()) as AgentRun;
        setRuns((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
        if (updated.status === "awaiting_review") {
          setDraftJson(formatDraft(updated));
        }
      } catch {
        // 短时轮询失败不打断用户操作，下一轮继续读取运行状态。
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [latestRunId, latestRunStatus]);

  const hasActiveRun = latestRun ? activeStatuses.includes(latestRun.status) : false;
  const latestEvents = useMemo(
    () => [...(latestRun?.events ?? [])].sort((a, b) => b.id - a.id).slice(0, 12),
    [latestRun?.events],
  );

  /** 启动一次受控运行，并把最新运行记录置顶展示。 */
  async function startRun() {
    setSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`/products/${productId}/agent-runs`, { method: "POST" });
      const run = await readResponse(response);
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
      setDraftJson(formatDraft(run));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "启动 Agent 失败");
    } finally {
      setSubmitting(false);
    }
  }

  /** 提交人工复核决策：通过 / 修改后通过（需完整 edited_output）/ 驳回。 */
  async function submitReview(decision: "approve" | "edit_and_approve" | "reject") {
    if (!latestRun) return;
    setSubmitting(true);
    setError(null);
    try {
      let editedOutput: AgentDraftOutput | undefined;
      if (decision === "edit_and_approve") {
        editedOutput = JSON.parse(draftJson) as AgentDraftOutput;
        if (!editedOutput.diagnosis || !Array.isArray(editedOutput.creative_plans)) {
          throw new Error("编辑内容必须包含 diagnosis 和 creative_plans");
        }
      }
      const response = await fetch(`/agent-runs/${latestRun.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          note: reviewNote.trim() || null,
          ...(editedOutput ? { edited_output: editedOutput } : {}),
        }),
      });
      const run = await readResponse(response);
      setRuns((current) => [run, ...current.filter((item) => item.id !== run.id)]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "提交复核失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.55fr)]">
      <div className="grid gap-6">
        <div className="rounded-md border border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-emerald-700">
                <Bot className="h-5 w-5" aria-hidden="true" />
                <span className="text-sm font-semibold">商品运营 Agent</span>
              </div>
              <h2 className="mt-2 text-xl font-semibold text-slate-950">从商品信息到可审核运营方案</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                内部专家按固定流程协作，质量不达标最多返修一次；最终结果只有人工确认后才写入诊断和创意方案。
              </p>
            </div>
            <button
              type="button"
              onClick={startRun}
              disabled={!canEdit || submitting || hasActiveRun}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {hasActiveRun ? "运行进行中" : "启动运营 Agent"}
            </button>
          </div>
          {error ? (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {error}
            </div>
          ) : null}
        </div>

        {latestRun ? (
          <>
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                    Run #{latestRun.id} · v{latestRun.workflow_version}
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">专家协作进度</h3>
                </div>
                <RunStatusBadge status={latestRun.status} />
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-4">
                {specialistSteps.map((step) => {
                  const state = specialistState(latestRun, step.key);
                  const Icon = step.icon;
                  return (
                    <div key={step.key} className="rounded-md border border-slate-200 p-4">
                      <div className="flex items-center justify-between">
                        <Icon className="h-5 w-5 text-slate-600" aria-hidden="true" />
                        <StepStateIcon state={state} />
                      </div>
                      <p className="mt-3 text-sm font-semibold text-slate-900">{step.label}</p>
                      <p className="mt-1 text-xs text-slate-500">{stepStateLabel(state)}</p>
                    </div>
                  );
                })}
              </div>
              <div className="mt-5 flex flex-wrap gap-4 text-xs text-slate-500">
                <span>
                  返修 {latestRun.revision_count}/{latestRun.max_revisions}
                </span>
                <span>模型调用 {numberValue(latestRun.usage.calls)} 次</span>
                <span>Token {numberValue(latestRun.usage.total_tokens)}</span>
              </div>
            </div>

            <QualityPanel run={latestRun} />
            {latestRun.status === "awaiting_review" ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 p-6">
                <div className="flex items-center gap-2 text-amber-800">
                  <UserCheck className="h-5 w-5" aria-hidden="true" />
                  <h3 className="text-lg font-semibold">等待人工复核</h3>
                </div>
                <p className="mt-2 text-sm leading-6 text-amber-800/80">
                  可直接通过、编辑完整结构化草稿后通过，或驳回。本步骤不会自动执行投放或资金操作。
                </p>
                <label className="mt-5 block text-sm font-medium text-slate-700" htmlFor="agent-draft-json">
                  结构化草稿（可编辑）
                </label>
                <textarea
                  id="agent-draft-json"
                  value={draftJson}
                  onChange={(event) => setDraftJson(event.target.value)}
                  rows={20}
                  spellCheck={false}
                  className="mt-2 w-full rounded-md border border-amber-200 bg-white p-3 font-mono text-xs leading-5 text-slate-800 outline-none focus:border-amber-500"
                />
                <label className="mt-4 block text-sm font-medium text-slate-700" htmlFor="agent-review-note">
                  复核备注
                </label>
                <input
                  id="agent-review-note"
                  value={reviewNote}
                  onChange={(event) => setReviewNote(event.target.value)}
                  className="mt-2 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-sm outline-none focus:border-amber-500"
                  placeholder="可选：记录修改原因或驳回原因"
                />
                <div className="mt-4 flex flex-wrap gap-3">
                  <ReviewButton disabled={submitting || !canEdit} onClick={() => submitReview("approve")}>
                    通过
                  </ReviewButton>
                  <ReviewButton disabled={submitting || !canEdit} onClick={() => submitReview("edit_and_approve")}>
                    修改后通过
                  </ReviewButton>
                  <button
                    type="button"
                    disabled={submitting || !canEdit}
                    onClick={() => submitReview("reject")}
                    className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                  >
                    驳回
                  </button>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <div className="rounded-md border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
            <Bot className="mx-auto h-9 w-9 text-slate-300" aria-hidden="true" />
            <p className="mt-4 font-medium text-slate-700">还没有 Agent 运行记录</p>
            <p className="mt-1 text-sm text-slate-500">启动后将显示专家协作、质量检查和人工复核过程。</p>
          </div>
        )}
      </div>

      <aside className="grid content-start gap-6">
        <div className="rounded-md border border-slate-200 bg-white p-5">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-slate-500" aria-hidden="true" />
            <h3 className="font-semibold">运行轨迹</h3>
          </div>
          <div className="mt-4 grid gap-3">
            {latestEvents.length ? (
              latestEvents.map((event) => (
                <div key={event.id} className="border-l-2 border-slate-200 pl-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-slate-800">{eventLabel(event.event_type)}</p>
                    <span className="text-[11px] text-slate-400">{formatTime(event.created_at)}</span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {event.message ?? agentLabel(event.agent_name)}
                  </p>
                  {event.metrics.latency_ms ? (
                    <p className="mt-1 text-[11px] text-slate-400">耗时 {String(event.metrics.latency_ms)} ms</p>
                  ) : null}
                </div>
              ))
            ) : (
              <p className="py-8 text-center text-sm text-slate-400">暂无运行事件</p>
            )}
          </div>
        </div>

        <div className="rounded-md border border-slate-200 bg-white p-5">
          <h3 className="font-semibold">最近运行</h3>
          <div className="mt-4 grid gap-2">
            {runs.slice(0, 5).map((run) => (
              <div key={run.id} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2.5">
                <div>
                  <p className="text-sm font-medium">Run #{run.id}</p>
                  <p className="mt-0.5 text-xs text-slate-400">{formatTime(run.created_at)}</p>
                </div>
                <RunStatusBadge status={run.status} compact />
              </div>
            ))}
            {!runs.length ? <p className="py-6 text-center text-sm text-slate-400">暂无记录</p> : null}
          </div>
        </div>
      </aside>
    </section>
  );
}

/** 渲染质量审核面板，展示质量得分与规则检查问题。 */
function QualityPanel({ run }: { run: AgentRun }) {
  const report = run.quality_report;
  if (typeof report.score !== "number") return null;
  return (
    <div className="rounded-md border border-slate-200 bg-white p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-emerald-700" aria-hidden="true" />
          <h3 className="text-lg font-semibold">质量审核</h3>
        </div>
        <span className={`text-lg font-semibold ${report.passed ? "text-emerald-700" : "text-amber-700"}`}>
          {report.score} 分
        </span>
      </div>
      <div className="mt-4 grid gap-2">
        {(report.issues ?? []).length ? (
          report.issues?.map((issue) => (
            <div key={`${issue.code}-${issue.field}`} className="flex items-start gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm">
              {issue.severity === "error" ? (
                <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" aria-hidden="true" />
              ) : (
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
              )}
              <span className="text-slate-600">{issue.message}</span>
            </div>
          ))
        ) : (
          <p className="flex items-center gap-2 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> 结构、差异性与合规规则检查通过
          </p>
        )}
      </div>
    </div>
  );
}

/** 渲染运行状态徽标，按状态着色。 */
function RunStatusBadge({ status, compact = false }: { status: AgentRunStatus; compact?: boolean }) {
  const labels: Record<AgentRunStatus, string> = {
    queued: "排队中",
    running: "执行中",
    awaiting_review: "待复核",
    resume_queued: "恢复排队",
    completed: "已完成",
    rejected: "已驳回",
    failed: "失败",
    cancelled: "已取消",
  };
  const color =
    status === "completed"
      ? "bg-emerald-50 text-emerald-700"
      : status === "failed" || status === "rejected"
        ? "bg-rose-50 text-rose-700"
        : status === "awaiting_review"
          ? "bg-amber-50 text-amber-700"
          : "bg-sky-50 text-sky-700";
  return (
    <span className={`rounded-md px-2.5 py-1 ${compact ? "text-[11px]" : "text-xs"} font-semibold ${color}`}>
      {labels[status]}
    </span>
  );
}

/** 渲染专家环节状态图标。 */
function StepStateIcon({ state }: { state: "pending" | "running" | "completed" | "failed" }) {
  if (state === "completed") return <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />;
  if (state === "failed") return <XCircle className="h-4 w-4 text-rose-600" aria-hidden="true" />;
  if (state === "running") return <RefreshCw className="h-4 w-4 animate-spin text-sky-600" aria-hidden="true" />;
  return <Clock3 className="h-4 w-4 text-slate-300" aria-hidden="true" />;
}

/** 依据运行事件推导单个专家环节的状态。 */
function specialistState(run: AgentRun, agentName: string) {
  if (run.events.some((event) => event.agent_name === agentName && event.status === "failed")) return "failed" as const;
  if (run.current_agent === agentName && run.status === "running") return "running" as const;
  if (run.events.some((event) => event.agent_name === agentName && event.event_type === "agent_step_completed")) {
    return "completed" as const;
  }
  return "pending" as const;
}

/** 把专家环节状态映射为中文文案。 */
function stepStateLabel(state: "pending" | "running" | "completed" | "failed") {
  return { pending: "等待执行", running: "正在处理", completed: "已完成", failed: "执行失败" }[state];
}

/** 把运行草稿格式化为可编辑 JSON；无草稿时返回空串。 */
function formatDraft(run: AgentRun | null) {
  if (!run?.draft_output?.diagnosis || !run.draft_output.creative_plans) return "";
  return JSON.stringify(run.draft_output, null, 2);
}

/** 读取响应并解析为运行对象；失败时优先按机器可读错误码给出提示。 */
async function readResponse(response: Response): Promise<AgentRun> {
  const payload = (await response.json()) as AgentRun & { detail?: string; code?: string };
  if (!response.ok) {
    const mapped = payload.code ? AGENT_ERROR_MESSAGES[payload.code] : undefined;
    throw new Error(mapped ?? payload.detail ?? `请求失败（${response.status}）`);
  }
  return payload;
}

/** 渲染复核决策按钮。 */
function ReviewButton({ children, disabled, onClick }: { children: ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-md bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

/** 把用量字段安全转换为数字。 */
function numberValue(value: unknown) {
  return typeof value === "number" ? value : 0;
}

/** 把专家标识映射为中文标签。 */
function agentLabel(agentName: string | null) {
  return specialistSteps.find((step) => step.key === agentName)?.label ?? agentName ?? "工作流";
}

/** 把运行事件类型映射为中文标签。 */
function eventLabel(eventType: string) {
  const labels: Record<string, string> = {
    queued: "已进入队列",
    workflow_started: "工作流启动",
    workflow_resumed: "工作流恢复",
    agent_step_started: "专家开始处理",
    agent_step_completed: "专家处理完成",
    agent_step_failed: "专家处理失败",
    revision_requested: "质量返修",
    human_review_requested: "等待人工复核",
    resume_queued: "复核已提交",
    human_review_received: "收到人工决定",
    approval_requested: "等待人工审批",
    approval_accepted: "审批已通过",
    approval_rejected: "审批已驳回",
  };
  return labels[eventType] ?? eventType;
}

/** 格式化时间，统一展示口径。 */
function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(
    new Date(value),
  );
}
