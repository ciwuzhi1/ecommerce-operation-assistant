import { redirect } from "next/navigation";
import { NextRequest } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { authHeaders } from "@/lib/session";

/** 处理模型设置/更新请求：读取表单和路径参数，调用后端 API，并按结果重定向回设置页。 */
export async function POST(request: NextRequest) {
  const formData = await request.formData();
  // 设置表单按 text/image/video 分组提交；空 API Key 由后端解释为「保持原密钥不变」。
  const body = {
    text: {
      base_url: value(formData, "text_base_url"),
      api_key: value(formData, "text_api_key"),
      model: value(formData, "text_model"),
    },
    image: {
      provider: value(formData, "image_provider"),
      base_url: value(formData, "image_base_url"),
      api_key: value(formData, "image_api_key"),
      model: value(formData, "image_model"),
      size: value(formData, "image_size"),
      workspace_id: value(formData, "image_workspace_id"),
      poll_interval_seconds: numberValue(formData, "image_poll_interval_seconds"),
      poll_max_attempts: numberValue(formData, "image_poll_max_attempts"),
    },
    video: {
      provider: value(formData, "video_provider"),
      base_url: value(formData, "video_base_url"),
      api_key: value(formData, "video_api_key"),
      model: value(formData, "video_model"),
      size: value(formData, "video_size"),
      duration: numberValue(formData, "video_duration"),
      workspace_id: value(formData, "video_workspace_id"),
      poll_interval_seconds: numberValue(formData, "video_poll_interval_seconds"),
      poll_max_attempts: numberValue(formData, "video_poll_max_attempts"),
    },
  };

  const response = await fetch(`${API_BASE_URL}/api/v1/model-settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify(body),
  });

  // 保存结果通过 URL 参数回显，页面重新服务端渲染后读取最新脱敏配置。
  redirect(`/settings?save=${response.ok ? "ok" : "error"}`);
}

/** 值，把不可信表单值转换为去空白字符串。 */
function value(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim();
}

/** 数值值，把不可信表单值转换为数字；空值返回 undefined 以便后端保留原配置。 */
function numberValue(formData: FormData, name: string) {
  const raw = value(formData, name);
  return raw ? Number(raw) : undefined;
}
