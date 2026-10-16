import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AUTH_COOKIE_NAME, WORKSPACE_COOKIE_NAME } from "@/lib/session";

/** 处理退出登录请求：读取表单和路径参数，调用后端 API，并按结果响应或重定向。 */
export async function POST() {
  const cookieStore = await cookies();
  cookieStore.delete(AUTH_COOKIE_NAME);
  cookieStore.delete(WORKSPACE_COOKIE_NAME);
  redirect("/login");
}
