import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  ExternalLink,
  ImageIcon,
  LinkIcon,
  Megaphone,
  RefreshCw,
  Video,
} from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CompetitorCreateForm } from "@/components/competitor-create-form";
import { CompetitorUrlImportForm } from "@/components/competitor-url-import-form";
import { AgentRunPanel } from "@/components/agent-run-panel";
import { CreativePlanStatusActions } from "@/components/creative-plan-status-actions";
import { DiagnosisEditForm } from "@/components/diagnosis-edit-form";
import { GenerationJobAutoRefresh } from "@/components/generation-job-auto-refresh";
import { MainImagePlanEditForm } from "@/components/main-image-plan-edit-form";
import { PerformanceImportForm } from "@/components/performance-import-form";
import { PerformanceRecordForm } from "@/components/performance-record-form";
import { PlatformMappingPanel } from "@/components/platform-mapping-panel";
import { ProductEditForm } from "@/components/product-edit-form";
import { ReviewReportEditForm } from "@/components/review-report-edit-form";
import { SkuCreateForm, SkuInventoryPanel } from "@/components/sku-inventory-forms";
import { VideoScriptEditForm } from "@/components/video-script-edit-form";
import { getAdExperimentDashboard, getAgentRuns, getCurrentUser, getProduct, getStores } from "@/lib/api";
import { getAuthToken } from "@/lib/session";
import type {
  AdExperiment,
  AdExperimentDashboard,
  Competitor,
  CompetitorMonitor,
  GeneratedAsset,
  GenerationJob,
  PerformanceRecord,
  ProductDetail,
  PromotionLink,
} from "@/types";

const platformLabels: Record<string, string> = {
  douyin: "抖音",
  taobao: "淘宝",
  tmall: "天猫",
  pinduoduo: "拼多多",
  jd: "京东",
  tiktok_shop: "TikTok",
  amazon: "Amazon",
  other: "其他",
};

const productTabs = [
  { key: "overview", label: "商品&竞品" },
  { key: "agent", label: "运营 Agent" },
  { key: "diagnosis", label: "诊断" },
  { key: "main-images", label: "主图" },
  { key: "video", label: "视频" },
  { key: "assets", label: "素材库" },
  { key: "links", label: "链接" },
  { key: "ads", label: "投放" },
  { key: "jobs", label: "任务" },
  { key: "review", label: "复盘" },
] as const;

type ProductTabKey = (typeof productTabs)[number]["key"];

type ProductDetailPageProps = {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{
    assets?: string;
    experiment?: string;
    competitor?: string;
    competitor_import?: string;
    monitor?: string;
    count?: string;
    import?: string;
    inventory?: string;
    links?: string;
    mapping?: string;
    performance?: string;
    sku?: string;
    tab?: string;
  }>;
};

