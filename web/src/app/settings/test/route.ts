import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { describeAgentErrorCode, extractAgentErrorCode } from "@/lib/agent-error";
import { authHeaders } from "@/lib/session";

/** 处理模型设置/测试请求：调用后端连通性测试接口，并把结果回显到设置页。 */
export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const target = String(formData.get("target") ?? "text");

  // 连通性测试只请求后端测试接口，不在前端创建素材记录或保存供应商响应。
  const response = await fetch(`${API_BASE_URL}/api/v1/model-settings/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ target }),
  });

  let message = "";
  if (response.ok) {
    try {
      const data = (await response.json()) as { message?: string };
      message = String(data.message ?? "");
    } catch {
      // 供应商或代理返回非 JSON 时仍给用户一个可读状态，避免设置页空白失败。
      message = "测试通过";
    }
  } else {
    // 优先按机器可读错误码给出准确提示（MODEL_NOT_CONFIGURED / MODEL_UPSTREAM_ERROR）。
    const code = await extractAgentErrorCode(response);
    message = describeAgentErrorCode(code) || "测试失败，请检查配置。";
  }

  const params = new URLSearchParams({
    test: target,
    status: response.ok ? "ok" : "error",
    message,
  });

  redirect(`/settings?${params.toString()}`);
}
