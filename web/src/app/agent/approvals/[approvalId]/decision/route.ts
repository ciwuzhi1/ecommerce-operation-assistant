import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { extractAgentErrorCode } from "@/lib/agent-error";
import { workspaceAuthHeaders } from "@/lib/session";

type RouteContext = { params: Promise<{ approvalId: string }> };

/** 审批工作台三决策：approve（通过）/ edit_and_approve（修改后通过）/ reject（驳回）。 */
const WORKBENCH_DECISIONS = ["approve", "edit_and_approve", "reject"] as const;

/** 处理Agent/审批/决策请求：读取表单和路径参数，调用后端 API，并按结果重定向回审批收件箱。 */
export async function POST(request: Request, context: RouteContext) {
  const { approvalId } = await context.params;
  const formData = await request.formData();
  const workspaceId = Number(formData.get("workspace_id"));
  const decision = String(formData.get("decision") ?? "");
  const note = String(formData.get("note") ?? "").trim() || null;
  const editedOutputText = String(formData.get("edited_output") ?? "").trim();

  const valid =
    Number.isInteger(workspaceId) &&
    workspaceId > 0 &&
    /^\d+$/.test(approvalId) &&
    (WORKBENCH_DECISIONS as readonly string[]).includes(decision);

  if (!valid) {
    return redirectToAgent(request, workspaceId, "failed");
  }

  // 后端审批接口接受 approve / edit_and_approve / reject 三决策；
  // edit_and_approve 必须携带非空 edited_output，否则后端按校验失败（APPR_EDIT_OUTPUT_REQUIRED）拒绝。
  let editedOutput: Record<string, unknown> | null = null;
  if (decision === "edit_and_approve") {
    if (!editedOutputText) {
      return redirectToAgent(request, workspaceId, "APPR_EDIT_OUTPUT_REQUIRED");
    }
    try {
      const parsed = JSON.parse(editedOutputText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("edited_output must be an object");
      }
      editedOutput = parsed as Record<string, unknown>;
    } catch {
      return redirectToAgent(request, workspaceId, "APPR_EDIT_OUTPUT_REQUIRED");
    }
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/agent/approvals/${approvalId}/decision`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await workspaceAuthHeaders(workspaceId)),
      },
      body: JSON.stringify({ decision, note, edited_output: editedOutput }),
    },
  );
  const result = response.ok ? "approved" : await extractAgentErrorCode(response);
  return redirectToAgent(request, workspaceId, result);
}

/** 重定向回 Agent 审批收件箱，并带上本次决策结果。 */
function redirectToAgent(request: Request, workspaceId: number, result: string) {
  const target = new URL("/agent", request.url);
  if (Number.isInteger(workspaceId) && workspaceId > 0) {
    target.searchParams.set("workspace", String(workspaceId));
  }
  target.searchParams.set("result", result);
  target.hash = "approval-inbox";
  return NextResponse.redirect(target, 303);
}