/** 渲染商品页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default async function ProductDetailPage({ params, searchParams }: ProductDetailPageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  // 商品详情页是单品运营闭环主入口，首屏并行读取详情、实验看板、店铺和登录态。
  const [product, adExperimentDashboard, agentRuns, stores, token] = await Promise.all([
    getProduct(id),
    getAdExperimentDashboard(id),
    getAgentRuns(id),
    getStores(),
    getAuthToken(),
  ]);

  if (!product) {
    notFound();
  }

  const priceSpread =
    product.competitors.length > 0
      ? product.competitors
          .map((competitor) => Number(competitor.price))
          .filter((price) => Number.isFinite(price) && price > 0)
      : [];
  const latestDiagnosis = product.diagnoses[0];
  const mainImagePlans = product.creative_plans
    .filter((plan) => plan.type === "main_image")
    .sort((a, b) => b.id - a.id)
    .slice(0, 4);
  const videoScripts = product.creative_plans
    .filter((plan) => plan.type === "video_script")
    .sort((a, b) => b.id - a.id)
    .slice(0, 3);
  const performanceSummary = summarizePerformance(product.performance_records);
  const performanceRecords = [...product.performance_records].sort((a, b) => b.id - a.id).slice(0, 5);
  const latestReviewReport = [...product.review_reports].sort((a, b) => b.id - a.id)[0];
  const latestAdRecommendation = [...product.ad_recommendations].sort((a, b) => b.id - a.id)[0];
  const adExperiments = [...product.ad_experiments].sort((a, b) => b.id - a.id).slice(0, 4);
  const activeTab = resolveProductTab(resolvedSearchParams?.tab);
  const workflowSteps = buildProductWorkflowSteps(product);
  const competitorInsights = buildCompetitorInsights(product.competitors, product.price);
  const assetLibrary = collectAssetLibrary(product.generated_assets, product.creative_plans);
  const hasActiveGenerationJobs = product.generation_jobs.some((job) =>
    ["pending", "running"].includes(job.status),
  );
  const currentUser = token ? await getCurrentUser(token) : null;
  // canEdit 只控制前端写操作入口展示；真实鉴权仍由后端 API 权限依赖兜底。
  const canEdit = Boolean(currentUser?.permissions.can_edit);

  return (
    <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <GenerationJobAutoRefresh active={hasActiveGenerationJobs} />
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5">
          <Link href="/" className="inline-flex w-fit items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            返回商品池
          </Link>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-medium text-emerald-700">
                {platformLabels[product.platform]} · {product.category ?? "未分类"}
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
                {product.name}
              </h1>
              <div className="mt-3 flex flex-wrap gap-2">
                {product.selling_points.length === 0 ? (
                  <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
                    暂无卖点
                  </span>
                ) : (
                  product.selling_points.map((point) => (
                    <span key={point} className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs text-emerald-700">
                      {point}
                    </span>
                  ))
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 sm:w-[480px]">
              <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
                <p className="text-xs text-slate-500">售价</p>
                <p className="mt-1 text-xl font-semibold">{product.price ? `¥${product.price}` : "-"}</p>
              </div>
              <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
                <p className="text-xs text-slate-500">竞品</p>
                <p className="mt-1 text-xl font-semibold">{product.competitors.length}</p>
              </div>
              <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
                <p className="text-xs text-slate-500">素材</p>
                <p className="mt-1 text-xl font-semibold">{product.creative_plans.length}</p>
              </div>
            </div>
          </div>
        </header>

        <ProductTabNav productId={product.id} activeTab={activeTab} />
        <ProductWorkflowPanel steps={workflowSteps} />
        {!canEdit ? (
          <section className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            当前账号为只读权限，生成、保存、取消、重试和导入等写操作按钮已隐藏。
          </section>
        ) : null}
        <GenerationJobSummary
          activeTab={activeTab}
          canEdit={canEdit}
          jobs={product.generation_jobs.slice(0, 5)}
          productId={product.id}
        />

        {activeTab === "agent" ? (
          <AgentRunPanel productId={product.id} initialRuns={agentRuns} canEdit={canEdit} />
        ) : null}

        {activeTab === "overview" ? (
        <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <div className="grid gap-6">
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <ProductEditForm product={product} canEdit={canEdit} />
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <SkuCreateForm productId={product.id} canEdit={canEdit} />
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <CompetitorUrlImportForm productId={product.id} canEdit={canEdit} />
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <CompetitorCreateForm productId={product.id} canEdit={canEdit} />
            </div>
          </div>

          <div className="grid gap-6">
            <SkuInventoryPanel
              productId={product.id}
              skus={product.skus ?? []}
              skuStatus={resolvedSearchParams?.sku}
              inventoryStatus={resolvedSearchParams?.inventory}
              canEdit={canEdit}
            />
            <PlatformMappingPanel
              productId={product.id}
              productPlatform={product.platform}
              productStoreId={product.store_id}
              stores={stores}
              skus={product.skus ?? []}
              mappings={product.platform_mappings ?? []}
              mappingStatus={resolvedSearchParams?.mapping}
              canEdit={canEdit}
            />
            <div className="rounded-md border border-slate-200 bg-white p-6">
            <CompetitorImportAlert
              competitorStatus={resolvedSearchParams?.competitor}
              importStatus={resolvedSearchParams?.competitor_import}
            />
            <CompetitorInsightsPanel insights={competitorInsights} />
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">竞品列表</h2>
                <p className="mt-1 text-sm text-slate-500">先把市场参照物摆上桌面，后续分析才有抓手</p>
              </div>
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {priceSpread.length > 0
                  ? `价格样本 ${Math.min(...priceSpread)}-${Math.max(...priceSpread)}`
                  : "待补充价格"}
              </span>
            </div>

            <div className="mt-5 overflow-hidden rounded-md border border-slate-200">
              <div className="grid grid-cols-[1.2fr_0.7fr_0.6fr_1.1fr_1fr] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500">
                <span>竞品</span>
                <span>平台</span>
                <span>售价</span>
                <span>标题</span>
                <span>卖点</span>
              </div>

              {product.competitors.length === 0 ? (
                <div className="px-4 py-12 text-center text-sm text-slate-500">
                  还没有竞品。建议先录入 3 个同价位或同类目爆款。
                </div>
              ) : (
                <div className="divide-y divide-slate-200">
                  {product.competitors.map((competitor) => (
                    <div
                      key={competitor.id}
                      className="grid min-h-16 grid-cols-[1.2fr_0.7fr_0.6fr_1.1fr_1fr] items-center px-4 py-3 text-sm"
                    >
                      <div>
                        <p className="font-medium text-slate-950">{competitor.name}</p>
                        {competitor.url ? (
                          <a
                            href={competitor.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-flex items-center gap-1 text-xs text-sky-700 hover:text-sky-900"
                          >
                            <LinkIcon className="h-3 w-3" aria-hidden="true" />
                            查看链接
                          </a>
                        ) : (
                          <p className="mt-1 text-xs text-slate-400">未填链接</p>
                        )}
                      </div>
                      <span className="text-slate-600">{platformLabels[competitor.platform]}</span>
                      <span className="font-medium text-slate-800">
                        {competitor.price ? `¥${competitor.price}` : "-"}
                      </span>
                      <span className="line-clamp-2 text-slate-600">{competitor.title ?? "-"}</span>
                      <div className="flex flex-wrap gap-1.5">
                        {competitor.selling_points.slice(0, 3).map((point) => (
                          <span key={point} className="rounded-md bg-sky-50 px-2 py-1 text-xs text-sky-700">
                            {point}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <CompetitorMonitorPanel
              competitors={product.competitors}
              monitors={product.competitor_monitors ?? []}
              productId={product.id}
              canEdit={canEdit}
            />
            </div>
          </div>
        </section>
        ) : null}

        {activeTab === "diagnosis" ? (
        <section className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="rounded-md border border-slate-200 bg-white p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">商品诊断</h2>
                <p className="mt-1 text-sm text-slate-500">
                  基于商品信息和竞品样本生成定位、价格带、痛点和动作建议
                </p>
              </div>
              {canEdit ? (
                <form action={`/products/${product.id}/diagnoses/generate`} method="post">
                  <button
                    type="submit"
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    <Brain className="h-4 w-4" aria-hidden="true" />
                    生成诊断
                  </button>
                </form>
              ) : null}
            </div>

            {latestDiagnosis ? (
              <div className="mt-5 grid gap-4">
                <div className="rounded-md border border-emerald-100 bg-emerald-50 p-4">
                  <p className="text-xs font-medium text-emerald-700">定位判断</p>
                  <p className="mt-2 text-sm leading-6 text-slate-800">{latestDiagnosis.positioning}</p>
                </div>

                <div className="rounded-md border border-slate-200 p-4">
                  <p className="text-xs font-medium text-slate-500">价格带判断</p>
                  <p className="mt-2 text-sm leading-6 text-slate-800">{latestDiagnosis.price_band}</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <DiagnosisList title="用户痛点" items={latestDiagnosis.pain_points} />
                  <DiagnosisList title="卖点判断" items={latestDiagnosis.selling_point_analysis} />
                  <DiagnosisList title="风险点" items={latestDiagnosis.risks} />
                  <DiagnosisList title="下一步建议" items={latestDiagnosis.recommendations} accent />
                </div>

                {canEdit ? (
                  <details className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">
                      编辑诊断
                    </summary>
                    <DiagnosisEditForm productId={product.id} diagnosis={latestDiagnosis} />
                  </details>
                ) : null}
              </div>
            ) : (
              <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                还没有诊断报告。建议补充至少 1-3 个竞品后生成第一版诊断。
              </div>
            )}
          </div>

          <div className="grid gap-4">
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-100 text-emerald-700">
              <ImageIcon className="h-4 w-4" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-950">主图方案</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              根据诊断结果生成可交给设计执行的画面方向
            </p>
            {canEdit ? (
              <form action={`/products/${product.id}/creative-plans/main-images/generate`} method="post">
                <button
                  type="submit"
                  className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
                >
                  <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" />
                  生成主图
                </button>
              </form>
            ) : null}
          </div>
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-violet-100 text-violet-700">
              <Video className="h-4 w-4" aria-hidden="true" />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-slate-950">短视频脚本</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              生成开头钩子、镜头分镜、口播和转化引导
            </p>
            {canEdit ? (
              <form action={`/products/${product.id}/creative-plans/video-scripts/generate`} method="post">
                <button
                  type="submit"
                  className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
                >
                  <Video className="h-3.5 w-3.5" aria-hidden="true" />
                  生成脚本
                </button>
              </form>
            ) : null}
          </div>
          <StageCard
            icon={Megaphone}
            title="投放复盘"
            detail="录入曝光、点击、转化、ROI 后判断下一步动作"
          />
          </div>
        </section>
        ) : null}

        {activeTab === "review" ? (
        <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <div className="grid gap-6">
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <PerformanceRecordForm
                productId={product.id}
                creativePlans={product.creative_plans}
                generatedAssets={product.generated_assets}
                promotionLinks={product.promotion_links}
                adExperiments={product.ad_experiments}
                canEdit={canEdit}
              />
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <PerformanceImportForm productId={product.id} canEdit={canEdit} />
            </div>
          </div>

          <div className="rounded-md border border-slate-200 bg-white p-6">
            <PerformanceImportAlert
              count={resolvedSearchParams?.count}
              importStatus={resolvedSearchParams?.import}
              performanceStatus={resolvedSearchParams?.performance}
            />
            <PerformanceSummaryCards summary={performanceSummary} />
            <PerformanceTrendPanel records={product.performance_records} />
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">投放复盘</h2>
                <p className="mt-1 text-sm text-slate-500">
                  录入经营数据后生成周期复盘，判断下一步换图、调价还是调人群
                </p>
              </div>
              {canEdit ? (
                <form action={`/products/${product.id}/review-reports/generate`} method="post">
                <button
                  type="submit"
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  <Megaphone className="h-4 w-4" aria-hidden="true" />
                  生成复盘
                </button>
                </form>
              ) : null}
            </div>

            {latestReviewReport ? (
              <div className="mt-5 grid gap-4">
                <div className="rounded-md border border-amber-100 bg-amber-50 p-4">
                  <p className="text-xs font-medium text-amber-700">
                    {latestReviewReport.period_start} 至 {latestReviewReport.period_end}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate-800">{latestReviewReport.summary}</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <ReviewList title="复盘洞察" items={latestReviewReport.insights} />
                  <ReviewList title="下一步动作" items={latestReviewReport.next_actions} accent />
                </div>

                {canEdit ? (
                  <details className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                  <summary className="cursor-pointer text-sm font-medium text-slate-700">
                    编辑复盘
                  </summary>
                    <ReviewReportEditForm productId={product.id} report={latestReviewReport} />
                  </details>
                ) : null}
              </div>
            ) : (
              <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                暂无复盘报告。先录入一条经营数据，再生成复盘。
              </div>
            )}

            <div className="mt-6 overflow-hidden rounded-md border border-slate-200">
              <div className="grid grid-cols-[1fr_0.9fr_0.8fr_0.8fr_0.55fr_0.55fr_0.55fr_0.55fr] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500">
                <span>周期</span>
                <span>实验</span>
                <span>素材</span>
                <span>链接</span>
                <span>CTR</span>
                <span>转化率</span>
                <span>花费</span>
                <span>ROI</span>
              </div>

              {performanceRecords.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-500">
                  还没有经营数据。录入后这里会展示最近 5 条记录。
                </div>
              ) : (
                <div className="divide-y divide-slate-200">
                  {performanceRecords.map((record) => (
                    <div
                      key={record.id}
                      className="grid min-h-14 grid-cols-[1fr_0.9fr_0.8fr_0.8fr_0.55fr_0.55fr_0.55fr_0.55fr] items-center px-4 py-3 text-sm"
                    >
                      <span className="text-slate-700">
                        {record.period_start} 至 {record.period_end}
                      </span>
                      <span className="line-clamp-1 text-slate-600">
                        {adExperimentTitle(product.ad_experiments, record.ad_experiment_id)}
                      </span>
                      <span className="line-clamp-1 text-slate-600">
                        {creativePlanTitle(product.creative_plans, record.creative_plan_id)}
                      </span>
                      <span className="line-clamp-1 text-slate-600">
                        {promotionLinkTitle(product.promotion_links, record.promotion_link_id)}
                      </span>
                      <span className="font-medium text-slate-800">{formatPercent(record.ctr)}</span>
                      <span className="font-medium text-slate-800">
                        {formatPercent(record.conversion_rate)}
                      </span>
                      <span className="text-slate-700">{formatMoney(record.spend)}</span>
                      <span className="font-semibold text-slate-950">{formatDecimal(record.roi)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
        ) : null}

        {activeTab === "links" ? (
        <section className="grid gap-6 lg:grid-cols-[420px_1fr]">
          <div className="grid gap-6">
            <div className="rounded-md border border-slate-200 bg-white p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-600 text-white">
                  <LinkIcon className="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-slate-950">生成推荐链接</h2>
                  <p className="text-sm text-slate-500">按商品承接页、短视频投放和主图测试生成链接</p>
                </div>
              </div>
              {canEdit ? (
                <form action={`/products/${product.id}/promotion-links/generate`} method="post" className="mt-4">
                <button
                  type="submit"
                  className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  <LinkIcon className="h-4 w-4" aria-hidden="true" />
                  生成链接
                </button>
                </form>
              ) : null}
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-6">
              <PromotionLinkCreateForm productId={product.id} canEdit={canEdit} />
            </div>
          </div>

          <div className="rounded-md border border-slate-200 bg-white p-6">
            <PromotionLinkAlert status={resolvedSearchParams?.links} />
            <PromotionLinkAttributionPanel
              links={product.promotion_links}
              records={product.performance_records}
            />
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">推荐链接库</h2>
                <p className="mt-1 text-sm text-slate-500">
                  管理商品承接、短视频投放、主图测试和私域转发链接
                </p>
              </div>
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {product.promotion_links.length} 个链接
              </span>
            </div>

            {product.promotion_links.length > 0 ? (
              <div className="mt-5 grid gap-3">
                {product.promotion_links.map((link) => (
                  <PromotionLinkCard key={link.id} link={link} />
                ))}
              </div>
            ) : (
              <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                还没有推荐链接。可以先生成一组系统链接，或手动添加平台推广链接。
              </div>
            )}
          </div>
        </section>
        ) : null}

        {activeTab === "ads" ? (
        <section className="rounded-md border border-slate-200 bg-white p-6">
          <AdWorkflowPanel product={product} />
          <AdLinkRecommendationPanel
            links={product.promotion_links}
            records={product.performance_records}
          />
          <AdAssetRecommendationPanel
            assets={product.generated_assets}
            records={product.performance_records}
          />
          <AdExperimentDashboardPanel
            dashboard={adExperimentDashboard}
            assets={product.generated_assets}
            links={product.promotion_links}
          />
          <AdExperimentPanel
            experiments={adExperiments}
            assets={product.generated_assets}
            links={product.promotion_links}
            productId={product.id}
            status={resolvedSearchParams?.experiment}
            canEdit={canEdit}
          />
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">投放建议</h2>
              <p className="mt-1 text-sm text-slate-500">
                基于诊断、素材方向和经营数据，生成下一轮人群、预算、素材测试和风控建议
              </p>
            </div>
            {canEdit ? (
              <form action={`/products/${product.id}/ad-recommendations/generate`} method="post">
              <button
                type="submit"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                <Megaphone className="h-4 w-4" aria-hidden="true" />
                生成投放建议
              </button>
              </form>
            ) : null}
          </div>

          {latestAdRecommendation ? (
            <div className="mt-5 grid gap-4">
              <div className="rounded-md border border-emerald-100 bg-emerald-50 p-4">
                <p className="text-xs font-medium text-emerald-700">
                  {latestAdRecommendation.source === "llm" ? "LLM 生成" : "规则生成"}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-800">{latestAdRecommendation.summary}</p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span
                    className={`${adRecommendationConfirmationTone(latestAdRecommendation.confirmation_status)} rounded-md px-2 py-1 text-xs font-medium`}
                  >
                    {adRecommendationConfirmationLabel(latestAdRecommendation.confirmation_status)}
                  </span>
                  {latestAdRecommendation.confirmed_at ? (
                    <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-500">
                      {formatDateTime(latestAdRecommendation.confirmed_at)}
                    </span>
                  ) : null}
                </div>
                {latestAdRecommendation.confirmation_note ? (
                  <p className="mt-2 text-xs leading-5 text-slate-600">{latestAdRecommendation.confirmation_note}</p>
                ) : null}
              </div>
              <PlanField label="本轮目标" value={contentText(latestAdRecommendation.content, "objective")} highlight />
              <div className="grid gap-4 lg:grid-cols-2">
                <AdObjectList title="人群建议" items={contentObjects(latestAdRecommendation.content, "audience_segments")} />
                <BudgetPlan content={latestAdRecommendation.content} />
                <AdObjectList title="素材测试" items={contentObjects(latestAdRecommendation.content, "creative_tests")} />
                <AdTextList title="出价策略" items={contentList(latestAdRecommendation.content, "bid_strategy")} />
                <AdTextList title="风险控制" items={contentList(latestAdRecommendation.content, "risk_controls")} />
                <AdTextList title="下一步动作" items={contentList(latestAdRecommendation.content, "next_steps")} accent />
              </div>
              {canEdit ? (
                <details className="rounded-md border border-slate-200 bg-white px-4 py-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">人工确认建议</summary>
                <form
                  action={`/products/${product.id}/ad-recommendations/${latestAdRecommendation.id}/confirmation`}
                  method="post"
                  className="mt-3 grid gap-3"
                >
                  <label className="grid gap-1.5">
                    <span className="text-xs font-medium text-slate-500">确认备注</span>
                    <textarea
                      name="confirmation_note"
                      defaultValue={latestAdRecommendation.confirmation_note ?? ""}
                      rows={2}
                      className="resize-y rounded-md border border-slate-200 px-2 py-2 text-sm leading-5 outline-none focus:border-slate-400"
                      placeholder="记录确认人判断、预算边界或暂不执行原因"
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="submit"
                      name="confirmation_status"
                      value="confirmed"
                      className="h-9 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
                    >
                      确认建议
                    </button>
                    <button
                      type="submit"
                      name="confirmation_status"
                      value="rejected"
                      className="h-9 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      暂不采纳
                    </button>
                  </div>
                </form>
                </details>
              ) : null}
            </div>
          ) : (
            <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              还没有投放建议。建议先生成诊断、主图/视频方案，并录入至少一条经营数据。
            </div>
          )}
        </section>
        ) : null}

        {activeTab === "assets" ? (
        <section className="rounded-md border border-slate-200 bg-white p-6">
            <AssetsSyncAlert status={resolvedSearchParams?.assets} />
            <AssetAttributionPanel
              assets={product.generated_assets}
              records={product.performance_records}
            />
            <AssetScaleRecommendationPanel
              assets={product.generated_assets}
              records={product.performance_records}
            />
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">素材资产库</h2>
              <p className="mt-1 text-sm text-slate-500">
                汇总当前商品已生成的主图和视频草稿，后续可扩展评分、标签、下载和投放引用
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {canEdit ? (
                <form action={`/products/${product.id}/assets/sync`} method="post">
                <button
                  type="submit"
                  className="h-8 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  同步历史素材
                </button>
                </form>
              ) : null}
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {assetLibrary.length} 个素材
              </span>
            </div>
          </div>

          {assetLibrary.length > 0 ? (
            <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {assetLibrary.map((asset) => (
                <div key={asset.url} className="overflow-hidden rounded-md border border-slate-200 bg-slate-50">
                  {asset.kind === "image" ? (
                    <a href={absoluteMediaUrl(asset.url)} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={absoluteMediaUrl(asset.url)}
                        alt={asset.title}
                        className="aspect-square w-full object-cover"
                      />
                    </a>
                  ) : (
                    <video
                      src={absoluteMediaUrl(asset.url)}
                      controls
                      className="aspect-video w-full bg-black object-contain"
                    />
                  )}
                  <div className="space-y-2 px-3 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-950">{asset.title}</p>
                      <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                        {asset.kind === "image" ? "主图" : "视频"}
                      </span>
                      <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                        V{asset.assetVersion}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">
                      {asset.model || "model"} · {asset.size || "size"}
                      {asset.duration ? ` · ${asset.duration}s` : ""}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {asset.status ? (
                        <span className={`${assetStatusTone(asset.status)} rounded-md px-2 py-1 text-xs`}>
                          {asset.status}
                        </span>
                      ) : null}
                      {asset.rating ? (
                        <span className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700">
                          {asset.rating} 分
                        </span>
                      ) : null}
                      {asset.tags.map((tag) => (
                        <span key={tag} className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                          {tag}
                        </span>
                      ))}
                      {asset.usageContexts.map((context) => (
                        <span key={context} className="rounded-md bg-sky-50 px-2 py-1 text-xs text-sky-700">
                          {context}
                        </span>
                      ))}
                    </div>
                    {asset.note ? <p className="text-xs leading-5 text-slate-500">{asset.note}</p> : null}
                    <a
                      href={absoluteMediaUrl(asset.url)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      打开素材
                    </a>
                    <details className="rounded-md border border-slate-200 bg-white px-3 py-2">
                      <summary className="cursor-pointer text-xs font-medium text-slate-700">评价素材</summary>
                      {canEdit ? (
                        <form
                        action={`/products/${product.id}/creative-plans/${asset.planId}/assets/update`}
                        method="post"
                        className="mt-3 grid gap-3"
                      >
                        <input type="hidden" name="url" value={asset.url} />
                        <input type="hidden" name="asset_type" value={asset.kind} />
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="grid gap-1.5">
                            <span className="text-xs font-medium text-slate-500">评分</span>
                            <input
                              name="rating"
                              type="number"
                              min="1"
                              max="5"
                              defaultValue={asset.rating ?? ""}
                              className="h-9 rounded-md border border-slate-200 px-2 text-sm outline-none focus:border-slate-400"
                            />
                          </label>
                          <label className="grid gap-1.5">
                            <span className="text-xs font-medium text-slate-500">状态</span>
                            <select
                              name="status"
                              defaultValue={asset.status || "待评估"}
                              className="h-9 rounded-md border border-slate-200 px-2 text-sm outline-none focus:border-slate-400"
                            >
                              <option value="待评估">待评估</option>
                              <option value="通过">通过</option>
                              <option value="弃用">弃用</option>
                              <option value="复测">复测</option>
                            </select>
                          </label>
                        </div>
                        <div className="grid gap-3 sm:grid-cols-2">
                          <label className="grid gap-1.5">
                            <span className="text-xs font-medium text-slate-500">素材版本</span>
                            <input
                              name="asset_version"
                              type="number"
                              min="1"
                              defaultValue={asset.assetVersion}
                              className="h-9 rounded-md border border-slate-200 px-2 text-sm outline-none focus:border-slate-400"
                            />
                          </label>
                          <label className="grid gap-1.5">
                            <span className="text-xs font-medium text-slate-500">使用场景</span>
                            <input
                              name="usage_contexts"
                              defaultValue={asset.usageContexts.join("，")}
                              className="h-9 rounded-md border border-slate-200 px-2 text-sm outline-none focus:border-slate-400"
                              placeholder="冷启动，人群测试，复测"
                            />
                          </label>
                        </div>
                        <label className="grid gap-1.5">
                          <span className="text-xs font-medium text-slate-500">标签</span>
                          <input
                            name="tags"
                            defaultValue={asset.tags.join("，")}
                            className="h-9 rounded-md border border-slate-200 px-2 text-sm outline-none focus:border-slate-400"
                            placeholder="通勤，控油，高点击潜力"
                          />
                        </label>
                        <label className="grid gap-1.5">
                          <span className="text-xs font-medium text-slate-500">备注</span>
                          <textarea
                            name="note"
                            defaultValue={asset.note}
                            rows={2}
                            className="resize-y rounded-md border border-slate-200 px-2 py-2 text-sm leading-5 outline-none focus:border-slate-400"
                            placeholder="记录适合投放的人群、需要优化的问题或复盘观察"
                          />
                        </label>
                        <button
                          type="submit"
                          className="h-9 w-fit rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
                        >
                          保存评价
                        </button>
                        </form>
                      ) : null}
                    </details>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              还没有生成素材。可以先到主图或视频 Tab 生成第一批草稿。
            </div>
          )}
        </section>
        ) : null}

        {activeTab === "jobs" ? (
        <section className="rounded-md border border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">生成任务中心</h2>
              <p className="mt-1 text-sm text-slate-500">
                查看当前商品所有图片和视频生成任务，包括状态、结果、错误和重试入口
              </p>
            </div>
            <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
              {product.generation_jobs.length + product.public_link_parse_tasks.length} 个任务
            </span>
          </div>

          {product.generation_jobs.length > 0 ? (
            <div className="mt-5 overflow-hidden rounded-md border border-slate-200">
              <div className="grid grid-cols-[80px_90px_110px_1fr_170px] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
                <span>ID</span>
                <span>类型</span>
                <span>状态</span>
                <span>结果 / 错误</span>
                <span>操作</span>
              </div>
              <div className="divide-y divide-slate-200">
                {product.generation_jobs.map((job) => (
                  <div
                    key={job.id}
                    className="grid grid-cols-[80px_90px_110px_1fr_170px] items-center gap-3 px-3 py-3 text-sm"
                  >
                    <span className="font-medium text-slate-700">#{job.id}</span>
                    <span className="text-slate-600">{job.kind === "video_asset" ? "视频" : "图片"}</span>
                    <JobStatusBadge job={job} />
                    <div className="min-w-0">
                      {job.status === "succeeded" && jobResultUrl(job) ? (
                        <a
                          href={absoluteMediaUrl(jobResultUrl(job) || "")}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sky-700 hover:text-sky-900"
                        >
                          打开生成结果
                        </a>
                      ) : job.error ? (
                        <p className="line-clamp-2 text-xs leading-5 text-rose-700">{job.error}</p>
                      ) : (
                        <p className="text-xs text-slate-500">
                          {job.started_at ? `开始于 ${job.started_at}` : "等待后台执行"}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/products/${product.id}/generation-jobs/${job.id}`}
                        className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        详情
                      </Link>
                      {canEdit && job.status === "failed" ? (
                        <form action={`/products/${product.id}/generation-jobs/${job.id}/retry`} method="post">
                          <input type="hidden" name="tab" value="jobs" />
                          <button
                            type="submit"
                            className="h-8 rounded-md bg-slate-950 px-3 text-xs font-medium text-white hover:bg-slate-800"
                          >
                            重试
                          </button>
                        </form>
                      ) : canEdit && (job.status === "pending" || job.status === "running") ? (
                        <form action={`/products/${product.id}/generation-jobs/${job.id}/cancel`} method="post">
                          <input type="hidden" name="tab" value="jobs" />
                          <button
                            type="submit"
                            className="h-8 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
                          >
                            取消
                          </button>
                        </form>
                      ) : (
                        <span className="text-xs text-slate-400">-</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              还没有生成任务。可以先到主图或视频 Tab 创建第一条生成任务。
            </div>
          )}

          <div className="mt-6 border-t border-slate-200 pt-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-950">公开链接解析任务</h3>
                <p className="mt-1 text-sm text-slate-500">用于把用户提交的公开商品页异步解析成竞品档案</p>
              </div>
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {product.public_link_parse_tasks.length} 个任务
              </span>
            </div>

            {product.public_link_parse_tasks.length > 0 ? (
              <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
                <div className="grid grid-cols-[80px_110px_1fr_1.2fr] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
                  <span>ID</span>
                  <span>状态</span>
                  <span>链接</span>
                  <span>结果 / 错误</span>
                </div>
                <div className="divide-y divide-slate-200">
                  {product.public_link_parse_tasks.map((task) => (
                    <div
                      key={task.id}
                      className="grid grid-cols-[80px_110px_1fr_1.2fr] items-center gap-3 px-3 py-3 text-sm"
                    >
                      <span className="font-medium text-slate-700">#{task.id}</span>
                      <LinkParseTaskStatusBadge status={task.status} />
                      <a href={task.url} target="_blank" rel="noreferrer" className="truncate text-sky-700 hover:text-sky-900">
                        {task.url}
                      </a>
                      {task.error ? (
                        <p className="line-clamp-2 text-xs leading-5 text-rose-700">{task.error}</p>
                      ) : task.result.competitor_id ? (
                        <p className="text-xs text-slate-600">已生成竞品 #{String(task.result.competitor_id)}</p>
                      ) : (
                        <p className="text-xs text-slate-500">
                          {task.next_run_at ? `等待执行：${task.next_run_at}` : "等待后台调度"}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                还没有公开链接解析任务。可以在概览里提交竞品链接。
              </div>
            )}
          </div>
        </section>
        ) : null}

        {activeTab === "video" ? (
        <section className="rounded-md border border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">短视频脚本</h2>
              <p className="mt-1 text-sm text-slate-500">
                先生成可拍摄脚本，后续再接视频生成或达人协作流程
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {videoScripts.length > 0 ? `最近 ${videoScripts.length} 条脚本` : "待生成"}
              </span>
              <form action={`/products/${product.id}/creative-plans/video-scripts/generate`} method="post">
                <button
                  type="submit"
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  <Video className="h-4 w-4" aria-hidden="true" />
                  生成脚本
                </button>
              </form>
            </div>
          </div>

          {videoScripts.length === 0 ? (
            <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              还没有短视频脚本。建议先有诊断和主图方向后再生成。
            </div>
          ) : (
            <div className="mt-5 grid gap-4">
              {videoScripts.map((script) => (
                <div key={script.id} className="rounded-md border border-slate-200 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-base font-semibold text-slate-950">{script.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        {planText(script.content, "angle")}
                      </p>
                    </div>
                    <div className="grid gap-2">
                      <span className="w-fit rounded-md bg-violet-50 px-2 py-1 text-xs text-violet-700">
                        {planValue(script.content, "duration_seconds")}s
                      </span>
                      <CreativePlanStatusActions productId={product.id} plan={script} tab="video" canEdit={canEdit} />
                    </div>
                  </div>

                  <div className="mt-4 rounded-md bg-violet-50 px-3 py-2">
                    <p className="text-xs font-medium text-violet-700">开头钩子</p>
                    <p className="mt-1 text-sm leading-6 text-slate-800">
                      {planText(script.content, "hook")}
                    </p>
                  </div>

                  <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
                    <div className="grid grid-cols-[90px_1fr_1fr] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
                      <span>镜头</span>
                      <span>画面</span>
                      <span>口播</span>
                    </div>
                    <div className="divide-y divide-slate-200">
                      {planScenes(script.content).map((scene) => (
                        <div
                          key={`${script.id}-${scene.shot}`}
                          className="grid grid-cols-[90px_1fr_1fr] gap-3 px-3 py-3 text-sm leading-6"
                        >
                          <span className="font-medium text-slate-700">{scene.shot}</span>
                          <span className="text-slate-600">{scene.visual}</span>
                          <span className="text-slate-800">{scene.voiceover}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs font-medium text-slate-500">视频草稿</p>
                      <JobStatusBadge job={latestJob(product.generation_jobs, script.id, "video_asset")} />
                      {canEdit ? (
                        <form action={`/products/${product.id}/creative-plans/${script.id}/videos/generate`} method="post">
                        <button
                          type="submit"
                          className="inline-flex h-8 items-center justify-center gap-2 rounded-md bg-violet-600 px-3 text-xs font-semibold text-white transition hover:bg-violet-700"
                        >
                          <Video className="h-3.5 w-3.5" aria-hidden="true" />
                          生成视频草稿
                        </button>
                        </form>
                      ) : null}
                    </div>
                    {generatedVideos(script.content).length > 0 ? (
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        {generatedVideos(script.content).map((video) => (
                          <div
                            key={video.url}
                            className="overflow-hidden rounded-md border border-slate-200 bg-slate-50"
                          >
                            <video
                              src={absoluteMediaUrl(video.url)}
                              controls
                              className="aspect-video w-full bg-black object-contain"
                            />
                            <div className="px-3 py-2 text-xs text-slate-500">
                              {video.model || "video model"} · {video.size || "video"} · {video.duration || "-"}s
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-5 text-center text-sm text-slate-500">
                        还没有视频草稿。确认脚本后可先生成 1 条测试视频。
                      </div>
                    )}
                    <JobError job={latestJob(product.generation_jobs, script.id, "video_asset")} />
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-[1fr_220px]">
                    <div>
                      <p className="text-xs font-medium text-slate-500">卖点证明</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {planList(script.content, "selling_point_proof").map((point) => (
                          <span key={point} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                            {point}
                          </span>
                        ))}
                      </div>
                    </div>
                    <PlanField label="转化引导" value={planText(script.content, "cta")} highlight />
                  </div>

                  {canEdit ? (
                    <details className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">
                      编辑脚本
                    </summary>
                      <VideoScriptEditForm productId={product.id} script={script} />
                    </details>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>
        ) : null}

        {activeTab === "main-images" ? (
        <section className="rounded-md border border-slate-200 bg-white p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">主图方案</h2>
              <p className="mt-1 text-sm text-slate-500">
                先生成能执行的设计方向，后续再接图片生成模型
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                {mainImagePlans.length > 0 ? `最近 ${mainImagePlans.length} 个方案` : "待生成"}
              </span>
              <form action={`/products/${product.id}/creative-plans/main-images/generate`} method="post">
                <button
                  type="submit"
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  <ImageIcon className="h-4 w-4" aria-hidden="true" />
                  生成主图
                </button>
              </form>
            </div>
          </div>

          {mainImagePlans.length === 0 ? (
            <div className="mt-5 rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              还没有主图方案。建议先生成诊断，再点击右侧“生成主图”。
            </div>
          ) : (
            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              {mainImagePlans.map((plan) => (
                <div key={plan.id} className="rounded-md border border-slate-200 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-base font-semibold text-slate-950">{plan.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500">
                        {planText(plan.content, "angle")}
                      </p>
                    </div>
                    <CreativePlanStatusActions productId={product.id} plan={plan} tab="main-images" canEdit={canEdit} />
                  </div>

                  <div className="mt-4 grid gap-3">
                    <PlanField label="主文案" value={planText(plan.content, "headline")} highlight />
                    <PlanField label="副文案" value={planText(plan.content, "sub_headline")} />
                    <PlanField label="画面布局" value={planText(plan.content, "layout")} />
                    <PlanField label="视觉重点" value={planText(plan.content, "visual_focus")} />
                  </div>

                  <div className="mt-4">
                    <p className="text-xs font-medium text-slate-500">证明点</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {planList(plan.content, "proof_points").map((point) => (
                        <span key={point} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                          {point}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs font-medium text-slate-500">图片草稿</p>
                      <JobStatusBadge job={latestJob(product.generation_jobs, plan.id, "main_image_asset")} />
                      {canEdit ? (
                        <form action={`/products/${product.id}/creative-plans/${plan.id}/images/generate`} method="post">
                        <button
                          type="submit"
                          className="inline-flex h-8 items-center justify-center gap-2 rounded-md bg-emerald-600 px-3 text-xs font-semibold text-white transition hover:bg-emerald-700"
                        >
                          <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" />
                          生成图片草稿
                        </button>
                        </form>
                      ) : null}
                    </div>
                    {generatedImages(plan.content).length > 0 ? (
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        {generatedImages(plan.content).map((image) => (
                          <a
                            key={image.url}
                            href={absoluteImageUrl(image.url)}
                            target="_blank"
                            rel="noreferrer"
                            className="group overflow-hidden rounded-md border border-slate-200 bg-slate-50"
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={absoluteImageUrl(image.url)}
                              alt={`${plan.title} 图片草稿`}
                              className="aspect-square w-full object-cover transition group-hover:scale-[1.02]"
                            />
                            <div className="px-3 py-2 text-xs text-slate-500">
                              {image.model || "image model"} · {image.size || "image"}
                            </div>
                          </a>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-3 rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
                        还没有图片草稿。确认提示词后可先生成 1 张测试图。
                      </div>
                    )}
                    <JobError job={latestJob(product.generation_jobs, plan.id, "main_image_asset")} />
                  </div>

                  {canEdit ? (
                    <details className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <summary className="cursor-pointer text-sm font-medium text-slate-700">
                      编辑方案
                    </summary>
                      <MainImagePlanEditForm productId={product.id} plan={plan} />
                    </details>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>
        ) : null}
      </div>
    </main>
  );
}

/** resolve商品页签，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function resolveProductTab(tab: string | undefined): ProductTabKey {
  return productTabs.some((item) => item.key === tab) ? (tab as ProductTabKey) : "overview";
}

/** 渲染 ProductTabNav 组件，集中展示商品页签nav所需的数据、状态和操作入口。 */
function ProductTabNav({
  productId,
  activeTab,
}: {
  productId: number;
  activeTab: ProductTabKey;
}) {
  return (
    <nav className="overflow-x-auto border-b border-slate-200" aria-label="商品运营工作区">
      <div className="flex min-w-max gap-1">
        {productTabs.map((tab) => {
          const isActive = tab.key === activeTab;
          return (
            <Link
              key={tab.key}
              href={`/products/${productId}?tab=${tab.key}`}
              className={`inline-flex h-11 items-center border-b-2 px-4 text-sm font-medium transition ${
                isActive
                  ? "border-slate-950 text-slate-950"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

type ProductWorkflowStep = {
  key: string;
  title: string;
  href: string;
  done: boolean;
  hint: string;
};

/** 渲染 ProductWorkflowPanel 组件，集中展示商品工作流面板所需的数据、状态和操作入口。 */
function ProductWorkflowPanel({
  steps,
}: {
  steps: ProductWorkflowStep[];
}) {
  const nextStep = steps.find((step) => !step.done) ?? steps[steps.length - 1];

  return (
    <section className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-cyan-700 text-white">
            <ClipboardList className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-950">单品运营流程</h2>
            <p className="mt-1 text-sm text-slate-500">{nextStep.done ? "当前商品已跑通主要闭环。" : `下一步：${nextStep.title}`}</p>
          </div>
        </div>
        <Link
          href={nextStep.href}
          className="inline-flex h-9 w-fit items-center gap-2 rounded-md bg-slate-950 px-3 text-sm font-medium text-white hover:bg-slate-800"
        >
          {nextStep.done ? "查看复盘" : "继续处理"}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>

      <div className="mt-4 grid gap-2 lg:grid-cols-4">
        {steps.map((step) => (
          <Link
            key={step.key}
            href={step.href}
            className={`rounded-md border px-3 py-3 transition ${
              step.done ? "border-emerald-100 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-950">{step.title}</p>
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />
              )}
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">{step.hint}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}

/** 构建商品工作流steps，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildProductWorkflowSteps(product: ProductDetail): ProductWorkflowStep[] {
  const hasSku = product.skus.length > 0;
  const hasInventory = product.skus.some((sku) => sku.inventory_item && sku.inventory_item.quantity > 0);
  const hasMainImagePlan = product.creative_plans.some((plan) => plan.type === "main_image");
  const hasVideoScript = product.creative_plans.some((plan) => plan.type === "video_script");
  const hasAsset = product.generated_assets.length > 0 || hasMainImagePlan || hasVideoScript;
  const hasAdPlan = product.ad_recommendations.length > 0 || product.ad_experiments.length > 0;
  const hasPerformance = product.performance_records.length > 0;

  return [
    {
      key: "profile",
      title: "建档/SKU",
      href: `/products/${product.id}?tab=overview`,
      done: Boolean(product.name && product.store_id && hasSku && hasInventory),
      hint: hasSku ? "SKU 和库存已开始维护" : "补 SKU、库存和平台映射",
    },
    {
      key: "competitor",
      title: "竞品",
      href: `/products/${product.id}?tab=overview`,
      done: product.competitors.length > 0,
      hint: product.competitors.length > 0 ? `${product.competitors.length} 个竞品样本` : "添加竞品或创建链接解析任务",
    },
    {
      key: "diagnosis",
      title: "诊断",
      href: `/products/${product.id}?tab=diagnosis`,
      done: product.diagnoses.length > 0,
      hint: product.diagnoses.length > 0 ? "已有诊断结果" : "生成商品运营诊断",
    },
    {
      key: "content",
      title: "素材",
      href: `/products/${product.id}?tab=main-images`,
      done: hasAsset,
      hint: hasAsset ? "已有主图/视频素材草稿" : "生成主图方案和视频脚本",
    },
    {
      key: "ads",
      title: "投放",
      href: `/products/${product.id}?tab=ads`,
      done: hasAdPlan,
      hint: hasAdPlan ? "已有建议或实验计划" : "生成投放建议并人工确认实验",
    },
    {
      key: "performance",
      title: "数据",
      href: `/products/${product.id}?tab=review`,
      done: hasPerformance,
      hint: hasPerformance ? `${product.performance_records.length} 条经营数据` : "回填经营数据",
    },
    {
      key: "review",
      title: "复盘",
      href: `/products/${product.id}?tab=review`,
      done: product.review_reports.length > 0,
      hint: product.review_reports.length > 0 ? "已有复盘报告" : "生成周期复盘",
    },
  ];
}

/** 渲染 DiagnosisList 组件，集中展示商品诊断列表所需的数据、状态和操作入口。 */
function DiagnosisList({
  title,
  items,
  accent = false,
}: {
  title: string;
  items: string[];
  accent?: boolean;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <p
            key={item}
            className={`rounded-md px-3 py-2 text-sm leading-6 ${
              accent ? "bg-emerald-50 text-emerald-800" : "bg-slate-50 text-slate-700"
            }`}
          >
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}

/** 渲染 ReviewList 组件，集中展示复盘列表所需的数据、状态和操作入口。 */
function ReviewList({
  title,
  items,
  accent = false,
}: {
  title: string;
  items: string[];
  accent?: boolean;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <p
            key={item}
            className={`rounded-md px-3 py-2 text-sm leading-6 ${
              accent ? "bg-amber-50 text-amber-800" : "bg-slate-50 text-slate-700"
            }`}
          >
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}

/** 渲染 AdTextList 组件，集中展示投放文本列表所需的数据、状态和操作入口。 */
function AdTextList({
  title,
  items,
  accent = false,
}: {
  title: string;
  items: string[];
  accent?: boolean;
}) {
  return (
    <div className="rounded-md border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <p
            key={item}
            className={`rounded-md px-3 py-2 text-sm leading-6 ${
              accent ? "bg-emerald-50 text-emerald-800" : "bg-slate-50 text-slate-700"
            }`}
          >
            {item}
          </p>
        ))}
      </div>
    </div>
  );
}

/** 渲染 AdObjectList 组件，集中展示投放对象列表所需的数据、状态和操作入口。 */
function AdObjectList({ title, items }: { title: string; items: Record<string, unknown>[] }) {
  return (
    <div className="rounded-md border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-3 space-y-3">
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="rounded-md bg-slate-50 px-3 py-3">
            <p className="text-sm font-medium text-slate-900">
              {contentObjectText(item, "name") || `方案 ${index + 1}`}
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              {contentObjectText(item, "rationale") ||
                contentObjectText(item, "hypothesis") ||
                contentObjectText(item, "asset_direction")}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[
                ...contentObjectList(item, "targeting"),
                contentObjectText(item, "success_metric"),
              ]
                .filter(Boolean)
                .map((value) => (
                  <span key={value} className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                    {value}
                  </span>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 渲染 BudgetPlan 组件，集中展示预算方案所需的数据、状态和操作入口。 */
function BudgetPlan({ content }: { content: Record<string, unknown> }) {
  const value = content.budget_plan;
  const budget = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
  return (
    <div className="rounded-md border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-950">预算计划</p>
      <div className="mt-3 space-y-2">
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm leading-6 text-emerald-800">
          {contentObjectText(budget, "daily_budget") || "先用小预算测试。"}
        </p>
        {contentObjectList(budget, "allocation").map((item) => (
          <p key={item} className="rounded-md bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700">
            {item}
          </p>
        ))}
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-800">
          {contentObjectText(budget, "stop_loss_rule") || "到达止损线及时暂停。"}
        </p>
      </div>
    </div>
  );
}

/** 渲染 PromotionLinkCreateForm 组件，集中展示推广链接创建表单所需的数据、状态和操作入口。 */
function PromotionLinkCreateForm({ canEdit, productId }: { canEdit: boolean; productId: number }) {
  if (!canEdit) {
    return (
      <div>
        <h2 className="text-base font-semibold text-slate-950">手动添加链接</h2>
        <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          当前账号为只读权限，不能添加推荐链接。
        </p>
      </div>
    );
  }

  return (
    <form action={`/products/${productId}/promotion-links/create`} method="post" className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-sky-600 text-white">
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">手动添加链接</h2>
          <p className="text-sm text-slate-500">保存平台商品链接、达人链接或活动页链接</p>
        </div>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">链接名称</span>
        <input
          name="label"
          required
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="例如：6月短视频A组链接"
        />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">URL</span>
        <input
          name="url"
          required
          type="url"
          className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="https://..."
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">类型</span>
          <select
            name="link_type"
            defaultValue="landing"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          >
            <option value="landing">承接页</option>
            <option value="tracking">投放追踪</option>
            <option value="affiliate">达人/分销</option>
            <option value="activity">活动页</option>
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">场景</span>
          <input
            name="scenario"
            className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
            placeholder="短视频投放"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-slate-700">备注</span>
        <textarea
          name="note"
          rows={3}
          className="mt-2 w-full resize-y rounded-md border border-slate-200 bg-white px-3 py-3 text-sm text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
          placeholder="记录链接来源、投放人群、素材版本或活动周期"
        />
      </label>

      <button
        type="submit"
        className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
      >
        <ExternalLink className="h-4 w-4" aria-hidden="true" />
        保存链接
      </button>
    </form>
  );
}

/** 渲染 AssetsSyncAlert 组件，集中展示素材sync提示所需的数据、状态和操作入口。 */
function AssetsSyncAlert({ status }: { status?: string }) {
  if (status === "synced") {
    return (
      <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        已同步历史素材到独立资产表。
      </div>
    );
  }

  if (status === "sync_failed") {
    return (
      <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        历史素材同步失败，请稍后重试。
      </div>
    );
  }

  return null;
}

/** 渲染 AssetAttributionPanel 组件，集中展示素材归因面板所需的数据、状态和操作入口。 */
function AssetAttributionPanel({
  assets,
  records,
}: {
  assets: GeneratedAsset[];
  records: PerformanceRecord[];
}) {
  const rows = buildAssetAttribution(assets, records);

  if (assets.length === 0) {
    return null;
  }

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">素材效果归因</h2>
          <p className="mt-1 text-xs text-slate-500">按经营数据中关联的生成素材汇总点击、成交、CTR 和 ROI</p>
        </div>
        <span className="w-fit rounded-md bg-white px-2.5 py-1 text-xs text-slate-600">
          {rows.filter((row) => row.recordCount > 0).length} 个有数据
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {rows.slice(0, 5).map((row) => (
          <div key={row.asset.id} className="rounded-md border border-slate-200 bg-white px-3 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-950">{row.asset.title || "生成素材"}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {row.asset.asset_type === "video" ? "视频" : "图片"} · {row.asset.model || "model"}
                </p>
              </div>
              <span className="w-fit rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                {row.recordCount} 条数据
              </span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-5">
              <InsightMetric label="点击" value={formatInteger(row.clicks)} />
              <InsightMetric label="成交" value={formatInteger(row.conversions)} />
              <InsightMetric label="CTR" value={formatNumberPercent(row.ctr)} />
              <InsightMetric label="花费" value={formatNumberMoney(row.spend)} />
              <InsightMetric label="ROI" value={formatNumberDecimal(row.roi)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 渲染 AssetScaleRecommendationPanel 组件，集中展示素材scale建议面板所需的数据、状态和操作入口。 */
function AssetScaleRecommendationPanel({
  assets,
  records,
}: {
  assets: GeneratedAsset[];
  records: PerformanceRecord[];
}) {
  const recommendation = bestAssetRecommendation(assets, records);

  if (!recommendation) {
    return null;
  }

  const action = assetScaleAction(recommendation);

  return (
    <div className="mb-5 rounded-md border border-amber-100 bg-amber-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium text-amber-700">素材放量建议</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-950">
            {recommendation.asset.title || "生成素材"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-700">{action}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-700">
              CTR {formatNumberPercent(recommendation.ctr)}
            </span>
            <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-700">
              ROI {formatNumberDecimal(recommendation.roi)}
            </span>
            <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-700">
              {recommendation.recordCount} 条数据
            </span>
          </div>
        </div>
        <a
          href={absoluteMediaUrl(recommendation.asset.url)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 w-fit shrink-0 items-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          查看素材
        </a>
      </div>
    </div>
  );
}

/** 渲染 PromotionLinkAlert 组件，集中展示推广链接提示所需的数据、状态和操作入口。 */
function PromotionLinkAlert({ status }: { status?: string }) {
  if (status === "generated") {
    return (
      <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        已生成推荐链接。
      </div>
    );
  }

  if (status === "created") {
    return (
      <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        已保存链接。
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        链接保存失败，请检查 URL 和字段格式。
      </div>
    );
  }

  return null;
}

/** 渲染 PromotionLinkCard 组件，集中展示推广链接卡片所需的数据、状态和操作入口。 */
function PromotionLinkCard({ link }: { link: PromotionLink }) {
  const shortUrl = shortPromotionLinkUrl(link.short_code);

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-slate-950">{link.label}</h3>
            <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
              {promotionLinkTypeLabel(link.link_type)}
            </span>
            <span className="rounded-md bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
              {link.status === "active" ? "启用" : link.status}
            </span>
            <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
              短链点击 {formatInteger(link.click_count)}
            </span>
          </div>
          <p className="mt-2 break-all text-xs leading-5 text-slate-500">{link.url}</p>
          {shortUrl ? (
            <p className="mt-2 break-all rounded-md bg-white px-2 py-1 text-xs leading-5 text-sky-700">
              短链：{shortUrl}
            </p>
          ) : null}
          {link.tracking_code ? (
            <p className="mt-2 w-fit rounded-md bg-white px-2 py-1 text-xs text-slate-600">
              tracking_code: {link.tracking_code}
            </p>
          ) : null}
          {link.note ? <p className="mt-2 text-sm leading-6 text-slate-600">{link.note}</p> : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {shortUrl ? (
            <a
              href={shortUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-8 w-fit items-center gap-1.5 rounded-md bg-slate-950 px-3 text-xs font-medium text-white hover:bg-slate-800"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              打开短链
            </a>
          ) : null}
          <a
            href={link.tracking_url || link.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-8 w-fit items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
            打开原链
          </a>
        </div>
      </div>
      {link.scenario ? (
        <p className="mt-2 w-fit rounded-md bg-white px-2 py-1 text-xs text-slate-600">
          {link.scenario}
        </p>
      ) : null}
    </div>
  );
}

/** 渲染 PromotionLinkAttributionPanel 组件，集中展示推广链接归因面板所需的数据、状态和操作入口。 */
function PromotionLinkAttributionPanel({
  links,
  records,
}: {
  links: PromotionLink[];
  records: PerformanceRecord[];
}) {
  const rows = buildPromotionLinkAttribution(links, records);

  if (links.length === 0) {
    return null;
  }

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">链接效果归因</h2>
          <p className="mt-1 text-xs text-slate-500">按经营数据中关联的推荐链接汇总点击、成交、花费和 ROI</p>
        </div>
        <span className="w-fit rounded-md bg-white px-2.5 py-1 text-xs text-slate-600">
          {rows.filter((row) => row.recordCount > 0).length} 个有数据
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {rows.slice(0, 5).map((row) => (
          <div key={row.link.id} className="rounded-md border border-slate-200 bg-white px-3 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-950">{row.link.label}</p>
                <p className="mt-1 text-xs text-slate-500">{row.link.scenario || promotionLinkTypeLabel(row.link.link_type)}</p>
              </div>
              <span className="w-fit rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                {row.recordCount} 条数据
              </span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-5">
              <InsightMetric label="点击" value={formatInteger(row.clicks)} />
              <InsightMetric label="成交" value={formatInteger(row.conversions)} />
              <InsightMetric label="CTR" value={formatNumberPercent(row.ctr)} />
              <InsightMetric label="花费" value={formatNumberMoney(row.spend)} />
              <InsightMetric label="ROI" value={formatNumberDecimal(row.roi)} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 渲染 AdWorkflowPanel 组件，集中展示投放工作流面板所需的数据、状态和操作入口。 */
function AdWorkflowPanel({ product }: { product: ProductDetail }) {
  const steps = buildAdWorkflowSteps(product);
  const nextStep = steps.find((step) => !step.done) ?? steps[steps.length - 1];

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">投放工作流</h2>
          <p className="mt-1 text-xs text-slate-500">
            从素材和链接生成实验计划，执行前必须人工确认，回填数据后再复盘。
          </p>
        </div>
        <Link
          href={nextStep.href}
          className="inline-flex h-9 w-fit items-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
        >
          {nextStep.done ? "查看复盘" : "继续处理"}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>

      <div className="mt-4 grid gap-2 md:grid-cols-5">
        {steps.map((step) => (
          <Link
            key={step.title}
            href={step.href}
            className={`rounded-md border px-3 py-3 transition ${
              step.done ? "border-emerald-100 bg-emerald-50" : "border-slate-200 bg-white hover:bg-slate-50"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-slate-950">{step.title}</p>
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />
              )}
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">{step.hint}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

/** 构建投放工作流steps，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildAdWorkflowSteps(product: ProductDetail) {
  const hasAsset = product.generated_assets.length > 0 || product.creative_plans.length > 0;
  const hasLink = product.promotion_links.length > 0;
  const hasRecommendation = product.ad_recommendations.length > 0;
  const hasExperiment = product.ad_experiments.length > 0;
  const hasConfirmedExperiment = product.ad_experiments.some((experiment) => experiment.status !== "draft");
  const hasPerformance = product.performance_records.length > 0;
  const hasReview = product.review_reports.length > 0;

  return [
    {
      title: "素材建议",
      done: hasAsset,
      hint: hasAsset ? "已有素材或创意方案" : "先生成主图/视频素材",
      href: `/products/${product.id}?tab=assets`,
    },
    {
      title: "承接链接",
      done: hasLink,
      hint: hasLink ? `${product.promotion_links.length} 个链接可用` : "生成或添加推广链接",
      href: `/products/${product.id}?tab=links`,
    },
    {
      title: "实验计划",
      done: hasRecommendation || hasExperiment,
      hint: hasExperiment ? `${product.ad_experiments.length} 个实验` : "生成投放建议和实验",
      href: `/products/${product.id}?tab=ads`,
    },
    {
      title: "人工确认",
      done: hasConfirmedExperiment,
      hint: hasConfirmedExperiment ? "已有非草稿实验" : "投放前由人工确认",
      href: `/products/${product.id}?tab=ads`,
    },
    {
      title: "数据复盘",
      done: hasPerformance && hasReview,
      hint: hasPerformance ? "回填数据后生成复盘" : "回填曝光、点击和成交",
      href: `/products/${product.id}?tab=review`,
    },
  ];
}

/** 渲染 AdLinkRecommendationPanel 组件，集中展示投放链接建议面板所需的数据、状态和操作入口。 */
function AdLinkRecommendationPanel({
  links,
  records,
}: {
  links: PromotionLink[];
  records: PerformanceRecord[];
}) {
  const bestLink = buildPromotionLinkAttribution(links, records).find((row) => row.recordCount > 0);

  if (!bestLink) {
    return null;
  }

  return (
    <div className="mb-5 rounded-md border border-emerald-100 bg-emerald-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-medium text-emerald-700">推荐投放链接</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-950">{bestLink.link.label}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            已关联 {bestLink.recordCount} 条经营数据，ROI {formatNumberDecimal(bestLink.roi)}，
            CTR {formatNumberPercent(bestLink.ctr)}。下一轮投放可优先沿用该链接，并继续观察转化稳定性。
          </p>
        </div>
        <a
          href={bestLink.link.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 w-fit shrink-0 items-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          打开链接
        </a>
      </div>
    </div>
  );
}

/** 渲染 AdAssetRecommendationPanel 组件，集中展示投放素材建议面板所需的数据、状态和操作入口。 */
function AdAssetRecommendationPanel({
  assets,
  records,
}: {
  assets: GeneratedAsset[];
  records: PerformanceRecord[];
}) {
  const recommendation = bestAssetRecommendation(assets, records);

  if (!recommendation) {
    return null;
  }

  return (
    <div className="mb-5 rounded-md border border-sky-100 bg-sky-50 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-medium text-sky-700">推荐投放素材</p>
          <h2 className="mt-1 text-sm font-semibold text-slate-950">
            {recommendation.asset.title || "生成素材"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            当前素材 ROI {formatNumberDecimal(recommendation.roi)}，CTR {formatNumberPercent(recommendation.ctr)}。
            下一轮建议继续小步放量，并复制 2-3 个同结构不同卖点版本。
          </p>
        </div>
        <a
          href={absoluteMediaUrl(recommendation.asset.url)}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 w-fit shrink-0 items-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white hover:bg-slate-800"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          打开素材
        </a>
      </div>
    </div>
  );
}

/** 渲染 AdExperimentDashboardPanel 组件，集中展示投放实验看板面板所需的数据、状态和操作入口。 */
function AdExperimentDashboardPanel({
  dashboard,
  assets,
  links,
}: {
  dashboard: AdExperimentDashboard | null;
  assets: GeneratedAsset[];
  links: PromotionLink[];
}) {
  if (!dashboard || dashboard.total_experiments === 0) {
    return null;
  }

  const rows = dashboard.rows.slice(0, 6);

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">实验看板</h2>
          <p className="mt-1 text-xs text-slate-500">
            按投放实验汇总回填数据，快速判断继续、暂停、复制或放量
          </p>
        </div>
        <span className="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
          {dashboard.measured_experiments}/{dashboard.total_experiments} 已回填
        </span>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        <InsightMetric label="执行中" value={formatInteger(dashboard.active_experiments)} />
        <InsightMetric label="总花费" value={formatMoney(dashboard.total_spend)} />
        <InsightMetric label="总成交额" value={formatMoney(dashboard.total_revenue)} />
        <InsightMetric label="整体 ROI" value={formatDecimal(dashboard.overall_roi)} />
      </div>

      {dashboard.best_experiment ? (
        <div className="mt-4 rounded-md border border-emerald-100 bg-emerald-50 px-3 py-3">
          <p className="text-xs font-medium text-emerald-700">当前优胜实验</p>
          <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-950">
                {dashboard.best_experiment.name}
              </h3>
              <p className="mt-1 text-sm leading-6 text-slate-700">
                ROI {formatDecimal(dashboard.best_experiment.roi)}，CTR{" "}
                {formatPercent(dashboard.best_experiment.ctr)}。
                {dashboard.best_experiment.decision_reason}
              </p>
            </div>
            <span className="w-fit shrink-0 rounded-md bg-white px-2.5 py-1 text-xs font-medium text-emerald-700">
              {adExperimentDecisionLabel(dashboard.best_experiment.decision)}
            </span>
          </div>
        </div>
      ) : null}

      <div className="mt-4 grid gap-3">
        {rows.map((row) => (
          <div key={row.ad_experiment_id} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-950">{row.name}</h3>
                  <span className="rounded-md bg-white px-2 py-1 text-xs text-slate-600">
                    {adExperimentStatusLabel(row.status)}
                  </span>
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                    {formatDateRange(row.period_start, row.period_end)}
                  </span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {generatedAssetTitle(assets, row.generated_asset_id)} ·{" "}
                  {promotionLinkTitle(links, row.promotion_link_id)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="rounded-md bg-white px-2.5 py-1 text-xs font-medium text-slate-700">
                  日预算 {formatMoney(row.daily_budget)}
                </span>
                <span className="rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                  {adExperimentDecisionLabel(row.decision)}
                </span>
              </div>
            </div>

            <div className="mt-3 grid gap-2 sm:grid-cols-6">
              <InsightMetric label="曝光" value={formatInteger(row.impressions)} />
              <InsightMetric label="点击" value={formatInteger(row.clicks)} />
              <InsightMetric label="成交" value={formatInteger(row.conversions)} />
              <InsightMetric label="CTR" value={formatPercent(row.ctr)} />
              <InsightMetric label="花费" value={formatMoney(row.spend)} />
              <InsightMetric label="ROI" value={formatDecimal(row.roi)} />
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-600">{row.decision_reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 渲染 AdExperimentPanel 组件，集中展示投放实验面板所需的数据、状态和操作入口。 */
function AdExperimentPanel({
  experiments,
  assets,
  links,
  productId,
  status,
  canEdit,
}: {
  experiments: AdExperiment[];
  assets: GeneratedAsset[];
  links: PromotionLink[];
  productId: number;
  status?: string;
  canEdit: boolean;
}) {
  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      {status === "generated" ? (
        <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          已生成投放实验计划，实际投放前仍需人工确认。
        </div>
      ) : null}
      {status === "failed" ? (
        <div className="mb-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          实验计划生成失败，请先确认素材、链接和经营数据是否已保存。
        </div>
      ) : null}
      {status === "updated" ? (
        <div className="mb-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          实验状态已更新。
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">投放实验计划</h2>
          <p className="mt-1 text-xs text-slate-500">
            把推荐素材和推荐链接组合成可复盘的测试单，只做计划和记录，不自动执行资金操作
          </p>
        </div>
        {canEdit ? (
          <form action={`/products/${productId}/ad-experiments/generate`} method="post">
          <button
            type="submit"
            className="inline-flex h-9 w-fit items-center justify-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
          >
            <Megaphone className="h-3.5 w-3.5" aria-hidden="true" />
            生成实验
          </button>
          </form>
        ) : null}
      </div>

      {experiments.length === 0 ? (
        <div className="mt-4 rounded-md border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
          还没有实验计划。可以先用现有素材和链接生成第一条小预算测试单。
        </div>
      ) : (
        <div className="mt-4 grid gap-3">
          {experiments.map((experiment) => (
            <div key={experiment.id} className="rounded-md border border-slate-200 bg-white px-4 py-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-slate-950">{experiment.name}</h3>
                    <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      {adExperimentStatusLabel(experiment.status)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{experiment.objective}</p>
                </div>
                <span className="w-fit shrink-0 rounded-md bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                  日预算 {formatMoney(experiment.daily_budget)}
                </span>
              </div>

              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <PlanField label="关联素材" value={generatedAssetTitle(assets, experiment.generated_asset_id)} />
                <PlanField label="承接链接" value={promotionLinkTitle(links, experiment.promotion_link_id)} />
                <PlanField label="人群" value={experiment.audience ?? "待补充"} />
                <PlanField label="成功指标" value={experiment.success_metric ?? "待补充"} highlight />
              </div>

              {experiment.hypothesis ? (
                <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-600">
                  {experiment.hypothesis}
                </p>
              ) : null}
              <AdExperimentStatusActions productId={productId} experiment={experiment} canEdit={canEdit} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** 渲染 AdExperimentStatusActions 组件，集中展示投放实验状态actions所需的数据、状态和操作入口。 */
function AdExperimentStatusActions({
  productId,
  experiment,
  canEdit,
}: {
  productId: number;
  experiment: AdExperiment;
  canEdit: boolean;
}) {
  const nextStatuses =
    experiment.status === "draft"
      ? [{ status: "active", label: "标记执行中" }]
      : experiment.status === "active"
        ? [
            { status: "paused", label: "标记暂停" },
            { status: "completed", label: "标记完成" },
          ]
        : experiment.status === "paused"
          ? [{ status: "active", label: "恢复执行" }]
          : [];

  if (!canEdit || nextStatuses.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {nextStatuses.map((item) => (
        <form
          key={item.status}
          action={`/products/${productId}/ad-experiments/${experiment.id}/status`}
          method="post"
        >
          <input type="hidden" name="status" value={item.status} />
          <button
            type="submit"
            className="h-8 rounded-md border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            {item.label}
          </button>
        </form>
      ))}
    </div>
  );
}

/** 把投放实验状态状态映射为中文显示文本，保持页面口径一致。 */
function adExperimentStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "执行中",
    archived: "已归档",
    completed: "已完成",
    draft: "待确认",
    paused: "已暂停",
  };
  return labels[status] ?? status;
}

/** 把投放实验决策状态映射为中文显示文本，保持页面口径一致。 */
function adExperimentDecisionLabel(decision: string): string {
  const labels: Record<string, string> = {
    keep: "继续观察",
    needs_data: "待回填",
    observe: "观察",
    pause: "建议暂停",
    scale: "可放量",
  };
  return labels[decision] ?? decision;
}

/** 格式化日期range，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatDateRange(start: string | null, end: string | null): string {
  if (!start && !end) {
    return "待回填周期";
  }
  if (start && end && start !== end) {
    return `${start} 至 ${end}`;
  }
  return start ?? end ?? "待回填周期";
}

/** 把推广链接type状态映射为中文显示文本，保持页面口径一致。 */
function promotionLinkTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    activity: "活动页",
    affiliate: "达人/分销",
    landing: "承接页",
    tracking: "投放追踪",
  };
  return labels[type] ?? type;
}

/** 渲染 CompetitorImportAlert 组件，集中展示竞品导入提示所需的数据、状态和操作入口。 */
function CompetitorImportAlert({
  competitorStatus,
  importStatus,
}: {
  competitorStatus?: string;
  importStatus?: string;
}) {
  if (importStatus === "queued") {
    return (
      <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-700">
        已创建竞品链接解析任务，可在任务中心查看后续处理结果。
      </div>
    );
  }

  if (importStatus === "success") {
    return (
      <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        已解析链接并添加为竞品。
      </div>
    );
  }

  if (importStatus === "failed") {
    return (
      <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        竞品链接解析失败。可换一个公开商品页，或先用手动表单录入关键字段。
      </div>
    );
  }

  if (competitorStatus === "failed") {
    return (
      <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        竞品保存失败，请检查名称、链接和价格格式。
      </div>
    );
  }

  return null;
}

type CompetitorInsights = {
  averagePrice: number | null;
  completeness: number;
  cheaperCount: number;
  competitorCount: number;
  higherCount: number;
  maxPrice: number | null;
  minPrice: number | null;
  priceSampleCount: number;
  topSellingPoints: Array<{ count: number; name: string }>;
};

/** 渲染 CompetitorInsightsPanel 组件，集中展示竞品洞察面板所需的数据、状态和操作入口。 */
function CompetitorInsightsPanel({ insights }: { insights: CompetitorInsights }) {
  if (insights.competitorCount === 0) {
    return null;
  }

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">竞品洞察</h2>
          <p className="mt-1 text-xs text-slate-500">基于当前竞品记录汇总价格带、卖点频次和数据完整度</p>
        </div>
        <span className="w-fit rounded-md bg-white px-2.5 py-1 text-xs text-slate-600">
          完整度 {insights.completeness}%
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <InsightMetric label="竞品数量" value={`${insights.competitorCount} 个`} />
        <InsightMetric
          label="价格带"
          value={
            insights.priceSampleCount > 0
              ? `${formatNumberMoney(insights.minPrice ?? 0)} - ${formatNumberMoney(insights.maxPrice ?? 0)}`
              : "待补充"
          }
        />
        <InsightMetric
          label="均价"
          value={insights.averagePrice === null ? "待补充" : formatNumberMoney(insights.averagePrice)}
        />
        <InsightMetric label="价格位置" value={`低于 ${insights.higherCount} 个，高于 ${insights.cheaperCount} 个`} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {insights.topSellingPoints.length > 0 ? (
          insights.topSellingPoints.map((point) => (
            <span key={point.name} className="rounded-md bg-white px-2.5 py-1 text-xs text-slate-700">
              {point.name} × {point.count}
            </span>
          ))
        ) : (
          <span className="rounded-md bg-white px-2.5 py-1 text-xs text-slate-500">
            待补充竞品卖点
          </span>
        )}
      </div>
    </div>
  );
}

/** 渲染 CompetitorMonitorPanel 组件，集中展示竞品monitor面板所需的数据、状态和操作入口。 */
function CompetitorMonitorPanel({
  competitors,
  monitors,
  productId,
  canEdit,
}: {
  competitors: Competitor[];
  monitors: CompetitorMonitor[];
  productId: number;
  canEdit: boolean;
}) {
  const monitorByCompetitor = new Map(monitors.map((monitor) => [monitor.competitor_id, monitor]));

  if (competitors.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">竞品监控</h2>
          <p className="mt-1 text-xs text-slate-500">保存监控频率和快照，检查时只解析已录入的公开链接</p>
        </div>
        <span className="w-fit rounded-md bg-white px-2.5 py-1 text-xs text-slate-600">
          已启用 {monitors.filter((monitor) => monitor.status === "active").length} 个
        </span>
      </div>

      <div className="mt-4 divide-y divide-slate-200 overflow-hidden rounded-md border border-slate-200 bg-white">
        {competitors.map((competitor) => {
          const monitor = monitorByCompetitor.get(competitor.id);
          const latestSnapshot = monitor?.snapshots?.[0];

          return (
            <div key={competitor.id} className="grid gap-3 px-4 py-3 text-sm lg:grid-cols-[1.1fr_0.9fr_1.4fr_auto] lg:items-center">
              <div>
                <p className="font-medium text-slate-950">{competitor.name}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {monitor ? `每 ${monitor.interval_days} 天检查` : competitor.url ? "可启用监控" : "缺少链接"}
                </p>
              </div>
              <div className="text-xs text-slate-500">
                <p>上次：{monitor?.last_checked_at ? formatDateTime(monitor.last_checked_at) : "-"}</p>
                <p className="mt-1">下次：{monitor?.next_check_at ? formatDateTime(monitor.next_check_at) : "-"}</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {latestSnapshot?.error ? (
                  <span className="rounded-md bg-rose-50 px-2 py-1 text-xs text-rose-700">{latestSnapshot.error}</span>
                ) : (
                  (latestSnapshot?.changes ?? ["暂无快照"]).slice(0, 3).map((change) => (
                    <span key={change} className="rounded-md bg-sky-50 px-2 py-1 text-xs text-sky-700">
                      {change}
                    </span>
                  ))
                )}
              </div>
              <div className="flex gap-2">
                {canEdit && monitor ? (
                  <form action={`/products/${productId}/competitor-monitors/${monitor.id}/run`} method="post">
                    <button
                      type="submit"
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-slate-950 px-3 text-xs font-semibold text-white transition hover:bg-slate-800"
                    >
                      <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                      检查
                    </button>
                  </form>
                ) : canEdit ? (
                  <form action={`/products/${productId}/competitors/${competitor.id}/monitor`} method="post" className="flex gap-2">
                    <input type="hidden" name="interval_days" value="1" />
                    <button
                      type="submit"
                      disabled={!competitor.url}
                      className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-white px-3 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                    >
                      启用
                    </button>
                  </form>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 渲染 InsightMetric 组件，集中展示洞察指标所需的数据、状态和操作入口。 */
function InsightMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

/** 渲染 PerformanceImportAlert 组件，集中展示经营数据导入提示所需的数据、状态和操作入口。 */
function PerformanceImportAlert({
  count,
  importStatus,
  performanceStatus,
}: {
  count?: string;
  importStatus?: string;
  performanceStatus?: string;
}) {
  if (importStatus === "success") {
    return (
      <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
        已导入 {count ?? "多"} 条经营数据。
      </div>
    );
  }

  if (importStatus === "empty") {
    return (
      <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
        CSV 中没有可导入的数据，请检查日期列和表头。
      </div>
    );
  }

  if (importStatus === "failed" || performanceStatus === "failed") {
    return (
      <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        数据保存失败，请检查日期、数字格式和素材 ID 是否属于当前商品。
      </div>
    );
  }

  return null;
}

type PerformanceSummary = {
  clicks: number;
  conversions: number;
  conversionRate: number | null;
  ctr: number | null;
  impressions: number;
  recordCount: number;
  revenue: number;
  roi: number | null;
  spend: number;
};

/** 渲染 PerformanceSummaryCards 组件，集中展示经营数据汇总cards所需的数据、状态和操作入口。 */
function PerformanceSummaryCards({ summary }: { summary: PerformanceSummary }) {
  if (summary.recordCount === 0) {
    return null;
  }

  const items = [
    { label: "数据周期", value: `${summary.recordCount} 条` },
    { label: "总曝光", value: formatInteger(summary.impressions) },
    { label: "整体 CTR", value: formatNumberPercent(summary.ctr) },
    { label: "总成交", value: formatInteger(summary.conversions) },
    { label: "总花费", value: formatNumberMoney(summary.spend) },
    { label: "整体 ROI", value: formatNumberDecimal(summary.roi) },
  ];

  return (
    <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs text-slate-500">{item.label}</p>
          <p className="mt-1 text-lg font-semibold text-slate-950">{item.value}</p>
        </div>
      ))}
    </div>
  );
}

/** 渲染 PerformanceTrendPanel 组件，集中展示经营数据趋势面板所需的数据、状态和操作入口。 */
function PerformanceTrendPanel({ records }: { records: PerformanceRecord[] }) {
  const trendRecords = [...records]
    .sort((a, b) => a.period_end.localeCompare(b.period_end) || a.id - b.id)
    .slice(-5);

  if (trendRecords.length < 2) {
    return null;
  }

  const roiValues = trendRecords.map((record) => numberValue(record.roi));
  const maxRoi = Math.max(...roiValues, 1);

  return (
    <div className="mb-5 rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">经营趋势</h2>
          <p className="mt-1 text-xs text-slate-500">查看最近 {trendRecords.length} 条数据的 CTR、转化率和 ROI 变化</p>
        </div>
        <span className="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
          最近记录
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        {trendRecords.map((record) => {
          const ctr = numberValue(record.ctr);
          const conversionRate = numberValue(record.conversion_rate);
          const roi = numberValue(record.roi);

          return (
            <div key={record.id} className="grid gap-2 rounded-md bg-slate-50 px-3 py-3">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="font-medium text-slate-700">
                  {record.period_start} 至 {record.period_end}
                </span>
                <span className="text-slate-500">{record.conversions ?? 0} 单</span>
              </div>
              <TrendBar label="CTR" value={formatNumberPercent(ctr)} percent={Math.min(ctr / 0.08, 1) * 100} />
              <TrendBar
                label="转化"
                value={formatNumberPercent(conversionRate)}
                percent={Math.min(conversionRate / 0.08, 1) * 100}
              />
              <TrendBar label="ROI" value={formatNumberDecimal(roi)} percent={(roi / maxRoi) * 100} accent />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 渲染 TrendBar 组件，集中展示趋势bar所需的数据、状态和操作入口。 */
function TrendBar({
  accent = false,
  label,
  percent,
  value,
}: {
  accent?: boolean;
  label: string;
  percent: number;
  value: string;
}) {
  return (
    <div className="grid grid-cols-[52px_1fr_54px] items-center gap-2 text-xs">
      <span className="text-slate-500">{label}</span>
      <div className="h-2 overflow-hidden rounded-full bg-white">
        <div
          className={`h-full rounded-full ${accent ? "bg-emerald-500" : "bg-sky-500"}`}
          style={{ width: `${Math.max(4, Math.min(percent, 100))}%` }}
        />
      </div>
      <span className="text-right font-medium text-slate-700">{value}</span>
    </div>
  );
}

/** 渲染 StageCard 组件，集中展示阶段卡片所需的数据、状态和操作入口。 */
function StageCard({
  icon: Icon,
  title,
  detail,
}: {
  icon: typeof CircleDollarSign;
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-100 text-slate-700">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-slate-950">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-500">{detail}</p>
    </div>
  );
}

/** 渲染 GenerationJobSummary 组件，集中展示生成任务任务汇总所需的数据、状态和操作入口。 */
function GenerationJobSummary({
  activeTab,
  canEdit,
  jobs,
  productId,
}: {
  activeTab: ProductTabKey;
  canEdit: boolean;
  jobs: GenerationJob[];
  productId: number;
}) {
  if (jobs.length === 0) {
    return null;
  }

  return (
    <section className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">生成任务</h2>
          <p className="mt-1 text-xs text-slate-500">图片和视频生成会在后台继续执行，页面会自动刷新状态。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5"
            >
              <span className="text-xs text-slate-500">{job.kind === "video_asset" ? "视频" : "图片"} #{job.id}</span>
              <JobStatusBadge job={job} />
              {canEdit && job.status === "failed" ? (
                <form action={`/products/${productId}/generation-jobs/${job.id}/retry`} method="post">
                  <input type="hidden" name="tab" value={activeTab} />
                  <button
                    type="submit"
                    className="h-6 rounded-md bg-slate-950 px-2 text-xs font-medium text-white hover:bg-slate-800"
                  >
                    重试
                  </button>
                </form>
              ) : canEdit && (job.status === "pending" || job.status === "running") ? (
                <form action={`/products/${productId}/generation-jobs/${job.id}/cancel`} method="post">
                  <input type="hidden" name="tab" value={activeTab} />
                  <button
                    type="submit"
                    className="h-6 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    取消
                  </button>
                </form>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      {jobs.some((job) => job.status === "failed" && job.error) ? (
        <div className="mt-3 grid gap-2">
          {jobs
            .filter((job) => job.status === "failed" && job.error)
            .map((job) => (
              <JobError key={job.id} job={job} />
            ))}
        </div>
      ) : null}
    </section>
  );
}

/** 渲染 JobStatusBadge 组件，集中展示任务状态状态徽标所需的数据、状态和操作入口。 */
function JobStatusBadge({ job }: { job: GenerationJob | undefined }) {
  if (!job) {
    return null;
  }

  const statusLabels: Record<GenerationJob["status"], string> = {
    pending: "排队中",
    running: "生成中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  const tone: Record<GenerationJob["status"], string> = {
    pending: "bg-slate-100 text-slate-600",
    running: "bg-amber-50 text-amber-700",
    succeeded: "bg-emerald-50 text-emerald-700",
    failed: "bg-rose-50 text-rose-700",
    cancelled: "bg-slate-100 text-slate-500",
  };

  return (
    <span
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-2.5 text-xs font-medium ${tone[job.status]}`}
    >
      {job.status === "pending" || job.status === "running" ? (
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
      ) : null}
      {statusLabels[job.status]}
    </span>
  );
}

/** 渲染 LinkParseTaskStatusBadge 组件，集中展示链接解析任务状态状态徽标所需的数据、状态和操作入口。 */
function LinkParseTaskStatusBadge({ status }: { status: string }) {
  const statusLabels: Record<string, string> = {
    pending: "等待中",
    running: "执行中",
    succeeded: "成功",
    failed: "失败",
  };
  const tone: Record<string, string> = {
    pending: "bg-amber-50 text-amber-700",
    running: "bg-sky-50 text-sky-700",
    succeeded: "bg-emerald-50 text-emerald-700",
    failed: "bg-rose-50 text-rose-700",
  };

  return (
    <span className={`w-fit rounded-md px-2 py-1 text-xs font-medium ${tone[status] ?? "bg-slate-100 text-slate-600"}`}>
      {statusLabels[status] ?? status}
    </span>
  );
}

/** 渲染 JobError 组件，集中展示任务错误所需的数据、状态和操作入口。 */
function JobError({ job }: { job: GenerationJob | undefined }) {
  if (!job || job.status !== "failed" || !job.error) {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
      {job.error}
    </div>
  );
}

/** 最新任务，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function latestJob(
  jobs: GenerationJob[],
  creativePlanId: number,
  kind: GenerationJob["kind"],
): GenerationJob | undefined {
  return jobs.find((job) => job.creative_plan_id === creativePlanId && job.kind === kind);
}

/** 任务结果URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function jobResultUrl(job: GenerationJob): string | null {
  const value = job.result.url;
  return typeof value === "string" && value ? value : null;
}

type AssetLibraryItem = {
  assetVersion: number;
  kind: "image" | "video";
  planId: number;
  title: string;
  model?: string;
  size?: string;
  duration?: number;
  rating?: number;
  tags: string[];
  note: string;
  status: string;
  url: string;
  usageContexts: string[];
};

/** 收集素材素材库，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function collectAssetLibrary(
  generatedAssets: GeneratedAsset[],
  creativePlans: Array<{ id: number; title: string; content: Record<string, unknown> }>,
): AssetLibraryItem[] {
  // 优先使用统一素材库；没有迁移数据时再兼容读取旧版 creative_plan.content 内的生成结果。
  if (generatedAssets.length > 0) {
    return generatedAssets.map((asset) => ({
      assetVersion: asset.asset_version ?? 1,
      duration: asset.duration ?? undefined,
      kind: asset.asset_type === "video" ? "video" : "image",
      model: asset.model ?? undefined,
      note: asset.note ?? "",
      planId: asset.creative_plan_id,
      rating: asset.rating ?? undefined,
      size: asset.size ?? undefined,
      status: asset.status ?? "",
      tags: asset.tags,
      title: asset.title ?? creativePlans.find((plan) => plan.id === asset.creative_plan_id)?.title ?? "生成素材",
      url: asset.url,
      usageContexts: asset.usage_contexts ?? [],
    }));
  }

  return collectAssetsFromCreativePlans(creativePlans);
}

/** 收集素材from创意plans，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function collectAssetsFromCreativePlans(
  creativePlans: Array<{ id: number; title: string; content: Record<string, unknown> }>,
): AssetLibraryItem[] {
  return creativePlans.flatMap((plan) => [
    ...generatedImages(plan.content).map((image) => ({
      kind: "image" as const,
      planId: plan.id,
      title: plan.title,
      ...image,
    })),
    ...generatedVideos(plan.content).map((video) => ({
      kind: "video" as const,
      planId: plan.id,
      title: plan.title,
      ...video,
    })),
  ]);
}

/** 渲染 PlanField 组件，集中展示方案字段所需的数据、状态和操作入口。 */
function PlanField({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className={`rounded-md px-3 py-2 ${highlight ? "bg-emerald-50" : "bg-slate-50"}`}>
      <p className={`text-xs font-medium ${highlight ? "text-emerald-700" : "text-slate-500"}`}>
        {label}
      </p>
      <p className="mt-1 text-sm leading-6 text-slate-800">{value || "-"}</p>
    </div>
  );
}

/** 方案文本，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planText(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

/** 内容文本，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function contentText(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

/** 方案值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planValue(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  return "";
}

/** 方案列表，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** 内容objects，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function contentObjects(content: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = content[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
}

/** 内容列表，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function contentList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** 内容对象文本，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function contentObjectText(content: Record<string, unknown>, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

/** 内容对象列表，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function contentObjectList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** 处理生成images交互，维护必要状态并把副作用交给受控路由或后端 API。 */
function generatedImages(content: Record<string, unknown>): Array<{
  assetVersion: number;
  model?: string;
  size?: string;
  rating?: number;
  tags: string[];
  note: string;
  status: string;
  url: string;
  usageContexts: string[];
}> {
  // creative_plan.content 来自 AI/规则生成和人工编辑，读取时必须逐项收窄类型，避免坏数据打断页面。
  const value = content.generated_images;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => ({
      assetVersion: typeof item.asset_version === "number" && item.asset_version > 0 ? item.asset_version : 1,
      model: typeof item.model === "string" ? item.model : undefined,
      size: typeof item.size === "string" ? item.size : undefined,
      rating: typeof item.rating === "number" ? item.rating : undefined,
      tags: Array.isArray(item.tags)
        ? item.tags.filter((tag): tag is string => typeof tag === "string")
        : [],
      note: typeof item.note === "string" ? item.note : "",
      status: typeof item.status === "string" ? item.status : "",
      url: typeof item.url === "string" ? item.url : "",
      usageContexts: Array.isArray(item.usage_contexts)
        ? item.usage_contexts.filter((context): context is string => typeof context === "string")
        : [],
    }))
    .filter((item) => item.url);
}

/** 绝对地址图片URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function absoluteImageUrl(url: string): string {
  return absoluteMediaUrl(url);
}

/** 处理生成videos交互，维护必要状态并把副作用交给受控路由或后端 API。 */
function generatedVideos(content: Record<string, unknown>): Array<{
  assetVersion: number;
  model?: string;
  size?: string;
  duration?: number;
  rating?: number;
  tags: string[];
  note: string;
  status: string;
  url: string;
  usageContexts: string[];
}> {
  // 视频素材同样从结构化 content 中安全提取，缺失字段只影响展示，不影响页面整体渲染。
  const value = content.generated_videos;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => ({
      assetVersion: typeof item.asset_version === "number" && item.asset_version > 0 ? item.asset_version : 1,
      model: typeof item.model === "string" ? item.model : undefined,
      size: typeof item.size === "string" ? item.size : undefined,
      duration: typeof item.duration === "number" ? item.duration : undefined,
      rating: typeof item.rating === "number" ? item.rating : undefined,
      tags: Array.isArray(item.tags)
        ? item.tags.filter((tag): tag is string => typeof tag === "string")
        : [],
      note: typeof item.note === "string" ? item.note : "",
      status: typeof item.status === "string" ? item.status : "",
      url: typeof item.url === "string" ? item.url : "",
      usageContexts: Array.isArray(item.usage_contexts)
        ? item.usage_contexts.filter((context): context is string => typeof context === "string")
        : [],
    }))
    .filter((item) => item.url);
}

/** 把素材状态状态映射为视觉样式，避免组件内散落条件分支。 */
function assetStatusTone(status: string): string {
  const tones: Record<string, string> = {
    待评估: "bg-slate-100 text-slate-600",
    通过: "bg-emerald-50 text-emerald-700",
    弃用: "bg-rose-50 text-rose-700",
    复测: "bg-amber-50 text-amber-700",
  };
  return tones[status] ?? "bg-slate-100 text-slate-600";
}

/** 把投放建议确认状态映射为中文显示文本，保持页面口径一致。 */
function adRecommendationConfirmationLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待人工确认",
    confirmed: "已人工确认",
    rejected: "暂不采纳",
  };
  return labels[status] ?? "待人工确认";
}

/** 把投放建议确认状态映射为视觉样式，避免组件内散落条件分支。 */
function adRecommendationConfirmationTone(status: string): string {
  const tones: Record<string, string> = {
    pending: "bg-amber-100 text-amber-700",
    confirmed: "bg-emerald-100 text-emerald-700",
    rejected: "bg-slate-100 text-slate-600",
  };
  return tones[status] ?? "bg-amber-100 text-amber-700";
}

/** 绝对地址媒体URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function absoluteMediaUrl(url: string): string {
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return url;
  }
  return `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}${url}`;
}

/** 短链推广链接URL，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function shortPromotionLinkUrl(shortCode: string | null): string | null {
  if (!shortCode) {
    return null;
  }
  return `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/links/r/${shortCode}`;
}

/** 方案scenes，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function planScenes(content: Record<string, unknown>): Array<{
  shot: string;
  visual: string;
  voiceover: string;
}> {
  const scenes = content.scenes;
  if (!Array.isArray(scenes)) {
    return [];
  }

  return scenes
    .filter((scene): scene is Record<string, unknown> => Boolean(scene) && typeof scene === "object")
    .map((scene) => ({
      shot: typeof scene.shot === "string" ? scene.shot : "",
      visual: typeof scene.visual === "string" ? scene.visual : "",
      voiceover: typeof scene.voiceover === "string" ? scene.voiceover : "",
    }));
}

/** 把创意方案状态映射为中文显示文本，保持页面口径一致。 */
function creativePlanTitle(
  creativePlans: Array<{ id: number; title: string; type: string }>,
  creativePlanId: number | null,
): string {
  if (!creativePlanId) {
    return "未关联";
  }
  const plan = creativePlans.find((item) => item.id === creativePlanId);
  if (!plan) {
    return "未知素材";
  }
  return `${plan.type === "main_image" ? "主图" : "视频"} · ${plan.title}`;
}

/** 把推广链接状态映射为中文显示文本，保持页面口径一致。 */
function promotionLinkTitle(promotionLinks: PromotionLink[], promotionLinkId: number | null): string {
  if (!promotionLinkId) {
    return "未关联";
  }
  const link = promotionLinks.find((item) => item.id === promotionLinkId);
  return link?.label ?? "未知链接";
}

/** 把投放实验状态映射为中文显示文本，保持页面口径一致。 */
function adExperimentTitle(adExperiments: AdExperiment[], adExperimentId: number | null): string {
  if (!adExperimentId) {
    return "未关联";
  }
  const experiment = adExperiments.find((item) => item.id === adExperimentId);
  return experiment?.name ?? "未知实验";
}

/** 把生成素材状态映射为中文显示文本，保持页面口径一致。 */
function generatedAssetTitle(assets: GeneratedAsset[], generatedAssetId: number | null): string {
  if (!generatedAssetId) {
    return "未关联";
  }
  const asset = assets.find((item) => item.id === generatedAssetId);
  if (!asset) {
    return "未知素材";
  }
  return `${asset.asset_type === "video" ? "视频" : "图片"} · ${asset.title || "生成素材"}`;
}

/** 构建推广链接归因，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildPromotionLinkAttribution(
  links: PromotionLink[],
  records: PerformanceRecord[],
): Array<{
  clicks: number;
  conversions: number;
  ctr: number | null;
  impressions: number;
  link: PromotionLink;
  recordCount: number;
  revenue: number;
  roi: number | null;
  spend: number;
}> {
  // 链接归因只汇总用户回填的经营记录和短链点击，不代表平台广告后台实时花费。
  return links
    .map((link) => {
      const linkedRecords = records.filter((record) => record.promotion_link_id === link.id);
      const summary = summarizePerformance(linkedRecords);

      return {
        clicks: summary.clicks,
        conversions: summary.conversions,
        ctr: summary.ctr,
        impressions: summary.impressions,
        link,
        recordCount: summary.recordCount,
        revenue: summary.revenue,
        roi: summary.roi,
        spend: summary.spend,
      };
    })
    .sort((a, b) => b.recordCount - a.recordCount || (b.roi ?? -1) - (a.roi ?? -1));
}

/** 构建素材归因，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildAssetAttribution(
  assets: GeneratedAsset[],
  records: PerformanceRecord[],
): Array<{
  asset: GeneratedAsset;
  clicks: number;
  conversions: number;
  ctr: number | null;
  impressions: number;
  recordCount: number;
  revenue: number;
  roi: number | null;
  spend: number;
}> {
  // 素材归因以 generated_asset_id 关联经营记录，帮助运营判断复测或弃用，不自动改素材状态。
  return assets
    .map((asset) => {
      const linkedRecords = records.filter((record) => record.generated_asset_id === asset.id);
      const summary = summarizePerformance(linkedRecords);

      return {
        asset,
        clicks: summary.clicks,
        conversions: summary.conversions,
        ctr: summary.ctr,
        impressions: summary.impressions,
        recordCount: summary.recordCount,
        revenue: summary.revenue,
        roi: summary.roi,
        spend: summary.spend,
      };
    })
    .sort((a, b) => b.recordCount - a.recordCount || (b.roi ?? -1) - (a.roi ?? -1));
}

/** 最佳素材建议，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function bestAssetRecommendation(assets: GeneratedAsset[], records: PerformanceRecord[]) {
  return buildAssetAttribution(assets, records)
    .filter((row) => row.recordCount > 0)
    .sort((a, b) => {
      const roiDiff = (b.roi ?? -1) - (a.roi ?? -1);
      if (roiDiff !== 0) {
        return roiDiff;
      }
      return (b.ctr ?? -1) - (a.ctr ?? -1);
    })[0];
}

/** 素材scaleaction，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function assetScaleAction(row: NonNullable<ReturnType<typeof bestAssetRecommendation>>): string {
  const roi = row.roi ?? 0;
  const ctr = row.ctr ?? 0;

  if (roi >= 3 && ctr >= 0.05) {
    return "ROI 和 CTR 都表现较好，建议下一轮保留该素材结构，小幅提高预算，并复制同结构的不同卖点版本继续测试。";
  }
  if (roi >= 2) {
    return "ROI 有放量潜力，但还需要观察点击稳定性。建议先保持预算或小幅加预算，同时补 1-2 个相似素材做对照。";
  }
  if (ctr >= 0.05) {
    return "点击表现不错但 ROI 还不够稳，建议检查承接页、价格权益和人群匹配，再决定是否放量。";
  }
  return "当前样本还不足以直接放量，建议继续小预算测试，优先优化首屏卖点和画面识别度。";
}

/** 构建竞品洞察，从现有业务数据推导稳定的页面展示模型，不在渲染阶段修改源数据。 */
function buildCompetitorInsights(competitors: Competitor[], productPrice: string | null): CompetitorInsights {
  // 竞品洞察只基于已录入/解析字段做轻量提示，缺样本时不推断市场真实价格带。
  const prices = competitors
    .map((competitor) => Number(competitor.price))
    .filter((price) => Number.isFinite(price) && price > 0);
  const currentPrice = Number(productPrice);
  const hasCurrentPrice = Number.isFinite(currentPrice) && currentPrice > 0;
  const pointCounts = new Map<string, number>();
  let completenessScore = 0;

  competitors.forEach((competitor) => {
    if (competitor.url) {
      completenessScore += 1;
    }
    if (competitor.price) {
      completenessScore += 1;
    }
    if (competitor.title) {
      completenessScore += 1;
    }
    if (competitor.selling_points.length > 0) {
      completenessScore += 1;
    }

    competitor.selling_points.forEach((point) => {
      pointCounts.set(point, (pointCounts.get(point) ?? 0) + 1);
    });
  });

  return {
    averagePrice:
      prices.length > 0 ? prices.reduce((sum, price) => sum + price, 0) / prices.length : null,
    cheaperCount: hasCurrentPrice ? prices.filter((price) => price < currentPrice).length : 0,
    competitorCount: competitors.length,
    completeness:
      competitors.length > 0 ? Math.round((completenessScore / (competitors.length * 4)) * 100) : 0,
    higherCount: hasCurrentPrice ? prices.filter((price) => price > currentPrice).length : 0,
    maxPrice: prices.length > 0 ? Math.max(...prices) : null,
    minPrice: prices.length > 0 ? Math.min(...prices) : null,
    priceSampleCount: prices.length,
    topSellingPoints: [...pointCounts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-CN"))
      .slice(0, 8)
      .map(([name, count]) => ({ count, name })),
  };
}

/** summarize经营数据，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function summarizePerformance(records: PerformanceRecord[]): PerformanceSummary {
  // 前端汇总用于看板展示，权威入库计算仍在后端；这里不写回任何实验或复盘状态。
  const summary = records.reduce(
    (accumulator, record) => {
      const impressions = record.impressions ?? 0;
      const clicks = record.clicks ?? 0;
      const conversions = record.conversions ?? 0;
      const spend = numberValue(record.spend);
      const revenue = numberValue(record.revenue);

      return {
        clicks: accumulator.clicks + clicks,
        conversions: accumulator.conversions + conversions,
        impressions: accumulator.impressions + impressions,
        recordCount: accumulator.recordCount + 1,
        revenue: accumulator.revenue + revenue,
        spend: accumulator.spend + spend,
      };
    },
    {
      clicks: 0,
      conversions: 0,
      impressions: 0,
      recordCount: 0,
      revenue: 0,
      spend: 0,
    },
  );

  return {
    ...summary,
    conversionRate: summary.clicks > 0 ? summary.conversions / summary.clicks : null,
    ctr: summary.impressions > 0 ? summary.clicks / summary.impressions : null,
    roi: summary.spend > 0 ? summary.revenue / summary.spend : null,
  };
}

/** 数值值，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function numberValue(value: string | null): number {
  if (!value) {
    return 0;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

/** 格式化percent，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatPercent(value: string | null): string {
  if (!value) {
    return "-";
  }
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : "-";
}

/** 格式化小数，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatDecimal(value: string | null): string {
  if (!value) {
    return "-";
  }
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(2) : "-";
}

/** 格式化金额，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatMoney(value: string | null): string {
  if (!value) {
    return "-";
  }
  const number = Number(value);
  return Number.isFinite(number) ? `¥${number.toFixed(2)}` : "-";
}

/** 格式化整数，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatInteger(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

/** 格式化日期time，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

/** 格式化数值percent，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatNumberPercent(value: number | null): string {
  return value === null ? "-" : `${(value * 100).toFixed(2)}%`;
}

/** 格式化数值小数，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatNumberDecimal(value: number | null): string {
  return value === null ? "-" : value.toFixed(2);
}

/** 格式化数值金额，统一空值、本地化和页面展示规则，避免各组件重复格式化。 */
function formatNumberMoney(value: number): string {
  return `¥${value.toFixed(2)}`;
}
