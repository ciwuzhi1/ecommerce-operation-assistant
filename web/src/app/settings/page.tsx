import {
  AlertCircle,
  ArrowLeft,
  Bot,
  CheckCircle2,
  FlaskConical,
  ImageIcon,
  KeyRound,
  Users,
  Video,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { getCurrentUser, getModelSettings, getUsers } from "@/lib/api";
import { getAuthToken } from "@/lib/session";
import type { UserAccount } from "@/types";

type SettingsPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/** 渲染模型设置页面；在服务端加载业务数据，并把交互交给对应表单或客户端组件。 */
export default async function SettingsPage({ searchParams }: SettingsPageProps) {
  const token = await getAuthToken();
  const currentUser = token ? await getCurrentUser(token) : null;
  const canEdit = Boolean(currentUser?.permissions.can_edit);
  const canManageUsers = Boolean(currentUser?.permissions.can_manage_users);
  // 用户列表只有具备管理权限时才请求，避免只读/普通运营账号看到成员管理数据。
  const [settings, users] = await Promise.all([getModelSettings(), canManageUsers ? getUsers() : Promise.resolve([])]);
  const params = (await searchParams) ?? {};
  const saveStatus = scalar(params.save);
  const testStatus = scalar(params.status);
  const testTarget = scalar(params.test);
  const testMessage = scalar(params.message);
  const userStatus = scalar(params.user);

  if (!settings) {
    return (
      <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
        <div className="mx-auto max-w-5xl">
          <BackLink />
          <div className="mt-6 rounded-md border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
            模型配置读取失败，请确认后端服务已经启动。
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f7f8fb] px-5 py-6 text-slate-950 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <BackLink />
            <p className="mt-5 text-sm font-medium text-emerald-700">Model Settings</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-normal text-slate-950 sm:text-3xl">
              模型配置中心
            </h1>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatusPill
              label="文本模型"
              value={settings.text.model || "未配置"}
              active={settings.text.has_api_key && Boolean(settings.text.model)}
            />
            <StatusPill
              label="图片模型"
              value={settings.image.model || "未配置"}
              active={settings.image.has_api_key && Boolean(settings.image.model)}
            />
            <StatusPill
              label="视频模型"
              value={settings.video.model || "未配置"}
              active={settings.video.has_api_key && Boolean(settings.video.model)}
            />
          </div>
        </header>

        {saveStatus ? (
          <Notice
            ok={saveStatus === "ok"}
            message={saveStatus === "ok" ? "配置已保存，下一次调用会使用新模型。" : "配置保存失败。"}
          />
        ) : null}

        {testStatus ? (
          <Notice
            ok={testStatus === "ok"}
            message={`${testTargetLabel(testTarget)}测试${
              testStatus === "ok" ? "通过" : "失败"
            }：${testMessage || "-"}`}
          />
        ) : null}

        {userStatus ? (
          <Notice
            ok={userStatus === "created"}
            message={userStatus === "created" ? "用户已创建。" : "用户创建失败，请检查邮箱是否重复。"}
          />
        ) : null}

        <form
          id="model-settings-form"
          action="/settings/update"
          method="post"
          className="grid gap-6 xl:grid-cols-3"
        >
          <section className="rounded-md border border-slate-200 bg-white p-5">
            <SectionTitle
              icon={<Bot className="h-5 w-5" aria-hidden="true" />}
              title="文本模型"
              subtitle="用于诊断、主图方案、视频脚本和复盘。"
              tone="bg-slate-950"
            />
            <div className="mt-5 space-y-4">
              <TextInput
                label="Base URL"
                name="text_base_url"
                defaultValue={settings.text.base_url}
                placeholder="https://api.deepseek.com"
              />
              <TextInput
                label="Model"
                name="text_model"
                defaultValue={settings.text.model}
                placeholder="deepseek-v4-pro"
              />
              <SecretInput
                label="API Key"
                name="text_api_key"
                masked={settings.text.api_key_masked}
              />
            </div>
          </section>

          <section className="rounded-md border border-slate-200 bg-white p-5">
            <SectionTitle
              icon={<ImageIcon className="h-5 w-5" aria-hidden="true" />}
              title="图片模型"
              subtitle="用于主图方案的一键出图。"
              tone="bg-emerald-600"
            />
            <div className="mt-5 space-y-4">
              <TextInput
                label="Provider"
                name="image_provider"
                defaultValue={settings.image.provider}
                placeholder="dashscope"
              />
              <TextInput
                label="Model"
                name="image_model"
                defaultValue={settings.image.model}
                placeholder="wan2.6-t2i"
              />
              <TextInput
                label="Base URL"
                name="image_base_url"
                defaultValue={settings.image.base_url}
                placeholder="https://dashscope.aliyuncs.com/api/v1"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput
                  label="Size"
                  name="image_size"
                  defaultValue={settings.image.size}
                  placeholder="1280*1280"
                />
                <TextInput
                  label="业务空间 ID"
                  name="image_workspace_id"
                  defaultValue={settings.image.workspace_id}
                  placeholder="llm-..."
                />
                <NumberInput
                  label="轮询间隔秒"
                  name="image_poll_interval_seconds"
                  defaultValue={settings.image.poll_interval_seconds}
                />
                <NumberInput
                  label="最大轮询次数"
                  name="image_poll_max_attempts"
                  defaultValue={settings.image.poll_max_attempts}
                />
              </div>
              <SecretInput
                label="API Key"
                name="image_api_key"
                masked={settings.image.api_key_masked}
              />
            </div>
          </section>

          <section className="rounded-md border border-slate-200 bg-white p-5">
            <SectionTitle
              icon={<Video className="h-5 w-5" aria-hidden="true" />}
              title="视频模型"
              subtitle="用于短视频脚本的一键成片。"
              tone="bg-violet-600"
            />
            <div className="mt-5 space-y-4">
              <ProviderSelect
                label="Provider"
                name="video_provider"
                defaultValue={settings.video.provider}
              />
              <TextInput
                label="Model"
                name="video_model"
                defaultValue={settings.video.model}
                placeholder="wan2.6-t2v"
              />
              <TextInput
                label="Base URL"
                name="video_base_url"
                defaultValue={settings.video.base_url}
                placeholder="https://dashscope.aliyuncs.com/api/v1"
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <TextInput
                  label="Size"
                  name="video_size"
                  defaultValue={settings.video.size}
                  placeholder="1280*720"
                />
                <NumberInput
                  label="时长秒"
                  name="video_duration"
                  defaultValue={settings.video.duration}
                />
                <TextInput
                  label="业务空间 ID"
                  name="video_workspace_id"
                  defaultValue={settings.video.workspace_id}
                  placeholder="llm-..."
                />
                <NumberInput
                  label="轮询间隔秒"
                  name="video_poll_interval_seconds"
                  defaultValue={settings.video.poll_interval_seconds}
                />
                <NumberInput
                  label="最大轮询次数"
                  name="video_poll_max_attempts"
                  defaultValue={settings.video.poll_max_attempts}
                />
              </div>
              <SecretInput
                label="API Key"
                name="video_api_key"
                masked={settings.video.api_key_masked}
              />
            </div>
          </section>
        </form>

        {canManageUsers ? (
          <UserManagementPanel users={users} />
        ) : (
          <ReadOnlyNotice message="当前账号没有用户管理权限，只能查看模型配置状态。" />
        )}

        {canEdit ? (
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="submit"
              form="model-settings-form"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-slate-950 px-5 text-sm font-semibold text-white hover:bg-slate-800"
            >
              <KeyRound className="h-4 w-4" aria-hidden="true" />
              保存配置
            </button>
            <TestButton target="text" label="测试文本模型" />
            <TestButton target="image" label="测试图片模型" />
            <TestButton target="video" label="测试视频模型" />
          </div>
        ) : (
          <ReadOnlyNotice message="当前账号为只读权限，模型保存和测试按钮已隐藏。" />
        )}
      </div>
    </main>
  );
}

/** 渲染 ReadOnlyNotice 组件，集中展示读取onlynotice所需的数据、状态和操作入口。 */
function ReadOnlyNotice({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      {message}
    </div>
  );
}

/** 渲染 UserManagementPanel 组件，集中展示用户管理面板所需的数据、状态和操作入口。 */
function UserManagementPanel({ users }: { users: UserAccount[] }) {
  return (
    <section className="rounded-md border border-slate-200 bg-white p-5">
      <SectionTitle
        icon={<Users className="h-5 w-5" aria-hidden="true" />}
        title="用户与权限"
        subtitle="按角色控制编辑、成员管理和投放确认权限"
        tone="bg-sky-700"
      />

      <form action="/settings/users/create" method="post" className="mt-5 grid gap-4 lg:grid-cols-[1fr_1fr_180px_180px_auto] lg:items-end">
        <TextInput label="邮箱" name="email" defaultValue="" placeholder="ops@example.com" />
        <TextInput label="姓名" name="display_name" defaultValue="" placeholder="运营同学" />
        <RoleSelect />
        <label className="block">
          <span className="text-sm font-medium text-slate-700">初始密码</span>
          <input
            name="password"
            type="password"
            minLength={8}
            placeholder="可留空"
            className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          />
        </label>
        <button
          type="submit"
          className="inline-flex h-11 items-center justify-center rounded-md bg-slate-950 px-4 text-sm font-semibold text-white hover:bg-slate-800"
        >
          添加用户
        </button>
      </form>

      <div className="mt-5 overflow-hidden rounded-md border border-slate-200">
        <div className="grid grid-cols-[1fr_120px_120px_1.2fr] bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-500">
          <span>用户</span>
          <span>角色</span>
          <span>状态</span>
          <span>权限</span>
        </div>
        {users.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            暂无用户。先添加 owner 或 operator，再逐步接入登录鉴权。
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {users.map((user) => (
              <div key={user.id} className="grid grid-cols-[1fr_120px_120px_1.2fr] px-4 py-3 text-sm">
                <div>
                  <p className="font-medium text-slate-950">{user.display_name}</p>
                  <p className="mt-1 text-xs text-slate-500">{user.email}</p>
                </div>
                <span className="text-slate-700">{roleLabel(user.role)}</span>
                <span className="text-slate-700">{user.status === "active" ? "启用" : "停用"}</span>
                <div className="flex flex-wrap gap-1.5">
                  {permissionBadges(user).map((badge) => (
                    <span key={badge} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      {badge}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

/** 渲染 BackLink 组件，集中展示返回链接所需的数据、状态和操作入口。 */
function BackLink() {
  return (
    <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      返回商品池
    </Link>
  );
}

/** 渲染 SectionTitle 组件，集中展示section标题所需的数据、状态和操作入口。 */
function SectionTitle({
  icon,
  title,
  subtitle,
  tone,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-10 w-10 items-center justify-center rounded-md text-white ${tone}`}>
        {icon}
      </div>
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>
    </div>
  );
}

/** 渲染 StatusPill 组件，集中展示状态pill所需的数据、状态和操作入口。 */
function StatusPill({ label, value, active }: { label: string; value: string; active: boolean }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs text-slate-500">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${active ? "bg-emerald-500" : "bg-slate-300"}`} />
        <p className="text-sm font-semibold text-slate-900">{value}</p>
      </div>
    </div>
  );
}

/** 渲染 Notice 组件，集中展示notice所需的数据、状态和操作入口。 */
function Notice({ ok, message }: { ok: boolean; message: string }) {
  const Icon = ok ? CheckCircle2 : AlertCircle;
  return (
    <div
      className={`flex items-start gap-3 rounded-md border p-4 text-sm ${
        ok
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-rose-200 bg-rose-50 text-rose-800"
      }`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

/** 渲染 TextInput 组件，集中展示文本input所需的数据、状态和操作入口。 */
function TextInput({
  label,
  name,
  defaultValue,
  placeholder,
}: {
  label: string;
  name: string;
  defaultValue: string;
  placeholder: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
      />
    </label>
  );
}

/** 渲染 NumberInput 组件，集中展示数值input所需的数据、状态和操作入口。 */
function NumberInput({
  label,
  name,
  defaultValue,
}: {
  label: string;
  name: string;
  defaultValue: number;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        type="number"
        min="1"
        defaultValue={defaultValue}
        className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
      />
    </label>
  );
}

/** 渲染 ProviderSelect 组件，集中展示provider选择所需的数据、状态和操作入口。 */
function ProviderSelect({
  label,
  name,
  defaultValue,
}: {
  label: string;
  name: string;
  defaultValue: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <select
        name={name}
        defaultValue={defaultValue || "dashscope"}
        className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
      >
        <option value="dashscope">DashScope / 通义万相</option>
        <option value="jimeng">Jimeng / 即梦</option>
        <option value="custom">Custom</option>
      </select>
    </label>
  );
}

/** 渲染 RoleSelect 组件，集中展示角色选择所需的数据、状态和操作入口。 */
function RoleSelect() {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">角色</span>
      <select
        name="role"
        defaultValue="operator"
        className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
      >
        <option value="owner">Owner</option>
        <option value="operator">Operator</option>
        <option value="viewer">Viewer</option>
      </select>
    </label>
  );
}

/** 渲染 SecretInput 组件，集中展示secretinput所需的数据、状态和操作入口。 */
function SecretInput({ label, name, masked }: { label: string; name: string; masked: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {/* 密钥输入框不回填明文，只显示脱敏占位；留空时后端保留原 key。 */}
      <input
        name={name}
        type="password"
        placeholder={masked ? `当前：${masked}，留空则保持不变` : "粘贴 API Key"}
        className="mt-2 h-11 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
      />
    </label>
  );
}

/** 渲染 TestButton 组件，集中展示test按钮所需的数据、状态和操作入口。 */
function TestButton({ target, label }: { target: "text" | "image" | "video"; label: string }) {
  return (
    <form action="/settings/test" method="post">
      <input type="hidden" name="target" value={target} />
      <button
        type="submit"
        className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-5 text-sm font-semibold text-slate-700 hover:bg-slate-50 sm:w-auto"
      >
        <FlaskConical className="h-4 w-4" aria-hidden="true" />
        {label}
      </button>
    </form>
  );
}

/** 标量，把不可信表单或 JSON 值转换为页面逻辑可安全使用的类型。 */
function scalar(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

/** 把testtarget状态映射为中文显示文本，保持页面口径一致。 */
function testTargetLabel(target: string | undefined) {
  if (target === "image") {
    return "图片模型";
  }
  if (target === "video") {
    return "视频模型";
  }
  return "文本模型";
}

/** 把角色状态映射为中文显示文本，保持页面口径一致。 */
function roleLabel(role: UserAccount["role"]): string {
  if (role === "owner") {
    return "Owner";
  }
  if (role === "viewer") {
    return "Viewer";
  }
  return "Operator";
}

/** 权限badges，封装当前页面重复使用的转换或展示规则，并统一处理空值边界。 */
function permissionBadges(user: UserAccount): string[] {
  const badges = ["可查看"];
  if (user.permissions.can_edit) {
    badges.push("可编辑");
  }
  if (user.permissions.can_manage_users) {
    badges.push("管理用户");
  }
  if (user.permissions.can_confirm_ad_actions) {
    badges.push("确认投放");
  }
  return badges;
}
