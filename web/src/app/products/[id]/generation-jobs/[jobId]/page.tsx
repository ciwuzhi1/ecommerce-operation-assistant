import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getProduct } from "@/lib/api";
import type { GenerationJob } from "@/types";

type GenerationJobDetailPageProps = {
  params: Promise<{ id: string; jobId: string }>;
};

/** 渲染商品/生成任务jobs页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default async function GenerationJobDetailPage({ params }: GenerationJobDetailPageProps) {
  const { id, jobId } = await params;
  const product = await getProduct(id);

  if (!product) {
    notFound();
  }

  const job = product.generation_jobs.find((item) => item.id === Number(jobId));
  if (!job) {
    notFound();
  }

  const creativePlan = product.creative_plans.find((plan) => plan.id === job.creative_plan_id);
  const resultUrl = jobResultUrl(job);

  return (
    <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5">
          <Link
            href={`/products/${product.id}?tab=jobs`}
            className="inline-flex w-fit items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            返回任务中心
          </Link>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-sm font-medium text-emerald-700">{product.name}</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-normal">生成任务 #{job.id}</h1>
            </div>
            <JobStatusBadge job={job} />
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <DetailMetric label="任务类型" value={job.kind === "video_asset" ? "视频生成" : "图片生成"} />
          <DetailMetric label="关联方案" value={creativePlan?.title ?? "未知方案"} />
          <DetailMetric label="开始时间" value={job.started_at ?? "未开始"} />
          <DetailMetric label="完成时间" value={job.finished_at ?? "未完成"} />
        </section>

        {job.error ? (
          <section
            className={
              job.status === "cancelled"
                ? "rounded-md border border-slate-200 bg-white p-4"
                : "rounded-md border border-rose-200 bg-rose-50 p-4"
            }
          >
            <h2
              className={
                job.status === "cancelled"
                  ? "text-sm font-semibold text-slate-950"
                  : "text-sm font-semibold text-rose-800"
              }
            >
              {job.status === "cancelled" ? "取消原因" : "失败原因"}
            </h2>
            <p
              className={
                job.status === "cancelled"
                  ? "mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600"
                  : "mt-2 whitespace-pre-wrap text-sm leading-6 text-rose-700"
              }
            >
              {job.error}
            </p>
            {job.status === "failed" ? (
              // 只有失败任务暴露重试入口；取消任务代表人工停止，不应该被误操作重新排队。
              <form action={`/products/${product.id}/generation-jobs/${job.id}/retry`} method="post" className="mt-4">
                <input type="hidden" name="tab" value="jobs" />
                <button
                  type="submit"
                  className="inline-flex h-9 items-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
                >
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  重试任务
                </button>
              </form>
            ) : null}
          </section>
        ) : null}

        {job.status === "pending" || job.status === "running" ? (
          <section className="rounded-md border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-950">任务控制</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">取消后任务会停止排队或释放运行锁，不会继续生成素材。</p>
            <form action={`/products/${product.id}/generation-jobs/${job.id}/cancel`} method="post" className="mt-4">
              <input type="hidden" name="tab" value="jobs" />
              <button
                type="submit"
                className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                取消任务
              </button>
            </form>
          </section>
        ) : null}

        {resultUrl ? (
          <section className="rounded-md border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">生成结果</h2>
                <p className="mt-1 break-all text-xs text-slate-500">{resultUrl}</p>
              </div>
              <a
                href={absoluteMediaUrl(resultUrl)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-9 shrink-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                打开结果
              </a>
            </div>
            {job.kind === "video_asset" ? (
              <video
                src={absoluteMediaUrl(resultUrl)}
                controls
                className="mt-4 aspect-video w-full rounded-md bg-black object-contain"
              />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={absoluteMediaUrl(resultUrl)}
                alt="生成结果"
                className="mt-4 max-h-[560px] w-full rounded-md object-contain"
              />
            )}
          </section>
        ) : null}

        <JobEventTimeline job={job} />

        <section className="grid gap-4 lg:grid-cols-2">
          <JsonPanel title="任务结果 JSON" value={job.result} />
          <JsonPanel title="关联方案 JSON" value={creativePlan?.content ?? {}} />
        </section>
      </div>
    </main>
  );
}

/** 渲染 JobEventTimeline 组件，集中展示任务事件时间线所需的数据、状态和操作入口。 */
function JobEventTimeline({ job }: { job: GenerationJob }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">任务事件</h2>
          <p className="mt-1 text-xs text-slate-500">记录入队、开始、失败、重试和完成等生命周期节点</p>
        </div>
        <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{job.events.length} 条</span>
      </div>

      {job.events.length > 0 ? (
        <div className="mt-4 grid gap-2">
          {job.events.map((event) => (
            <div key={event.id} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{generationJobEventLabel(event.event_type)}</p>
                  <p className="mt-1 text-xs text-slate-500">{event.created_at}</p>
                </div>
                <span className="w-fit rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                  {event.status ? generationJobStatusLabel(event.status) : "无状态"}
                </span>
              </div>
              {event.message ? <p className="mt-2 text-sm leading-6 text-slate-700">{event.message}</p> : null}
              {event.worker_id ? <p className="mt-1 text-xs text-slate-500">worker: {event.worker_id}</p> : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          暂无任务事件。新任务会在入队、执行和重试时写入事件。
        </div>
      )}
    </section>
  );
}

/** 渲染 DetailMetric 组件，集中展示详情指标所需的数据、状态和操作入口。 */
function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

/** 把生成任务任务事件状态映射为中文显示文本，保持页面口径一致。 */
function generationJobEventLabel(type: string): string {
  const labels: Record<string, string> = {
    failed: "执行失败",
    queued: "任务入队",
    retry_requested: "请求重试",
    retry_scheduled: "安排重试",
    started: "开始执行",
    succeeded: "执行成功",
    cancelled: "任务取消",
    timeout_checked: "超时检查",
  };
  return labels[type] ?? type;
}

/** 把生成任务任务状态状态映射为中文显示文本，保持页面口径一致。 */
function generationJobStatusLabel(status: GenerationJob["status"]): string {
  const labels: Record<GenerationJob["status"], string> = {
    failed: "失败",
    pending: "排队中",
    running: "生成中",
    succeeded: "已完成",
    cancelled: "已取消",
  };
  return labels[status];
}

/** 渲染 JsonPanel 组件，集中展示json面板所需的数据、状态和操作入口。 */
function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
      <pre className="mt-3 max-h-[420px] overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-100">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

/** 渲染 JobStatusBadge 组件，集中展示任务状态状态徽标所需的数据、状态和操作入口。 */
function JobStatusBadge({ job }: { job: GenerationJob }) {
  const statusLabels: Record<GenerationJob["status"], string> = {
    failed: "失败",
    pending: "排队中",
    running: "生成中",
    succeeded: "已完成",
    cancelled: "已取消",
  };
  const tone: Record<GenerationJob["status"], string> = {
    failed: "bg-rose-50 text-rose-700",
    pending: "bg-slate-100 text-slate-600",
    running: "bg-amber-50 text-amber-700",
    succeeded: "bg-emerald-50 text-emerald-700",
    cancelled: "bg-slate-100 text-slate-500",
  };

  return (
    <span className={`inline-flex h-8 w-fit items-center rounded-md px-2.5 text-xs font-medium ${tone[job.status]}`}>
      {statusLabels[job.status]}
    </span>
  );
}

/** 任务结果URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function jobResultUrl(job: GenerationJob): string | null {
  const value = job.result.url;
  // 生成结果可能来自不同 worker 或历史数据，详情页只认可明确的字符串 URL。
  return typeof value === "string" && value ? value : null;
}

/** 绝对地址媒体URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function absoluteMediaUrl(url: string): string {
  // worker 可返回完整 URL 或后端媒体相对路径；展示层统一补齐 API 域名，不改写入库结果。
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}${url}`;
}
