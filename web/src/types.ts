export type Platform =
  | "douyin"
  | "taobao"
  | "tmall"
  | "pinduoduo"
  | "jd"
  | "tiktok_shop"
  | "amazon"
  | "other";

export type Product = {
  id: number;
  store_id: number | null;
  name: string;
  platform: Platform;
  category: string | null;
  price: string | null;
  cost: string | null;
  target_audience: string | null;
  selling_points: string[];
  product_url: string | null;
  external_product_id: string | null;
  platform_status: string | null;
  images: string[];
  created_at: string;
  updated_at: string;
};

export type Store = {
  id: number;
  name: string;
  platform: Platform;
  status: "active" | "paused" | "closed";
  external_store_id: string | null;
  owner_name: string | null;
  note: string | null;
  platform_accounts: PlatformAccount[];
  created_at: string;
  updated_at: string;
};

export type PlatformAccount = {
  id: number;
  store_id: number;
  platform: Platform;
  account_name: string;
  external_account_id: string | null;
  status: "active" | "expired" | "disabled";
  auth_metadata: Record<string, unknown>;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductSku = {
  id: number;
  product_id: number;
  sku_code: string;
  name: string;
  attributes: Record<string, unknown>;
  price: string | null;
  cost: string | null;
  status: "active" | "inactive";
  inventory_item: InventoryItem | null;
  inventory_movements: InventoryMovement[];
  created_at: string;
  updated_at: string;
};

export type InventoryItem = {
  id: number;
  sku_id: number;
  quantity: number;
  locked_quantity: number;
  warning_threshold: number;
  location: string | null;
  created_at: string;
  updated_at: string;
};

export type InventoryMovement = {
  id: number;
  inventory_item_id: number;
  sku_id: number;
  movement_type: "inbound" | "outbound" | "adjustment" | "lock" | "release";
  quantity_delta: number;
  locked_delta: number;
  before_quantity: number;
  after_quantity: number;
  before_locked_quantity: number;
  after_locked_quantity: number;
  reason: string | null;
  reference_type: string | null;
  reference_id: string | null;
  operator_name: string | null;
  created_at: string;
  updated_at: string;
};

export type StoreInventoryRow = {
  product_id: number;
  product_name: string;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  quantity: number;
  locked_quantity: number;
  available_quantity: number;
  warning_threshold: number;
  is_low_stock: boolean;
  location: string | null;
};

export type StoreInventorySummary = {
  store_id: number;
  sku_count: number;
  total_quantity: number;
  total_locked_quantity: number;
  total_available_quantity: number;
  low_stock_count: number;
  rows: StoreInventoryRow[];
};

export type StoreInventoryMovementRow = {
  id: number;
  product_id: number;
  product_name: string;
  sku_id: number;
  sku_code: string;
  sku_name: string;
  movement_type: "inbound" | "outbound" | "adjustment" | "lock" | "release";
  quantity_delta: number;
  locked_delta: number;
  before_quantity: number;
  after_quantity: number;
  before_locked_quantity: number;
  after_locked_quantity: number;
  reason: string | null;
  operator_name: string | null;
  created_at: string;
};

export type StoreInventoryAdvice = {
  source: string;
  summary: string;
  risks: string[];
  replenishment_actions: string[];
  operation_actions: string[];
  ad_controls: string[];
  raw_output: Record<string, unknown>;
};

export type PlatformProductMapping = {
  id: number;
  store_id: number | null;
  product_id: number;
  sku_id: number | null;
  platform: Platform;
  external_product_id: string;
  external_sku_id: string | null;
  listing_url: string | null;
  status: string | null;
  raw_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Competitor = {
  id: number;
  product_id: number;
  name: string;
  platform: Platform;
  url: string | null;
  price: string | null;
  sales_hint: string | null;
  title: string | null;
  main_image: string | null;
  selling_points: string[];
  review_keywords: string[];
  created_at: string;
  updated_at: string;
};

export type CompetitorMonitorSnapshot = {
  id: number;
  monitor_id: number;
  product_id: number;
  competitor_id: number;
  checked_at: string;
  status: string;
  title: string | null;
  price: string | null;
  sales_hint: string | null;
  main_image: string | null;
  selling_points: string[];
  changes: string[];
  raw_payload: Record<string, unknown>;
  error: string | null;
};

export type CompetitorMonitor = {
  id: number;
  product_id: number;
  competitor_id: number;
  status: string;
  interval_days: number;
  last_checked_at: string | null;
  next_check_at: string | null;
  last_snapshot_id: number | null;
  note: string | null;
  snapshots: CompetitorMonitorSnapshot[];
  created_at: string;
  updated_at: string;
};

export type CreativePlan = {
  id: number;
  product_id: number;
  type: "main_image" | "video_script" | "title" | "detail";
  title: string;
  content: Record<string, unknown>;
  rationale: string | null;
  status: "draft" | "selected" | "archived";
  created_at: string;
  updated_at: string;
};

export type PerformanceRecord = {
  id: number;
  product_id: number;
  creative_plan_id: number | null;
  ad_experiment_id: number | null;
  promotion_link_id: number | null;
  generated_asset_id: number | null;
  period_start: string;
  period_end: string;
  impressions: number | null;
  clicks: number | null;
  ctr: string | null;
  conversions: number | null;
  conversion_rate: string | null;
  spend: string | null;
  revenue: string | null;
  roi: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type ReviewReport = {
  id: number;
  product_id: number;
  period_start: string;
  period_end: string;
  summary: string;
  insights: string[];
  next_actions: string[];
  created_at: string;
  updated_at: string;
};

export type AdRecommendation = {
  id: number;
  product_id: number;
  source: string;
  summary: string;
  content: Record<string, unknown>;
  confirmation_status: string;
  confirmed_by_user_id: number | null;
  confirmed_at: string | null;
  confirmation_note: string | null;
  created_at: string;
  updated_at: string;
};

export type AdExperiment = {
  id: number;
  product_id: number;
  generated_asset_id: number | null;
  promotion_link_id: number | null;
  name: string;
  objective: string;
  audience: string | null;
  daily_budget: string | null;
  status: string;
  success_metric: string | null;
  hypothesis: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type AdExperimentSummary = {
  ad_experiment_id: number;
  name: string;
  status: string;
  generated_asset_id: number | null;
  promotion_link_id: number | null;
  daily_budget: string | null;
  record_count: number;
  period_start: string | null;
  period_end: string | null;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: string;
  revenue: string;
  ctr: string | null;
  conversion_rate: string | null;
  roi: string | null;
  cpc: string | null;
  cpa: string | null;
  decision: string;
  decision_reason: string;
};

export type AdExperimentDashboard = {
  product_id: number;
  total_experiments: number;
  active_experiments: number;
  measured_experiments: number;
  total_spend: string;
  total_revenue: string;
  overall_roi: string | null;
  best_experiment: AdExperimentSummary | null;
  rows: AdExperimentSummary[];
};

export type PromotionLink = {
  id: number;
  product_id: number;
  label: string;
  url: string;
  link_type: string;
  scenario: string | null;
  status: string;
  tracking_code: string | null;
  short_code: string | null;
  tracking_url: string | null;
  click_count: number;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type ProductDiagnosis = {
  id: number;
  product_id: number;
  agent_run_id?: number | null;
  source: string;
  positioning: string;
  price_band: string;
  audience_insights: string[];
  pain_points: string[];
  selling_point_analysis: string[];
  risks: string[];
  recommendations: string[];
  raw_output: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GenerationJob = {
  id: number;
  product_id: number;
  creative_plan_id: number;
  kind: "main_image_asset" | "video_asset";
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  result: Record<string, unknown>;
  error: string | null;
  attempts: number;
  max_attempts: number;
  locked_at: string | null;
  locked_by: string | null;
  next_run_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  events: GenerationJobEvent[];
  created_at: string;
  updated_at: string;
};

export type GenerationJobEvent = {
  id: number;
  job_id: number;
  event_type: string;
  status: GenerationJob["status"] | null;
  message: string | null;
  payload: Record<string, unknown>;
  worker_id: string | null;
  created_at: string;
  updated_at: string;
};

export type PublicLinkParseTask = {
  id: number;
  product_id: number;
  task_type: string;
  url: string;
  platform: Platform;
  status: string;
  result: Record<string, unknown>;
  error: string | null;
  attempts: number;
  max_attempts: number;
  next_run_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type GeneratedAsset = {
  id: number;
  product_id: number;
  creative_plan_id: number;
  generation_job_id: number | null;
  asset_type: "image" | "video" | string;
  title: string | null;
  url: string;
  model: string | null;
  size: string | null;
  duration: number | null;
  status: string;
  asset_version: number;
  usage_contexts: string[];
  rating: number | null;
  tags: string[];
  note: string | null;
  asset_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProductDetail = Product & {
  skus: ProductSku[];
  platform_mappings: PlatformProductMapping[];
  competitors: Competitor[];
  competitor_monitors: CompetitorMonitor[];
  creative_plans: CreativePlan[];
  performance_records: PerformanceRecord[];
  review_reports: ReviewReport[];
  ad_recommendations: AdRecommendation[];
  ad_experiments: AdExperiment[];
  promotion_links: PromotionLink[];
  generated_assets: GeneratedAsset[];
  diagnoses: ProductDiagnosis[];
  generation_jobs: GenerationJob[];
  public_link_parse_tasks: PublicLinkParseTask[];
};

export type ModelSettings = {
  text: {
    base_url: string;
    api_key_masked: string;
    has_api_key: boolean;
    model: string;
  };
  image: {
    provider: string;
    base_url: string;
    api_key_masked: string;
    has_api_key: boolean;
    model: string;
    size: string;
    workspace_id: string;
    poll_interval_seconds: number;
    poll_max_attempts: number;
  };
  video: {
    provider: string;
    base_url: string;
    api_key_masked: string;
    has_api_key: boolean;
    model: string;
    size: string;
    duration: number;
    workspace_id: string;
    poll_interval_seconds: number;
    poll_max_attempts: number;
  };
};

export type UserRole = "owner" | "operator" | "viewer";
export type UserStatus = "active" | "disabled";

export type UserAccount = {
  id: number;
  email: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  permissions: {
    can_read: boolean;
    can_edit: boolean;
    can_manage_users: boolean;
    can_confirm_ad_actions: boolean;
  };
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AuthToken = {
  access_token: string;
  token_type: "bearer";
  user: UserAccount;
};

export type AgentRunStatus =
  | "queued"
  | "running"
  | "awaiting_review"
  | "resume_queued"
  | "completed"
  | "rejected"
  | "failed"
  | "cancelled";

export type AgentDiagnosisDraft = {
  source: "llm" | "rules";
  positioning: string;
  price_band: string;
  audience_insights: string[];
  pain_points: string[];
  selling_point_analysis: string[];
  risks: string[];
  recommendations: string[];
  provenance: Record<string, unknown>;
};

export type AgentCreativePlanDraft = {
  title: string;
  angle: string;
  layout: string;
  headline: string;
  sub_headline: string;
  visual_focus: string;
  proof_points: string[];
  suitable_audience: string;
  image_prompt: string;
  source: "llm" | "rules";
  provenance: Record<string, unknown>;
};

export type AgentDraftOutput = {
  diagnosis: AgentDiagnosisDraft;
  creative_plans: AgentCreativePlanDraft[];
};

export type AgentQualityIssue = {
  code: string;
  severity: "warning" | "error";
  message: string;
  field: string | null;
};

export type AgentQualityReport = {
  passed?: boolean;
  score?: number;
  issues?: AgentQualityIssue[];
  revision_recommended?: boolean;
  checked_rules?: string[];
};

export type AgentRunEvent = {
  id: number;
  event_type: string;
  agent_name: string | null;
  operation_name: string | null;
  status: string | null;
  message: string | null;
  input_snapshot: Record<string, unknown>;
  output_snapshot: Record<string, unknown>;
  metrics: Record<string, unknown>;
  trace_id: string | null;
  span_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentRunReview = {
  id: number;
  reviewed_by_user_id: number;
  decision: "approve" | "edit_and_approve" | "reject";
  edited_output: Record<string, unknown>;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentRun = {
  id: number;
  thread_id: string;
  workspace_id: number | null;
  task_id: number | null;
  product_id: number | null;
  requested_by_user_id: number;
  workflow_key: string;
  workflow_version: string;
  attempt: number;
  queue_name: string | null;
  status: AgentRunStatus;
  current_agent: string | null;
  revision_count: number;
  max_revisions: number;
  budget: Record<string, unknown>;
  usage: Record<string, unknown>;
  version_manifest: Record<string, unknown>;
  context_snapshot: Record<string, unknown>;
  draft_output: Partial<AgentDraftOutput>;
  quality_report: AgentQualityReport;
  final_output: Record<string, unknown>;
  error: string | null;
  lease_owner: string | null;
  lease_expires_at: string | null;
  timeout_at: string | null;
  cancel_requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  events: AgentRunEvent[];
  reviews: AgentRunReview[];
};

export type WorkspaceAccess = {
  workspace: {
    id: number;
    slug: string;
    name: string;
    status: "active" | "archived";
    settings: Record<string, unknown>;
    created_at: string;
    updated_at: string;
  };
  membership: {
    id: number;
    workspace_id: number;
    user_id: number;
    role: UserRole;
    status: "active" | "disabled";
    created_at: string;
    updated_at: string;
  };
};

export type AgentRiskLevel = "R0" | "R1" | "R2" | "R3";
export type AgentTaskStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type AgentDefinition = {
  key: string;
  version: string;
  description: string;
  tools: string[];
};

export type WorkflowDefinition = {
  key: string;
  version: string;
  title: string;
  description: string;
  agents: string[];
  required_context_any: string[];
  default_risk_level: AgentRiskLevel;
};

export type AgentCatalog = {
  coordinator: AgentDefinition;
  agents: AgentDefinition[];
  workflows: WorkflowDefinition[];
};

export type AgentTask = {
  id: number;
  workspace_id: number;
  conversation_id: number | null;
  requested_by_user_id: number;
  workflow_key: string;
  workflow_version: string;
  title: string;
  intent: string | null;
  status: AgentTaskStatus;
  risk_level: AgentRiskLevel;
  context_scope: Record<string, unknown>;
  input_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  version_manifest: Record<string, unknown>;
  error: string | null;
  cancelled_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentApproval = {
  id: number;
  workspace_id: number;
  task_id: number;
  run_id: number;
  requested_by_user_id: number;
  decided_by_user_id: number | null;
  action_key: string;
  risk_level: AgentRiskLevel;
  status: "pending" | "approved" | "rejected" | "expired" | "cancelled";
  request_payload: Record<string, unknown>;
  decision_payload: Record<string, unknown>;
  note: string | null;
  expires_at: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentMemory = {
  id: number;
  workspace_id: number;
  created_by_user_id: number;
  scope_type: "workspace" | "store" | "product" | "user";
  scope_id: string | null;
  memory_key: string;
  schema_version: string;
  content: Record<string, unknown>;
  source_type: string;
  source_reference: Record<string, unknown>;
  status: "active" | "revoked" | "expired";
  effective_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
};
