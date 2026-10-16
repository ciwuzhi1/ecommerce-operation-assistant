import {
  Activity,
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  DatabaseZap,
  Home,
  Layers3,
  Play,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AgentTaskAutoRefresh } from "@/components/agent-task-auto-refresh";
import {
  AgentApiError,
  getAgentApprovals,
  getAgentCatalog,
  getAgentMemories,
  getAgentTasks,
  getCurrentUser,
  getWorkspaces,
  getWorkspaceProducts,
  getWorkspaceStores,
} from "@/lib/api";
import { getActiveWorkspaceId, getAuthToken } from "@/lib/session";
import type { AgentRiskLevel, AgentTaskStatus } from "@/types";

type AgentCenterProps = {
  searchParams?: Promise<{ workspace?: string; result?: string; section?: string }>;
};

const statusLabels: Record<AgentTaskStatus, string> = {
  queued: "排队中",
  running: "执行中",
  awaiting_approval: "待审批",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const statusTones: Record<AgentTaskStatus, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-cyan-100 text-cyan-800",
  awaiting_approval: "bg-amber-100 text-amber-800",
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  cancelled: "bg-slate-100 text-slate-500",
};

const riskTones: Record<AgentRiskLevel, string> = {
  R0: "bg-sky-50 text-sky-700",
  R1: "bg-emerald-50 text-emerald-700",
  R2: "bg-amber-50 text-amber-700",
  R3: "bg-rose-50 text-rose-700",
};

