import { cookies } from "next/headers";

export const AUTH_COOKIE_NAME = "eo_auth_token";
export const WORKSPACE_COOKIE_NAME = "eo_workspace_id";

/** 获取认证token，集中维护服务端会话 Cookie 与转发后端所需的认证请求头。 */
export async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(AUTH_COOKIE_NAME)?.value ?? null;
}

/** 认证headers，集中维护服务端会话 Cookie 与转发后端所需的认证请求头。 */
export async function authHeaders(): Promise<Record<string, string>> {
  // 服务端组件和 route handler 统一从 httpOnly cookie 转发 Bearer token，前端 JS 不直接持有 token。
  const token = await getAuthToken();
  if (!token) return {};
  const workspaceId = await getActiveWorkspaceId();
  return {
    Authorization: `Bearer ${token}`,
    ...(workspaceId ? { "X-Workspace-ID": String(workspaceId) } : {}),
  };
}

/** Workspace认证headers，集中维护服务端会话 Cookie 与转发后端所需的认证请求头。 */
export async function workspaceAuthHeaders(workspaceId: number): Promise<Record<string, string>> {
  return {
    ...(await authHeaders()),
    "X-Workspace-ID": String(workspaceId),
  };
}

/** 获取当前WorkspaceID，集中维护服务端会话 Cookie 与转发后端所需的认证请求头。 */
export async function getActiveWorkspaceId(): Promise<number | null> {
  const cookieStore = await cookies();
  const value = Number(cookieStore.get(WORKSPACE_COOKIE_NAME)?.value);
  return Number.isInteger(value) && value > 0 ? value : null;
}
