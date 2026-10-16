/** 智能体域错误码映射（DesignSpec §6 错误码体系 / ADR-07 / PRD M-06）。
 *
 * 后端在错误响应体中提供机器可读的 code 字段，detail 文本保留用于兼容。
 * 本模块把 code 转换为可读文案，并在缺失 code 时回退到 detail 关键字匹配，
 * 保证前端给出准确提示，而不是只透传英文 detail。
 */

/** 错误码到中文提示的映射；未列出的 code 由调用方兜底为通用文案。 */
export const AGENT_ERROR_MESSAGES: Record<string, string> = {
  AUTH_TOKEN_INVALID: "登录状态已失效，请重新登录。",
  AUTH_PERMISSION_DENIED: "当前账号没有执行该操作的权限。",
  AUTH_WORKSPACE_MISMATCH: "目标资源不属于当前工作区。",
  BIZ_INVENTORY_INSUFFICIENT: "可用库存不足，操作被拒绝。",
  BIZ_PLAN_TYPE_MISMATCH: "方案类型与生成任务不匹配。",
  BIZ_STATE_TRANSITION_INVALID: "当前状态不允许该操作。",
  MODEL_NOT_CONFIGURED: "模型尚未配置，请先在「模型设置」完成配置。",
  MODEL_RESPONSE_INVALID: "模型返回内容不合规，已回退为规则结果。",
  MODEL_UPSTREAM_ERROR: "模型服务不可达或返回异常，请检查配置。",
  MEDIA_SUBMIT_FAILED: "媒体生成提交失败。",
  MEDIA_POLL_TIMEOUT: "媒体生成轮询超时，任务已标记失败。",
  MEDIA_DOWNLOAD_FAILED: "媒体文件下载失败。",
  JOB_NOT_RETRYABLE: "该任务当前不可重试。",
  JOB_NOT_CANCELLABLE: "该任务当前不可取消。",
  JOB_ALREADY_RUNNING: "任务已在执行中，请勿重复提交。",
  AGENT_TOOL_NOT_ALLOWED: "该动作不在工具白名单内，已被拒绝。",
  AGENT_TOOL_NO_ADAPTER: "该工具尚未接入执行实现。",
  AGENT_LEASE_LOST: "执行权属凭证已失效，本次运行被终止。",
  AGENT_BUDGET_EXCEEDED: "本次运行已超出额度预算，已被终止。",
  APPR_EXPIRED: "审批已超过 24 小时有效期，已自动失效并取消运行。",
  APPR_ALREADY_DECIDED: "该审批已被处理，请刷新后查看最新状态。",
  APPR_EDIT_OUTPUT_REQUIRED: "「修改后通过」必须提交完整的结构化结果。",
  SYS_DEPENDENCY_UNAVAILABLE: "依赖服务暂不可用，请稍后重试。",
};

/** 从错误响应体中提取机器可读错误码；缺失时回退到 detail 关键字，再回退为 "failed"。 */
export async function extractAgentErrorCode(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { code?: unknown; detail?: unknown };
    if (typeof payload.code === "string" && payload.code) {
      return payload.code;
    }
    const detail = typeof payload.detail === "string" ? payload.detail : "";
    return matchDetailToCode(detail) ?? "failed";
  } catch {
    // 上游返回非 JSON 时无法解析 code，统一回退为通用失败。
    return "failed";
  }
}

/** 把错误码转换为可读提示；空值或未知码返回空串，由调用方决定是否展示兜底文案。 */
export function describeAgentErrorCode(code: string | undefined): string {
  if (!code || code === "failed") {
    return "";
  }
  return AGENT_ERROR_MESSAGES[code] ?? "";
}

/** 依据 detail 关键字回退匹配已知错误码，兼容尚未返回 code 字段的后端。 */
function matchDetailToCode(detail: string): string | null {
  const normalized = detail.toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized.includes("expired")) {
    return "APPR_EXPIRED";
  }
  if (normalized.includes("not pending") || normalized.includes("already")) {
    return "APPR_ALREADY_DECIDED";
  }
  if (normalized.includes("not configured")) {
    return "MODEL_NOT_CONFIGURED";
  }
  if (normalized.includes("concurrency limit")) {
    return "AGENT_BUDGET_EXCEEDED";
  }
  return null;
}