/** 渲染 AgentCenter 组件，集中展示Agent中心所需的数据、状态和操作入口。 */
export default async function AgentCenter({ searchParams }: AgentCenterProps) {
  const token = await getAuthToken();
  if (!token) {
    redirect("/login");
  }
  const query = searchParams ? await searchParams : {};
  const activeWorkspaceId = await getActiveWorkspaceId();
  let workspaces: Awaited<ReturnType<typeof getWorkspaces>>;
  let currentUser: Awaited<ReturnType<typeof getCurrentUser>>;
  try {
    [workspaces, currentUser] = await Promise.all([getWorkspaces(), getCurrentUser(token)]);
  } catch (error) {
    if (error instanceof AgentApiError && error.status === 401) redirect("/login?expired=1");
    return <AgentServiceError />;
  }
  if (!currentUser) redirect("/login?expired=1");
  const workspace = selectWorkspace(
    workspaces,
    query.workspace ?? activeWorkspaceId?.toString(),
  );
  if (!workspace) {
    return <EmptyWorkspace />;
  }
  const workspaceId = workspace.workspace.id;
  let resources;
  try {
    resources = await Promise.all([
      getAgentCatalog(workspaceId),
      getAgentTasks(workspaceId),
      getAgentApprovals(workspaceId),
      getAgentMemories(workspaceId),
      getWorkspaceProducts(workspaceId),
      getWorkspaceStores(workspaceId),
    ]);
  } catch (error) {
    if (error instanceof AgentApiError && error.status === 401) redirect("/login?expired=1");
    return <AgentServiceError />;
  }
  const [catalog, tasks, approvals, memories, products, stores] = resources;
  const canEdit = workspace.membership.role !== "viewer";
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const activeCount = tasks.filter((task) => ["queued", "running"].includes(task.status)).length;

  return (
    <main className="min-h-screen bg-[#f6f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <AgentTaskAutoRefresh active={activeCount > 0} />
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-cyan-700">
              <Bot className="h-4 w-4" aria-hidden="true" />
              Ecommerce Operations Agent
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">统一运营 Agent 中心</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              由一个协调 Agent 选择受控工作流，八个专业 Agent 在 Harness 约束下协作；业务结果仍回到可编辑工作台。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {workspaces.length > 1 ? (
              <form action="/agent/workspaces/select" method="post">
                <select
                  name="workspace_id"
                  defaultValue={workspaceId}
                  className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
                  aria-label="切换 Workspace"
                >
                  {workspaces.map((item) => (
                    <option key={item.workspace.id} value={item.workspace.id}>
                      {item.workspace.name}
                    </option>
                  ))}
                </select>
                <button className="ml-2 h-9 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium hover:bg-slate-50">
                  切换
                </button>
              </form>
            ) : null}
            <Link href="/" className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
              <Home className="h-4 w-4" aria-hidden="true" />
              业务工作台
            </Link>
            <span className="inline-flex h-9 items-center rounded-md bg-slate-950 px-3 text-sm font-medium text-white">
              {currentUser?.display_name ?? "当前用户"} · {workspace.workspace.name}
            </span>
          </div>
        </header>

        {query.result ? <ResultBanner result={query.result} /> : null}

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric icon={Layers3} label="版本化工作流" value={catalog?.workflows.length ?? 0} />
          <Metric icon={Activity} label="进行中任务" value={activeCount} />
          <Metric icon={CheckCircle2} label="已完成任务" value={completedCount} />
          <Metric icon={ClipboardCheck} label="待处理审批" value={approvals.length} tone="text-amber-700" />
        </section>

        <nav className="flex flex-wrap gap-2 rounded-md border border-slate-200 bg-white p-2 text-sm">
          <a href="#agent-entry" className="rounded-md px-3 py-2 font-medium hover:bg-slate-100">Agent 入口</a>
          <a href="#task-center" className="rounded-md px-3 py-2 font-medium hover:bg-slate-100">任务中心</a>
          <a href="#approval-inbox" className="rounded-md px-3 py-2 font-medium hover:bg-slate-100">审批收件箱</a>
          <a href="#memory" className="rounded-md px-3 py-2 font-medium hover:bg-slate-100">结构化记忆</a>
          <a href="#catalog" className="rounded-md px-3 py-2 font-medium hover:bg-slate-100">Agent 目录</a>
        </nav>

        <section id="agent-entry" className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-md border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">告诉协调 Agent 你的目标</h2>
                <p className="mt-1 text-sm text-slate-500">协调 Agent 只从已注册工作流中路由，不会自由拼装高风险动作。</p>
              </div>
              <ShieldCheck className="h-6 w-6 text-cyan-700" aria-hidden="true" />
            </div>
            <form action="/agent/tasks/create" method="post" className="mt-5 space-y-4">
              <input type="hidden" name="workspace_id" value={workspaceId} />
              <textarea
                name="intent"
                required
                disabled={!canEdit}
                placeholder="例如：检查这款商品近期的库存和经营风险，并给出下一步建议"
                className="min-h-28 w-full rounded-md border border-slate-300 bg-white px-3 py-3 text-sm outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-100 disabled:bg-slate-100"
              />
              <ContextSelectors products={products} stores={stores} disabled={!canEdit} />
              <button type="submit" disabled={!canEdit} className="inline-flex h-10 items-center gap-2 rounded-md bg-cyan-700 px-4 text-sm font-medium text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:bg-slate-300">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
                创建受控任务
              </button>
            </form>
          </div>

          <div className="rounded-md border border-slate-200 bg-slate-950 p-5 text-white">
            <div className="flex items-center gap-2 text-sm font-medium text-cyan-300">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Harness 边界
            </div>
            <h2 className="mt-3 text-xl font-semibold">不是把多个 Prompt 串在一起</h2>
            <div className="mt-5 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
              {[
                ["身份与租户", "Workspace 强隔离"],
                ["工具策略", "Agent allowlist + 风险分级"],
                ["可靠执行", "Celery + Outbox + 幂等"],
                ["状态恢复", "PostgreSQL Checkpoint"],
                ["人工协作", "R2/R3 数据库审批"],
                ["质量闭环", "事件、评测和版本追踪"],
              ].map(([title, detail]) => (
                <div key={title} className="rounded-md border border-slate-700 bg-slate-900 p-3">
                  <p className="font-medium text-white">{title}</p>
                  <p className="mt-1 text-xs text-slate-400">{detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">任务模板</h2>
              <p className="mt-1 text-sm text-slate-500">每个模板对应一个可版本化、可评测、可回退的 LangGraph 工作流。</p>
            </div>
            <span className="text-xs text-slate-500">{catalog?.workflows.length ?? 0} 个已启用</span>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {catalog?.workflows.map((workflow) => (
              <form key={workflow.key} action="/agent/tasks/create" method="post" className="flex flex-col rounded-md border border-slate-200 p-4 hover:border-cyan-300">
                <input type="hidden" name="workspace_id" value={workspaceId} />
                <input type="hidden" name="workflow_key" value={workflow.key} />
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-cyan-50 text-cyan-700"><Play className="h-4 w-4" aria-hidden="true" /></div>
                  <span className={`rounded-md px-2 py-1 text-xs font-semibold ${riskTones[workflow.default_risk_level]}`}>{workflow.default_risk_level}</span>
                </div>
                <h3 className="mt-4 font-semibold">{workflow.title}</h3>
                <p className="mt-2 min-h-10 text-sm leading-5 text-slate-500">{workflow.description}</p>
                <div className="mt-3"><ContextSelectors products={products} stores={stores} compact disabled={!canEdit} /></div>
                <button type="submit" disabled={!canEdit} className="mt-4 inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-200 px-3 text-sm font-medium hover:bg-slate-50 disabled:text-slate-400">
                  启动工作流 <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </form>
            ))}
          </div>
        </section>

        <section id="task-center" className="rounded-md border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between gap-4">
            <div><h2 className="text-lg font-semibold">任务中心</h2><p className="mt-1 text-sm text-slate-500">Task 表达业务目标，Run 表达实际执行和重试。</p></div>
            <Clock3 className="h-5 w-5 text-slate-400" aria-hidden="true" />
          </div>
          <div className="mt-5 space-y-3">
            {tasks.length === 0 ? <EmptyText text="还没有 Agent Task。" /> : tasks.map((task) => (
              <details key={task.id} className="rounded-md border border-slate-200 p-4">
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div><p className="font-medium">#{task.id} {task.title}</p><p className="mt-1 text-xs text-slate-500">{task.workflow_key} · v{task.workflow_version} · {formatDate(task.created_at)}</p></div>
                    <div className="flex items-center gap-2"><span className={`rounded-md px-2 py-1 text-xs font-medium ${riskTones[task.risk_level]}`}>{task.risk_level}</span><span className={`rounded-md px-2 py-1 text-xs font-medium ${statusTones[task.status]}`}>{statusLabels[task.status]}</span></div>
                  </div>
                </summary>
                <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4 lg:grid-cols-2">
                  <JsonPanel title="上下文" value={task.context_scope} />
                  <JsonPanel title="结果摘要" value={task.result_summary} />
                </div>
                {task.error ? <p className="mt-3 text-sm text-rose-700">{task.error}</p> : null}
                {["queued", "running", "awaiting_approval"].includes(task.status) && canEdit ? (
                  <form action={`/agent/tasks/${task.id}/cancel`} method="post" className="mt-3"><input type="hidden" name="workspace_id" value={workspaceId} /><button className="inline-flex h-8 items-center gap-2 rounded-md border border-rose-200 px-3 text-xs font-medium text-rose-700 hover:bg-rose-50"><XCircle className="h-3.5 w-3.5" aria-hidden="true" />取消任务</button></form>
                ) : null}
              </details>
            ))}
          </div>
        </section>

        <section id="approval-inbox" className="rounded-md border border-amber-200 bg-amber-50/40 p-5">
          <div className="flex items-center gap-3"><ClipboardCheck className="h-5 w-5 text-amber-700" aria-hidden="true" /><div><h2 className="text-lg font-semibold">审批收件箱</h2><p className="mt-1 text-sm text-slate-600">R2/R3 副作用必须由策略层和数据库审批共同放行。</p></div></div>
          <div className="mt-5 space-y-3">
            {approvals.length === 0 ? <EmptyText text="当前没有待审批动作。" /> : approvals.map((approval) => (
              <div key={approval.id} className="rounded-md border border-amber-200 bg-white p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">任务 #{approval.task_id} · {approval.action_key}</p><p className="mt-1 text-xs text-slate-500">Run #{approval.run_id} · {formatDate(approval.created_at)}</p></div><span className={`w-fit rounded-md px-2 py-1 text-xs font-semibold ${riskTones[approval.risk_level]}`}>{approval.risk_level}</span></div>
                <div className="mt-3"><JsonPanel title="审批内容" value={approval.request_payload} /></div>
                {canEdit ? <div className="mt-4 flex flex-col gap-2"><ApprovalForm approvalId={approval.id} workspaceId={workspaceId} decision="approve" draftOutput={approval.request_payload.draft_output} /><ApprovalForm approvalId={approval.id} workspaceId={workspaceId} decision="reject" /></div> : null}
              </div>
            ))}
          </div>
        </section>

        <section id="memory" className="grid gap-6 xl:grid-cols-[360px_1fr]">
          <div className="rounded-md border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-2"><Brain className="h-5 w-5 text-violet-700" aria-hidden="true" /><h2 className="text-lg font-semibold">确认一条长期记忆</h2></div>
            <p className="mt-2 text-sm text-slate-500">只保存用户明确确认的结构化事实，不自动吸收全部聊天。</p>
            <form action="/agent/memories/create" method="post" className="mt-4 space-y-3">
              <input type="hidden" name="workspace_id" value={workspaceId} />
              <select name="scope_type" className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"><option value="workspace">工作区</option><option value="store">店铺</option><option value="product">商品</option><option value="user">用户偏好</option></select>
              <input name="scope_id" placeholder="范围 ID（工作区可留空）" className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" />
              <input name="memory_key" required placeholder="键，例如 brand_tone" className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" />
              <textarea name="memory_value" required placeholder="已确认的事实或偏好" className="min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              <button disabled={!canEdit} className="inline-flex h-9 items-center gap-2 rounded-md bg-violet-700 px-3 text-sm font-medium text-white disabled:bg-slate-300"><DatabaseZap className="h-4 w-4" aria-hidden="true" />保存记忆</button>
            </form>
          </div>
          <div className="rounded-md border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold">有效记忆</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {memories.length === 0 ? <EmptyText text="暂无已确认记忆。" /> : memories.map((memory) => <div key={memory.id} className="rounded-md border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><p className="font-medium">{memory.memory_key}</p><span className="text-xs text-slate-500">{memory.scope_type}:{memory.scope_id ?? workspaceId}</span></div><pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-600">{JSON.stringify(memory.content, null, 2)}</pre></div>)}
            </div>
          </div>
        </section>

        <section id="catalog" className="rounded-md border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold">内部专业 Agent 目录</h2>
          <p className="mt-1 text-sm text-slate-500">用户只与顶层 Agent 交互；专业 Agent 的版本和工具白名单可审计。</p>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {catalog?.agents.map((agent) => <div key={agent.key} className="rounded-md border border-slate-200 p-4"><p className="font-medium">{humanizeAgent(agent.key)}</p><p className="mt-1 text-xs text-cyan-700">v{agent.version}</p><p className="mt-3 text-sm leading-5 text-slate-500">{agent.description}</p><p className="mt-3 text-xs text-slate-400">{agent.tools.length} 个允许工具</p></div>)}
          </div>
        </section>
      </div>
    </main>
  );
}

/** 渲染 ContextSelectors 组件，集中展示上下文选择器所需的数据、状态和操作入口。 */
function ContextSelectors({ products, stores, compact = false, disabled = false }: { products: Array<{ id: number; name: string }>; stores: Array<{ id: number; name: string }>; compact?: boolean; disabled?: boolean }) {
  return <div className={`grid gap-3 ${compact ? "" : "sm:grid-cols-2"}`}><select name="product_id" disabled={disabled} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"><option value="">选择商品上下文</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select><select name="store_id" disabled={disabled} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm disabled:bg-slate-100"><option value="">选择店铺上下文</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></div>;
}

/** 渲染 ApprovalForm 组件，集中展示审批表单所需的数据、状态和操作入口。 */
function ApprovalForm({ approvalId, workspaceId, decision, draftOutput }: { approvalId: number; workspaceId: number; decision: "approve" | "reject"; draftOutput?: unknown }) {
  const approve = decision === "approve";
  return <form action={`/agent/approvals/${approvalId}/decision`} method="post" className="space-y-2"><input type="hidden" name="workspace_id" value={workspaceId} /><input type="hidden" name="decision" value={decision} />{approve ? <textarea name="edited_output" defaultValue={JSON.stringify(draftOutput ?? {}, null, 2)} className="min-h-40 w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-xs" aria-label="编辑后批准的结构化输出" /> : null}<button className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium ${approve ? "bg-emerald-700 text-white hover:bg-emerald-800" : "border border-rose-200 bg-white text-rose-700 hover:bg-rose-50"}`}>{approve ? <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> : <XCircle className="h-4 w-4" aria-hidden="true" />}{approve ? "编辑后批准并恢复" : "拒绝"}</button></form>;
}

/** 渲染 Metric 组件，集中展示指标所需的数据、状态和操作入口。 */
function Metric({ icon: Icon, label, value, tone = "text-cyan-700" }: { icon: typeof Activity; label: string; value: number; tone?: string }) {
  return <div className="rounded-md border border-slate-200 bg-white p-4"><div className="flex items-center justify-between"><p className="text-sm text-slate-500">{label}</p><Icon className={`h-4 w-4 ${tone}`} aria-hidden="true" /></div><p className="mt-2 text-2xl font-semibold">{value}</p></div>;
}

/** 渲染 JsonPanel 组件，集中展示json面板所需的数据、状态和操作入口。 */
function JsonPanel({ title, value }: { title: string; value: Record<string, unknown> }) {
  return <div className="rounded-md bg-slate-50 p-3"><p className="text-xs font-semibold text-slate-500">{title}</p><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-700">{Object.keys(value).length ? JSON.stringify(value, null, 2) : "暂无"}</pre></div>;
}

/** 渲染 EmptyText 组件，集中展示空状态文本所需的数据、状态和操作入口。 */
function EmptyText({ text }: { text: string }) { return <div className="rounded-md border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">{text}</div>; }

/** 渲染 EmptyWorkspace 组件，集中展示空状态Workspace所需的数据、状态和操作入口。 */
function EmptyWorkspace() { return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><div className="max-w-lg rounded-md border border-slate-200 bg-white p-8 text-center"><Bot className="mx-auto h-8 w-8 text-slate-400" /><h1 className="mt-4 text-xl font-semibold">暂无可用 Workspace</h1><p className="mt-2 text-sm text-slate-500">请先运行数据库迁移并为当前用户创建 WorkspaceMembership。</p></div></main>; }

/** 渲染 AgentServiceError 组件，集中展示Agent服务错误所需的数据、状态和操作入口。 */
function AgentServiceError() { return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><div className="max-w-lg rounded-md border border-rose-200 bg-white p-8 text-center"><XCircle className="mx-auto h-8 w-8 text-rose-600" /><h1 className="mt-4 text-xl font-semibold">Agent 服务暂不可用</h1><p className="mt-2 text-sm text-slate-500">请求未被伪装为空数据，请检查 API、权限或基础设施状态后重试。</p></div></main>; }

/** 渲染 ResultBanner 组件，集中展示结果提示横幅所需的数据、状态和操作入口。 */
function ResultBanner({ result }: { result: string }) {
  const failed = result === "failed";
  return <div className={`rounded-md border px-4 py-3 text-sm ${failed ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{failed ? "操作失败，请检查输入和权限。" : "操作已提交，任务状态会持续更新。"}</div>;
}

/** 处理选择Workspace交互，维护必要状态并把副作用交给受控路由或后端 API。 */
function selectWorkspace(workspaces: Awaited<ReturnType<typeof getWorkspaces>>, requested?: string) {
  const requestedId = Number(requested);
  return workspaces.find((item) => item.workspace.id === requestedId) ?? workspaces[0] ?? null;
}

/** 格式化日期，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatDate(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }

/** 转换显示名Agent，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function humanizeAgent(key: string) { return key.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" "); }
