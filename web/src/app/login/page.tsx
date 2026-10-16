import { LockKeyhole } from "lucide-react";
import Link from "next/link";

type LoginPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/** 渲染登录页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = (await searchParams) ?? {};
  const error = Array.isArray(params.error) ? params.error[0] : params.error;

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f7f8fb] px-5 py-10 text-slate-950">
      <section className="w-full max-w-md rounded-md border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-950 text-white">
            <LockKeyhole className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-medium text-emerald-700">Ecommerce Operation Assistant</p>
            <h1 className="text-xl font-semibold">登录工作台</h1>
          </div>
        </div>

        {error ? (
          <div className="mt-5 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            邮箱或密码不正确，或者账号已停用。
          </div>
        ) : null}

        <form action="/login/submit" method="post" className="mt-6 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">邮箱</span>
            <input
              name="email"
              type="email"
              required
              className="mt-2 h-11 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
              placeholder="owner@example.com"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">密码</span>
            <input
              name="password"
              type="password"
              required
              className="mt-2 h-11 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
              placeholder="输入密码"
            />
          </label>
          <button
            type="submit"
            className="inline-flex h-11 w-full items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-slate-800"
          >
            登录
          </button>
        </form>

        <Link href="/" className="mt-4 inline-flex text-sm text-slate-500 hover:text-slate-900">
          返回首页
        </Link>
      </section>
    </main>
  );
}
