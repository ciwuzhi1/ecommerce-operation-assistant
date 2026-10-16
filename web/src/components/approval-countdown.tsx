"use client";

import { useEffect, useState } from "react";

/** 审批有效期（Q5 决策）：审批创建后 24 小时内未决即自动失效，并联动取消运行。 */
const APPROVAL_VALIDITY_MS = 24 * 60 * 60 * 1000;

/** 审批剩余有效期：提醒审批人时间约束，并展示剩余进度。
 *
 * 依据 PRD FR-52 与 Q5 决策（有效期 24 小时）：超期未决将自动失效，并联动取消本次运行。
 * 为避免服务端与客户端时间差导致水合不一致，首次渲染只占位，挂载后再启动计时。
 */
export function ApprovalCountdown({ expiresAt }: { expiresAt: string | null }) {
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  if (!expiresAt) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs font-medium text-amber-900">审批有效期剩余</p>
          <p className="text-sm font-semibold text-amber-900">—</p>
        </div>
        <p className="mt-2 text-xs text-amber-700">该审批尚未设置有效期。</p>
      </div>
    );
  }

  const expiry = new Date(expiresAt).getTime();
  const remainingMs = now === null ? null : Math.max(expiry - now, 0);
  const expired = remainingMs === 0;
  const remainingRatio = remainingMs === null ? 0 : clamp(remainingMs / APPROVAL_VALIDITY_MS, 0, 1);
  const urgent = remainingMs !== null && remainingMs <= 60 * 60 * 1000;

  const tone = expired
    ? { border: "border-rose-200", bg: "bg-rose-50", text: "text-rose-900", bar: "bg-rose-500" }
    : urgent
      ? { border: "border-rose-200", bg: "bg-rose-50", text: "text-rose-900", bar: "bg-rose-500" }
      : { border: "border-amber-200", bg: "bg-amber-50", text: "text-amber-900", bar: "bg-amber-500" };

  return (
    <div className={`rounded-md border p-3 ${tone.border} ${tone.bg}`}>
      <div className="flex items-center justify-between gap-4">
        <p className={`text-xs font-medium ${tone.text}`}>审批有效期剩余</p>
        <p className={`text-sm font-semibold ${tone.text}`}>
          {remainingMs === null ? "计算中…" : expired ? "已过期" : formatRemaining(remainingMs)}
        </p>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/70">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${tone.bar}`}
          style={{ width: `${Math.round((expired ? 0 : remainingRatio) * 100)}%` }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round((expired ? 0 : remainingRatio) * 100)}
          aria-label="审批剩余有效期进度"
        />
      </div>
      <p className={`mt-2 text-xs ${tone.text}`}>
        {expired ? "审批已超过有效期，将自动失效并联动取消本次运行。" : "超期未决将自动失效，并联动取消本次运行。"}
      </p>
    </div>
  );
}

/** 把剩余毫秒格式化为「3h 12m」/「12m 05s」形式，接近到期时精确到秒。 */
function formatRemaining(remainingMs: number): string {
  const totalSeconds = Math.floor(remainingMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  }
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

/** clamp，把比例限制在 [0, 1]，避免过期或时钟漂移导致进度条越界。 */
function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
}
